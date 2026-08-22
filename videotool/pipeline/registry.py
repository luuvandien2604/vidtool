"""Stage definitions and registry for the video production pipeline (spec section 20).

Contains all 19 ordered, decoupled pipeline stages and the StageRegistry container.
"""
from __future__ import annotations

from dataclasses import asdict
from typing import Any, Callable

from videotool.domain.art_direction import EpisodeArtDirection
from videotool.domain.assets import AssetRequirement, MediaAsset
from videotool.domain.composition import VisualComposition
from videotool.domain.geometry import GeometryHistory, GeometryPlan
from videotool.domain.motion import MotionPlan
from videotool.domain.narration import Narration, synthetic_word_timings
from videotool.domain.semantic_beat import (
    SEMANTIC_BEAT_IDENTITY_VERSION,
    SemanticBeat,
    semantic_beats_identity,
)
from videotool.domain.strategy import SelectionRecord
from videotool.domain.timing import (
    NarrationTiming,
    SemanticAnchor,
    TimingBinding,
)
from videotool.domain.visual_history import VisualHistory
from videotool.editorial import validation
from videotool.editorial.composition import (
    FAMILIES_VERSION,
    assets_for_beat,
    compose_beat,
    history_from_compositions,
    semantic_asset_requirements,
)
from videotool.editorial.feasibility import run_feasibility_pass
from videotool.editorial.geometry import (
    GEOMETRY_CANDIDATE_VERSION,
    GEOMETRY_POLICY_VERSION,
    GEOMETRY_SCORE_VERSION,
    GEOMETRY_SIGNATURE_VERSION,
    GEOMETRY_SOLVER_VERSION,
    SEMANTIC_GEOMETRY_VERSION,
    geometry_input_projection,
    validate_geometry_plan,
    validate_geometry_plans,
)
from videotool.editorial.media import (
    ACQUISITION_SERVICE_VERSION,
    LICENSE_POLICY_VERSION,
    MEDIA_CACHE_VERSION,
    MEDIA_DOWNLOAD_VERSION,
    MEDIA_QUERY_VERSION,
    MEDIA_RANKING_VERSION,
    AcquisitionTrace,
    MediaAcquisitionService,
    MediaCache,
    MediaCandidate,
    MediaSearchPlan,
    plan_search,
    search_candidates,
    validate_media_assets,
)
from videotool.editorial.motion import build_motion_plan
from videotool.editorial.strategies import STRATEGY_CATALOG
from videotool.editorial.timeline import build_timeline
from videotool.editorial.timing import (
    ANCHOR_EXTRACTION_VERSION,
    MOTION_TIMING_VERSION,
    TIMING_BINDING_VERSION,
    annotate_composition_semantics,
    build_timing_bindings,
    extract_semantic_anchors,
    validate_anchors,
    validate_narration_timing,
    validate_timing_bindings,
)
from videotool.pipeline.context import PipelineContext
from videotool.pipeline.fingerprints import STAGE_VERSIONS, stable_hash
from videotool.pipeline.stage import BasePipelineStage, PipelineStage
from videotool.providers.timing import NARRATION_TIMING_VERSION


# ---------------------------------------------------------------------------
# Stage 1: Narration Timing
# ---------------------------------------------------------------------------
class NarrationTimingStage(BasePipelineStage):
    id = "narration_timing"

    def fingerprint(self, ctx: PipelineContext) -> str:
        narration_payload = ctx.narration.to_dict()
        return stable_hash(
            self.version,
            ctx.episode_id,
            narration_payload,
            ctx.timing_provider.provider_id,
            ctx.timing_provider.provider_version,
            NARRATION_TIMING_VERSION,
        )

    def execute(self, ctx: PipelineContext) -> dict:
        return ctx.timing_provider.align(ctx.narration).to_dict()

    def validate(self, payload: Any, ctx: PipelineContext) -> bool:
        try:
            timing = NarrationTiming.from_dict(payload)
        except Exception:
            return False
        return not validate_narration_timing(timing)


