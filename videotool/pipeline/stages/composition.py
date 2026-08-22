"""Visual compositions pipeline stage."""
from __future__ import annotations

from typing import Any

from videotool.domain.assets import MediaAsset
from videotool.domain.composition import VisualComposition
from videotool.domain.semantic_beat import SemanticBeat
from videotool.domain.visual_history import VisualHistory
from videotool.editorial import validation
from videotool.editorial.composition import (
    FAMILIES_VERSION,
    assets_for_beat,
    compose_beat,
)
from videotool.editorial.strategies import STRATEGY_CATALOG
from videotool.editorial.timing import annotate_composition_semantics
from videotool.pipeline.context import PipelineContext
from videotool.pipeline.fingerprints import stable_hash
from videotool.pipeline.stage import BasePipelineStage


def _fallback_invalid_compositions(
    comps: list[VisualComposition],
    beats: list[SemanticBeat],
    assets: list[MediaAsset],
    ctx: PipelineContext,
) -> list[VisualComposition]:
    report = validation.validate_compositions(comps, beats, assets, mode=ctx.mode)
    if report.ok:
        return comps
    beat_map = {b.beat_id: b for b in beats}
    bad_ids: set[str] = set()
    for err in report.errors:
        for comp in comps:
            if (
                err.startswith(f"{comp.composition_id}:")
                or err.startswith(f"{comp.composition_id}/")
                or err.startswith(f"{comp.beat_id}:")
            ):
                bad_ids.add(comp.composition_id)
    fallback_index = 0
    rebuilt = []
    for comp in comps:
        if comp.composition_id not in bad_ids:
            rebuilt.append(comp)
            continue
        beat = beat_map.get(comp.beat_id)
        if beat is None:
            continue
        ctx.record_repair(
            "visual_compositions",
            f"{comp.composition_id}: {report.errors[0]}",
            "deterministic fallback composition",
        )
        rebuilt.append(
            validation.deterministic_fallback_composition(
                beat, fallback_index, assets, family=comp.visual_family
            )
        )
        fallback_index += 1
    second = validation.validate_compositions(rebuilt, beats, assets, mode=ctx.mode)
    if not second.ok:
        # still broken: surface loudly at final QC, never hide
        ctx.record_repair(
            "visual_compositions",
            "fallback compositions still invalid",
            "kept for final QC to fail loudly",
        )
    return rebuilt


class VisualCompositionsStage(BasePipelineStage):
    id = "visual_compositions"

    def fingerprint(self, ctx: PipelineContext) -> str:
        import videotool.pipeline.runner as runner_module
        fam_ver = getattr(runner_module, "FAMILIES_VERSION", FAMILIES_VERSION)
        return stable_hash(
            self.version,
            ctx.episode_id,
            ctx.state["beats_semantic_hash"],
            ctx.state["plan_hash"],
            ctx.state["media_hash"],
            ctx.state["art_hash"],
            ctx.mode,
            fam_ver,
        )

    def execute(self, ctx: PipelineContext) -> list[dict]:
        history = VisualHistory()
        used: set[str] = set()
        sel_by_beat = {r.beat_id: r for r in ctx.state["strategy_plan"]}
        comps: list[VisualComposition] = []
        for beat in ctx.state["beats"]:
            sel = sel_by_beat.get(beat.beat_id)
            if sel is None:
                continue
            beat_assets = assets_for_beat(
                ctx.state["assets"], ctx.state["requirements"], beat.beat_id
            )
            try:
                strat_def = STRATEGY_CATALOG[sel.selected_strategy]
                comps.append(
                    compose_beat(
                        beat,
                        sel,
                        strat_def,
                        ctx.state["art_direction"],
                        beat_assets,
                        history,
                        used,
                        ctx.episode_id,
                    )
                )
            except Exception as exc:
                ctx.record_repair(
                    "visual_compositions",
                    f"{beat.beat_id}: family '{sel.visual_family}' raised {type(exc).__name__}",
                    "deterministic fallback composition",
                )
                comps.append(
                    validation.deterministic_fallback_composition(
                        beat, len(comps), beat_assets, family=sel.visual_family
                    )
                )
        comps = _fallback_invalid_compositions(
            comps, ctx.state["beats"], ctx.state["assets"], ctx
        )
        beat_by_id = {beat.beat_id: beat for beat in ctx.state["beats"]}
        for comp in comps:
            annotate_composition_semantics(comp, beat_by_id[comp.beat_id])
        return [c.to_dict() for c in comps]

    def validate(self, payload: Any, ctx: PipelineContext) -> bool:
        beat_ids = {b.beat_id for b in ctx.state["beats"]}
        try:
            comps = [VisualComposition.from_dict(c) for c in payload]
        except Exception:
            return False
        if not comps or any(c.beat_id not in beat_ids for c in comps):
            return False
        report = validation.validate_compositions(
            comps,
            ctx.state["beats"],
            ctx.state["assets"],
            mode=ctx.mode,
            allow_timing_independent_duration=True,
        )
        return report.ok
