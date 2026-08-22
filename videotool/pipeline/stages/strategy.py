"""Visual strategy plan pipeline stage."""
from __future__ import annotations

from dataclasses import asdict
from typing import Any

from videotool.domain.semantic_beat import SemanticBeat, SemanticFunction
from videotool.domain.strategy import SelectionRecord
from videotool.domain.visual_history import VisualHistory
from videotool.editorial import validation
from videotool.editorial.strategies import FUNCTION_CANDIDATES, STRATEGY_CATALOG
from videotool.pipeline.context import PipelineContext
from videotool.pipeline.fingerprints import stable_hash
from videotool.pipeline.stage import BasePipelineStage


def _default_strategy(beat: SemanticBeat | None, rec: SelectionRecord | None) -> str:
    fn = beat.semantic_function if beat is not None else None
    if fn is None and rec is not None:
        try:
            fn = SemanticFunction(rec.semantic_function)
        except ValueError:
            fn = None
    if fn is not None:
        for candidate in FUNCTION_CANDIDATES.get(fn, []):
            if candidate in STRATEGY_CATALOG:
                return candidate
    return "cinematic_hold"


def _repair_strategy_records(
    records: list[SelectionRecord], beats: list[SemanticBeat], ctx: PipelineContext
) -> list[SelectionRecord]:
    """Repair malformed records AND create records for missing beats."""
    beat_map = {b.beat_id: b for b in beats}
    by_beat: dict[str, SelectionRecord] = {}
    for rec in records:
        beat = beat_map.get(rec.beat_id)
        if (
            beat is not None
            and rec.selected_strategy in STRATEGY_CATALOG
            and len(rec.reason) >= 20
        ):
            by_beat[rec.beat_id] = rec
        else:
            default_id = _default_strategy(beat, rec)
            ctx.record_repair(
                "visual_strategy_plan",
                f"{rec.beat_id}: unusable selection",
                f"fallback strategy '{default_id}'",
            )
            by_beat[rec.beat_id] = SelectionRecord(
                beat_id=rec.beat_id,
                semantic_function=rec.semantic_function,
                selected_strategy=default_id,
                visual_family=STRATEGY_CATALOG[default_id].visual_family,
                reason=(
                    "deterministic fallback: planner output failed "
                    "stage validation; first catalog candidate used."
                ),
                is_fallback=True,
            )
    for beat in beats:  # beats with no record at all
        if beat.beat_id not in by_beat:
            default_id = _default_strategy(beat, None)
            ctx.record_repair(
                "visual_strategy_plan",
                f"{beat.beat_id}: missing selection record",
                f"created fallback strategy '{default_id}'",
            )
            by_beat[beat.beat_id] = SelectionRecord(
                beat_id=beat.beat_id,
                semantic_function=beat.semantic_function.value,
                selected_strategy=default_id,
                visual_family=STRATEGY_CATALOG[default_id].visual_family,
                reason=(
                    "deterministic fallback: no selection existed for "
                    "this beat; first catalog candidate used."
                ),
                is_fallback=True,
            )
    return [by_beat[b.beat_id] for b in beats if b.beat_id in by_beat]


class VisualStrategyPlanStage(BasePipelineStage):
    id = "visual_strategy_plan"

    def fingerprint(self, ctx: PipelineContext) -> str:
        planner_cfg = asdict(ctx.planner_config)
        return stable_hash(
            self.version,
            ctx.episode_id,
            ctx.state["beats_semantic_hash"],
            planner_cfg,
        )

    def execute(self, ctx: PipelineContext) -> list[dict]:
        records = ctx.planner.select(ctx.state["beats"], VisualHistory())
        records = _repair_strategy_records(records, ctx.state["beats"], ctx)
        return [r.to_dict() for r in records]

    def validate(self, payload: Any, ctx: PipelineContext) -> bool:
        try:
            records = [SelectionRecord.from_dict(r) for r in payload]
        except Exception:
            return False
        return validation.validate_strategy_plan(records, ctx.state["beats"]).ok