# ---------------------------------------------------------------------------
# Stage 2: Semantic Beats
# ---------------------------------------------------------------------------
class SemanticBeatsStage(BasePipelineStage):
    id = "semantic_beats"

    def fingerprint(self, ctx: PipelineContext) -> str:
        semantic_narration_payload = ctx.state["semantic_narration_payload"]
        return stable_hash(self.version, ctx.episode_id, semantic_narration_payload)

    def execute(self, ctx: PipelineContext) -> list[dict]:
        semantic_narration = ctx.state["semantic_narration"]
        beats = ctx.beat_analyzer.analyze(semantic_narration, ctx.episode_id)
        for b in beats:
            if b.semantic_function is None:
                ctx.record_repair(
                    "semantic_beats",
                    f"{b.beat_id}: missing semantic function",
                    "default function assigned (repair)",
                )
        beats = [validation.repair_beat(b) for b in beats]
        kept = [
            b for b in beats
            if validation.validate_beats([b], semantic_narration.duration_sec).ok
        ]
        for dropped in [b for b in beats if b not in kept]:
            ctx.record_repair(
                "semantic_beats", f"{dropped.beat_id} invalid", "dropped beat"
            )
        return [b.to_dict() for b in kept]

    def validate(self, payload: Any, ctx: PipelineContext) -> bool:
        try:
            beats = [SemanticBeat.from_dict(b) for b in payload]
        except Exception:
            return False
        narration_timing: NarrationTiming = ctx.state["narration_timing"]
        word_count = len(narration_timing.words)
        return bool(beats) and all(
            beat.semantic_function is not None
            and beat.narration_text
            and 0 <= beat.word_start < beat.word_end <= word_count
            and beat.end_sec > beat.start_sec
            for beat in beats
        )


# ---------------------------------------------------------------------------
# Stage 3: Semantic Anchors
# ---------------------------------------------------------------------------
class SemanticAnchorsStage(BasePipelineStage):
    id = "semantic_anchors"

    def fingerprint(self, ctx: PipelineContext) -> str:
        return stable_hash(
            self.version,
            ctx.episode_id,
            ctx.state["beats_semantic_hash"],
            ctx.state["timing_hash"],
            ANCHOR_EXTRACTION_VERSION,
        )

    def execute(self, ctx: PipelineContext) -> list[dict]:
        narration_timing: NarrationTiming = ctx.state["narration_timing"]
        beats: list[SemanticBeat] = ctx.state["beats"]
        return [
            anchor.to_dict()
            for anchor in extract_semantic_anchors(narration_timing, beats)
        ]

    def validate(self, payload: Any, ctx: PipelineContext) -> bool:
        try:
            anchors = [SemanticAnchor.from_dict(a) for a in payload]
        except Exception:
            return False
        return not validate_anchors(
            anchors, ctx.state["beats"], ctx.state["narration_timing"]
        )


# ---------------------------------------------------------------------------
# Stage 4: Episode Art Direction
# ---------------------------------------------------------------------------
class EpisodeArtDirectionStage(BasePipelineStage):
    id = "episode_art_direction"

    def fingerprint(self, ctx: PipelineContext) -> str:
        return stable_hash(
            self.version,
            ctx.episode_id,
            ctx.episode.subject,
            ctx.state["semantic_narration_payload"],
            ctx.state["beats_semantic_hash"],
        )

    def execute(self, ctx: PipelineContext) -> dict:
        ad = ctx.art_director.generate(
            ctx.episode_id,
            ctx.episode.subject,
            ctx.state["timed_narration"],
            ctx.state["beats"],
        )
        if not ad.visual_motifs or not ad.accent.get("primary"):
            ctx.record_repair(
                "episode_art_direction",
                "generated identity incomplete",
                "deterministic fallback art direction",
            )
            ad = validation.fallback_art_direction(ctx.episode_id, ctx.episode.subject)
        return ad.to_dict()

    def validate(self, payload: Any, ctx: PipelineContext) -> bool:
        try:
            ad = EpisodeArtDirection.from_dict(payload)
        except Exception:
            return False
        return bool(ad.visual_motifs) and bool(ad.accent.get("primary"))


# ---------------------------------------------------------------------------
# Stage 5: Visual Strategy Plan (Preliminary)
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# Stage 6: Asset Requirements
# ---------------------------------------------------------------------------
class AssetRequirementsStage(BasePipelineStage):
    id = "asset_requirements"

    def fingerprint(self, ctx: PipelineContext) -> str:
        return stable_hash(
            self.version,
            ctx.episode_id,
            ctx.state["beats_semantic_hash"],
        )

    def execute(self, ctx: PipelineContext) -> list[dict]:
        import videotool.pipeline.runner as runner_module
        req_fn = getattr(runner_module, "semantic_asset_requirements", semantic_asset_requirements)
        reqs = req_fn(ctx.state["beats"])
        kept = [r for r in reqs if r.beat_id and r.description]
        if len(kept) != len(reqs):
            ctx.record_repair(
                "asset_requirements", "invalid requirements", "dropped"
            )
        return [r.to_dict() for r in kept]

    def validate(self, payload: Any, ctx: PipelineContext) -> bool:
        beat_ids = {b.beat_id for b in ctx.state["beats"]}
        try:
            reqs = [AssetRequirement.from_dict(r) for r in payload]
        except Exception:
            return False
        return bool(reqs) and all(
            r.beat_id in beat_ids and r.description for r in reqs
        )


# ---------------------------------------------------------------------------
# Stage 7: Media Search Plan
# ---------------------------------------------------------------------------
class MediaSearchPlanStage(BasePipelineStage):
    id = "media_search_plan"

    def fingerprint(self, ctx: PipelineContext) -> str:
        import videotool.editorial.media as media_pkg
        import videotool.pipeline.runner as runner_module
        q_ver = getattr(runner_module, "MEDIA_QUERY_VERSION", getattr(media_pkg, "MEDIA_QUERY_VERSION", MEDIA_QUERY_VERSION))
        return stable_hash(
            self.version,
            ctx.episode_id,
            ctx.state["reqs_hash"],
            ctx.state["beats_semantic_hash"],
            q_ver,
        )

    def execute(self, ctx: PipelineContext) -> list[dict]:
        return [
            p.to_dict()
            for p in plan_search(ctx.state["requirements"], ctx.state["beats"])
        ]

    def validate(self, payload: Any, ctx: PipelineContext) -> bool:
        known = {r.requirement_id for r in ctx.state["requirements"]}
        try:
            plans = [MediaSearchPlan.from_dict(p) for p in payload]
        except Exception:
            return False
        return bool(plans) and all(
            p.requirement_id in known
            and p.primary_query.strip()
            and p.primary_query.lower()
            not in ("historical photo", "war image", "documentary image")
            for p in plans
        )


# ---------------------------------------------------------------------------
# Stage 8: Media Candidates
# ---------------------------------------------------------------------------
class MediaCandidatesStage(BasePipelineStage):
    id = "media_candidates"

    def fingerprint(self, ctx: PipelineContext) -> str:
        media_config = ctx.media_config
        provider = ctx.state["media_provider"]
        return stable_hash(
            self.version,
            ctx.episode_id,
            ctx.state["fp_search_plan"],
            ctx.state["search_plan_hash"],
            media_config.provider,
            provider.provider_version,
            media_config.max_candidates_per_query,
            media_config.timeout_sec,
            media_config.retries,
            ctx.episode.catalog,
        )

    def execute(self, ctx: PipelineContext) -> dict:
        media_config = ctx.media_config
        provider = ctx.state["media_provider"]
        diagnostics: dict[str, list[dict]] = {}
        found = search_candidates(
            ctx.state["media_search_plan"],
            provider,
            media_config.max_candidates_per_query,
            diagnostics=diagnostics,
        )
        return {
            "provider": media_config.provider,
            "by_requirement": {
                rid: [c.to_dict() for c in cands] for rid, cands in found.items()
            },
            "search_diagnostics": diagnostics,
        }

    def validate(self, payload: Any, ctx: PipelineContext) -> bool:
        try:
            cand_map = payload["by_requirement"]
            diagnostics = payload["search_diagnostics"]
            for items in cand_map.values():
                for c in items:
                    candidate = MediaCandidate.from_dict(c)
                    if (
                        not candidate.candidate_id
                        or candidate.provider != payload["provider"]
                        or not candidate.media_url
                    ):
                        return False
        except Exception:
            return False
        known = {p.requirement_id for p in ctx.state["media_search_plan"]}
        return set(cand_map) == known and set(diagnostics) == known


# ---------------------------------------------------------------------------
# Stage 9: Media Acquisition Result
# ---------------------------------------------------------------------------
class MediaAcquisitionResultStage(BasePipelineStage):
    id = "media_acquisition_result"

    def fingerprint(self, ctx: PipelineContext) -> str:
        import videotool.editorial.media as media_pkg
        import videotool.pipeline.runner as runner_module
        ranking_ver = getattr(runner_module, "MEDIA_RANKING_VERSION", getattr(media_pkg, "MEDIA_RANKING_VERSION", MEDIA_RANKING_VERSION))
        license_ver = getattr(runner_module, "LICENSE_POLICY_VERSION", getattr(media_pkg, "LICENSE_POLICY_VERSION", LICENSE_POLICY_VERSION))
        dl_ver = getattr(runner_module, "MEDIA_DOWNLOAD_VERSION", getattr(media_pkg, "MEDIA_DOWNLOAD_VERSION", MEDIA_DOWNLOAD_VERSION))
        cache_ver = getattr(runner_module, "MEDIA_CACHE_VERSION", getattr(media_pkg, "MEDIA_CACHE_VERSION", MEDIA_CACHE_VERSION))
        svc_ver = getattr(runner_module, "ACQUISITION_SERVICE_VERSION", getattr(media_pkg, "ACQUISITION_SERVICE_VERSION", ACQUISITION_SERVICE_VERSION))
        media_config = ctx.media_config
        return stable_hash(
            self.version,
            ctx.episode_id,
            ctx.state["fp_candidates"],
            ctx.state["candidates_hash"],
            ranking_ver,
            license_ver,
            dl_ver,
            cache_ver,
            svc_ver,
            media_config.to_dict(),
            ctx.mode,
        )

    def execute(self, ctx: PipelineContext) -> dict:
        media_config = ctx.media_config
        provider = ctx.state["media_provider"]
        cache = ctx.state["media_cache"]
        service = MediaAcquisitionService(provider, cache, media_config)
        outcome = service.acquire(
            ctx.state["requirements"],
            ctx.state["media_search_plan"],
            ctx.state["media_candidates"],
            mode=ctx.mode,
            search_diagnostics=ctx.state["candidates_payload"]["search_diagnostics"],
        )
        return {
            "assets": [a.to_dict() for a in outcome.assets],
            "traces": [t.to_dict() for t in outcome.traces],
            "attributions": [a.to_dict() for a in outcome.attributions],
        }

    def validate(self, payload: Any, ctx: PipelineContext) -> bool:
        try:
            assets = [MediaAsset.from_dict(a) for a in payload["assets"]]
            traces = [AcquisitionTrace.from_dict(t) for t in payload["traces"]]
        except Exception:
            return False
        known = {r.requirement_id for r in ctx.state["requirements"]}
        return (
            not validate_media_assets(
                assets,
                ctx.state["requirements"],
                ctx.mode,
                ctx.state["media_candidates"],
                ctx.state["media_cache"],
            )
            and len(traces) == len(ctx.state["requirements"])
            and {t.requirement_id for t in traces} == known
        )


# ---------------------------------------------------------------------------
# Stage 10: Media Assets
# ---------------------------------------------------------------------------
class MediaAssetsStage(BasePipelineStage):
    id = "media_assets"

    def fingerprint(self, ctx: PipelineContext) -> str:
        return stable_hash(
            self.version,
            ctx.episode_id,
            ctx.state["fp_acquisition"],
            ctx.state["acquisition_hash"],
        )

    def execute(self, ctx: PipelineContext) -> list[dict]:
        return ctx.state["acquisition_payload"]["assets"]

    def validate(self, payload: Any, ctx: PipelineContext) -> bool:
        try:
            assets = [MediaAsset.from_dict(a) for a in payload]
        except Exception:
            return False
        return not validate_media_assets(
            assets,
            ctx.state["requirements"],
            ctx.mode,
            ctx.state["media_candidates"],
            ctx.state["media_cache"],
        )


# ---------------------------------------------------------------------------
# Stage 11: Media Acquisition Trace
# ---------------------------------------------------------------------------
class MediaAcquisitionTraceStage(BasePipelineStage):
    id = "media_acquisition_trace"

    def fingerprint(self, ctx: PipelineContext) -> str:
        return stable_hash(
            self.version,
            ctx.episode_id,
            ctx.state["fp_acquisition"],
            ctx.state["acquisition_hash"],
            ctx.state["fp_media"],
            ctx.state["media_hash"],
        )

    def execute(self, ctx: PipelineContext) -> list[dict]:
        return ctx.state["acquisition_payload"]["traces"]

    def validate(self, payload: Any, ctx: PipelineContext) -> bool:
        known = {r.requirement_id for r in ctx.state["requirements"]}
        try:
            traces = [AcquisitionTrace.from_dict(t) for t in payload]
        except Exception:
            return False
        return (
            len(traces) == len(ctx.state["requirements"])
            and {t.requirement_id for t in traces} == known
            and all(t.queries_attempted for t in traces)
        )


# ---------------------------------------------------------------------------
# Stage 12: Media Attribution
# ---------------------------------------------------------------------------
class MediaAttributionStage(BasePipelineStage):
    id = "media_attribution"

    def fingerprint(self, ctx: PipelineContext) -> str:
        return stable_hash(self.version, ctx.episode_id, ctx.state["media_hash"])

    def execute(self, ctx: PipelineContext) -> dict:
        entries = []
        for a in ctx.state["assets"]:
            if a.is_placeholder:
                continue
            entries.append({
                "asset_id": a.asset_id,
                "creator": a.attribution.get("creator", ""),
                "source": a.provider or "fixture",
                "source_page": a.source_page,
                "license": a.license_name or a.attribution.get("license_name", ""),
                "license_url": a.attribution.get("license_url", ""),
            })
        return {"assets": entries}

    def validate(self, payload: Any, ctx: PipelineContext) -> bool:
        asset_ids = {a.asset_id for a in ctx.state["assets"]}
        try:
            entries = payload["assets"]
        except Exception:
            return False
        return all(e["asset_id"] in asset_ids for e in entries)


# ---------------------------------------------------------------------------
# Stage 13: Strategy Feasibility (Plan of Record)
# ---------------------------------------------------------------------------
class StrategyFeasibilityStage(BasePipelineStage):
    id = "strategy_feasibility"

    def fingerprint(self, ctx: PipelineContext) -> str:
        return stable_hash(
            self.version,
            ctx.episode_id,
            ctx.state["strategy_hash"],
            ctx.state["media_hash"],
            ctx.mode,
            ctx.planner_config.max_family_streak,
        )

    def execute(self, ctx: PipelineContext) -> dict:
        complete = _repair_strategy_records(
            ctx.state["preliminary_strategy_plan"], ctx.state["beats"], ctx
        )
        result = run_feasibility_pass(
            complete,
            ctx.state["beats"],
            ctx.state["requirements"],
            ctx.state["assets"],
            ctx.planner_config.max_family_streak,
        )
        return {
            "adjustments": result.adjustments,
            "records": [r.to_dict() for r in result.records],
        }

    def validate(self, payload: Any, ctx: PipelineContext) -> bool:
        try:
            records = [
                SelectionRecord.from_dict(r) for r in payload.get("records", [])
            ]
        except Exception:
            return False
        return validation.validate_strategy_plan(records, ctx.state["beats"]).ok


# ---------------------------------------------------------------------------
# Stage 14: Visual Compositions
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# Stage 15: Visual History
# ---------------------------------------------------------------------------
class VisualHistoryStage(BasePipelineStage):
    id = "visual_history"

    def fingerprint(self, ctx: PipelineContext) -> str:
        return stable_hash(
            self.version, ctx.episode_id, ctx.state["comps_hash"]
        )

    def execute(self, ctx: PipelineContext) -> dict:
        return history_from_compositions(ctx.state["compositions"]).to_dict()

    def validate(self, payload: Any, ctx: PipelineContext) -> bool:
        try:
            hist = VisualHistory.from_dict(payload)
        except Exception:
            return False
        return len(hist.entries) == len(ctx.state["compositions"])


# ---------------------------------------------------------------------------
# Stage 16: Timing Bindings
# ---------------------------------------------------------------------------
class TimingBindingsStage(BasePipelineStage):
    id = "timing_bindings"

    def fingerprint(self, ctx: PipelineContext) -> str:
        return stable_hash(
            self.version,
            ctx.episode_id,
            ctx.state["fp_anchors"],
            ctx.state["anchors_hash"],
            ctx.state["comps_hash"],
            TIMING_BINDING_VERSION,
            ctx.timing_policy.to_dict(),
        )

    def execute(self, ctx: PipelineContext) -> list[dict]:
        return [
            binding.to_dict()
            for binding in build_timing_bindings(
                ctx.state["beats"],
                ctx.state["compositions"],
                ctx.state["semantic_anchors"],
                ctx.timing_policy,
            )
        ]

    def validate(self, payload: Any, ctx: PipelineContext) -> bool:
        try:
            bindings = [TimingBinding.from_dict(b) for b in payload]
        except Exception:
            return False
        return not validate_timing_bindings(
            bindings,
            ctx.state["beats"],
            ctx.state["compositions"],
            ctx.state["semantic_anchors"],
        )


# ---------------------------------------------------------------------------
# Stage 17: Semantic Geometry
# ---------------------------------------------------------------------------
class SemanticGeometryStage(BasePipelineStage):
    id = "semantic_geometry"

    def fingerprint(self, ctx: PipelineContext) -> str:
        geometry_projection = geometry_input_projection(
            ctx.state["compositions"],
            ctx.state["assets"],
            ctx.state["strategy_plan"],
            ctx.state["art_direction"],
            ctx.state["semantic_anchors"],
            ctx.state["timing_bindings"],
            ctx.state["requirements"],
        )
        return stable_hash(
            self.version,
            ctx.episode_id,
            ctx.state["beats_semantic_hash"],
            geometry_projection,
            SEMANTIC_GEOMETRY_VERSION,
            GEOMETRY_POLICY_VERSION,
            GEOMETRY_SIGNATURE_VERSION,
            GEOMETRY_SOLVER_VERSION,
            GEOMETRY_CANDIDATE_VERSION,
            GEOMETRY_SCORE_VERSION,
        )

    def execute(self, ctx: PipelineContext) -> list[dict]:
        selection_by_beat = {item.beat_id: item for item in ctx.state["strategy_plan"]}
        composition_by_beat = {item.beat_id: item for item in ctx.state["compositions"]}
        history = GeometryHistory()
        plans: list[GeometryPlan] = []
        for beat in ctx.state["beats"]:
            selection = selection_by_beat[beat.beat_id]
            composition = composition_by_beat.get(beat.beat_id)
            beat_requirements = [
                item for item in ctx.state["requirements"] if item.beat_id == beat.beat_id
            ]
            beat_assets = assets_for_beat(
                ctx.state["assets"], ctx.state["requirements"], beat.beat_id
            )
            beat_anchors = [
                item for item in ctx.state["semantic_anchors"] if item.beat_id == beat.beat_id
            ]
            composition_bindings = [
                item
                for item in ctx.state["timing_bindings"]
                if composition is not None
                and item.composition_id == composition.composition_id
            ]
            try:
                plan = ctx.geometry_builder.build_plan(
                    beat,
                    selection.visual_family,
                    selection.selected_strategy,
                    beat_assets,
                    beat_requirements,
                    ctx.state["art_direction"],
                    beat_anchors,
                    composition,
                    composition_bindings,
                    history.recent(),
                )
                report = validate_geometry_plan(
                    plan, {asset.asset_id for asset in ctx.state["assets"]}
                )
                if not report.ok:
                    raise ValueError("; ".join(report.errors))
            except Exception as exc:
                reason = (
                    f"{composition.beat_id}: semantic geometry raised {type(exc).__name__}"
                )
                ctx.record_repair(
                    "semantic_geometry",
                    reason,
                    "deterministic semantic geometry fallback",
                )
                plan = ctx.geometry_builder.fallback_plan(
                    beat, selection.visual_family, reason, history.recent()
                )
            plans.append(plan)
            history.record(plan.structural_geometry_signature)
        return [plan.to_dict() for plan in plans]

    def validate(self, payload: Any, ctx: PipelineContext) -> bool:
        try:
            plans = [GeometryPlan.from_dict(item) for item in payload]
        except Exception:
            return False
        return validate_geometry_plans(
            plans,
            {beat.beat_id for beat in ctx.state["beats"]},
            {asset.asset_id for asset in ctx.state["assets"]},
        ).ok


# ---------------------------------------------------------------------------
# Stage 18: Motion Plan
# ---------------------------------------------------------------------------
class MotionPlanStage(BasePipelineStage):
    id = "motion_plan"

    def fingerprint(self, ctx: PipelineContext) -> str:
        return stable_hash(
            self.version,
            ctx.episode_id,
            ctx.state["beats_semantic_hash"],
            ctx.state["timing_hash"],
            ctx.state["comps_hash"],
            ctx.state["anchors_hash"],
            ctx.state["fp_bindings"],
            ctx.state["bindings_hash"],
            MOTION_TIMING_VERSION,
            ctx.timing_policy.to_dict(),
        )

    def execute(self, ctx: PipelineContext) -> dict:
        return build_motion_plan(
            ctx.episode_id,
            ctx.state["beats"],
            ctx.state["compositions"],
            ctx.state["semantic_anchors"],
            ctx.state["timing_bindings"],
            ctx.timing_policy,
        ).to_dict()

    def validate(self, payload: Any, ctx: PipelineContext) -> bool:
        try:
            motion = MotionPlan.from_dict(payload)
        except Exception:
            return False
        return validation.validate_motion(
            motion,
            ctx.state["beats"],
            ctx.state["compositions"],
            ctx.state["semantic_anchors"],
            ctx.state["timing_bindings"],
        ).ok


# ---------------------------------------------------------------------------
# Stage 19: Timeline
# ---------------------------------------------------------------------------
class TimelineStage(BasePipelineStage):
    id = "timeline"

    def fingerprint(self, ctx: PipelineContext) -> str:
        return stable_hash(
            self.version,
            ctx.episode_id,
            ctx.state["timing_hash"],
            ctx.state["beats_semantic_hash"],
            ctx.state["comps_hash"],
            ctx.state["fp_motion"],
            ctx.state["motion_hash"],
        )

    def execute(self, ctx: PipelineContext) -> dict:
        return build_timeline(
            ctx.episode_id,
            ctx.state["timed_narration"],
            ctx.state["beats"],
            ctx.state["compositions"],
            ctx.state["motion"],
            ctx.state["narration_timing"],
        )

    def validate(self, payload: Any, ctx: PipelineContext) -> bool:
        if not isinstance(payload, dict) or not payload.get("segments"):
            return False
        return validation.validate_timeline(
            payload, ctx.state["beats"], ctx.state["compositions"], ctx.mode
        ).ok


# ---------------------------------------------------------------------------
# Helper repair functions
# ---------------------------------------------------------------------------
def _default_strategy(
    beat: SemanticBeat | None, rec: SelectionRecord | None
) -> str:
    from videotool.domain.semantic_beat import SemanticFunction
    from videotool.editorial.strategies import FUNCTION_CANDIDATES

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


# ---------------------------------------------------------------------------
# Stage Registry
# ---------------------------------------------------------------------------
class StageRegistry:
    """Registry maintaining the canonical ordered sequence of pipeline stages."""

    def __init__(self):
        self._stages: list[PipelineStage] = [
            NarrationTimingStage(),
            SemanticBeatsStage(),
            SemanticAnchorsStage(),
            EpisodeArtDirectionStage(),
            VisualStrategyPlanStage(),
            AssetRequirementsStage(),
            MediaSearchPlanStage(),
            MediaCandidatesStage(),
            MediaAcquisitionResultStage(),
            MediaAssetsStage(),
            MediaAcquisitionTraceStage(),
            MediaAttributionStage(),
            StrategyFeasibilityStage(),
            VisualCompositionsStage(),
            VisualHistoryStage(),
            TimingBindingsStage(),
            SemanticGeometryStage(),
            MotionPlanStage(),
            TimelineStage(),
        ]

    def all_stages(self) -> list[PipelineStage]:
        return list(self._stages)

    def get_stage(self, stage_id: str) -> PipelineStage | None:
        for s in self._stages:
            if s.id == stage_id:
                return s
        return None
