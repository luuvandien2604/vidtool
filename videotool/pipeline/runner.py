"""Pipeline orchestration with integrity-checked resume (Phase 1.2 & Hardened 2F).

Stage order:
  narration_timing -> semantic_beats -> semantic_anchors ->
  episode_art_direction -> visual_strategy_plan -> asset_requirements ->
  media_search_plan -> media_candidates -> media_acquisition_result ->
  media_assets -> media_acquisition_trace -> media_attribution ->
  strategy_feasibility -> visual_compositions -> visual_history ->
  timing_bindings -> semantic_geometry -> motion_plan -> timeline

Hardening guarantees:
* Integrity-checked resume. stage_meta.json stores, per stage:
  {input_fingerprint, output_hash, stage_version}. Resuming requires ALL of:
  input fingerprint match -> artifact loads -> output hash matches ->
  deserializes -> stage validator passes. Valid-JSON corruption cannot
  silently resume; any failure recomputes the stage (downstream follows).
* Completeness gates: every beat has exactly one composition; final mode
  never passes with REQUIRED media unresolved for the plan-of-record
  (Media Completeness Gate); motion/timeline validated structurally.
* Execution mode has ONE source of truth: PipelineRunner.mode.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from videotool.ai.heuristic import HeuristicArtDirector, HeuristicBeatAnalyzer
from videotool.artifacts import ArtifactStore
from videotool.domain.art_direction import EpisodeArtDirection
from videotool.domain.assets import AssetRequirement, MediaAsset
from videotool.domain.composition import VisualComposition
from videotool.domain.geometry import GeometryPlan
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
    SemanticGeometryBuilder,
    validate_geometry_plans,
)
from videotool.editorial.media import (
    AcquisitionTrace,
    MediaAcquisitionConfig,
    MediaAcquisitionService,
    MediaCandidate,
    MediaCache,
    MediaSearchPlan,
    plan_search,
    search_candidates,
)
from videotool.editorial.motion import build_motion_plan
from videotool.editorial.strategies import (
    FUNCTION_CANDIDATES,
    STRATEGY_CATALOG,
    PlanningConfig,
    StrategyPlanner,
)
from videotool.editorial.timeline import build_timeline
from videotool.editorial.timing import (
    EditorialTimingPolicy,
    build_timing_bindings,
    extract_semantic_anchors,
    validate_anchors,
    validate_narration_timing,
    validate_timing_bindings,
)
from videotool.pipeline.context import EpisodeInput, PipelineContext
from videotool.pipeline.executor import StageExecutor
from videotool.pipeline.fingerprints import STAGE_VERSIONS, stable_hash
from videotool.pipeline.policy import ExecutionPolicy
from videotool.pipeline.registry import StageRegistry
from videotool.providers.media import build_provider
from videotool.providers.timing import DeterministicNarrationTimingProvider

STAGES = [
    "narration_timing",
    "semantic_beats",
    "semantic_anchors",
    "episode_art_direction",
    "visual_strategy_plan",
    "asset_requirements",
    "media_search_plan",
    "media_candidates",
    "media_acquisition_result",
    "media_assets",
    "media_acquisition_trace",
    "media_attribution",
    "strategy_feasibility",
    "visual_compositions",
    "visual_history",
    "timing_bindings",
    "semantic_geometry",
    "motion_plan",
    "timeline",
]


@dataclass
class PipelineResult:
    episode_id: str
    manifest: dict
    narration_timing: NarrationTiming | None = None
    beats: list[SemanticBeat] = field(default_factory=list)
    semantic_anchors: list[SemanticAnchor] = field(default_factory=list)
    art_direction: EpisodeArtDirection | None = None
    strategy_plan: list[SelectionRecord] = field(default_factory=list)  # plan-of-record
    preliminary_strategy_plan: list[SelectionRecord] = field(default_factory=list)
    feasibility: dict = field(default_factory=dict)
    requirements: list[AssetRequirement] = field(default_factory=list)
    media_search_plan: list = field(default_factory=list)
    media_candidates: dict = field(default_factory=dict)
    media_acquisition_result: dict = field(default_factory=dict)
    assets: list[MediaAsset] = field(default_factory=list)
    media_acquisition_trace: list[AcquisitionTrace] = field(default_factory=list)
    media_attribution: dict = field(default_factory=dict)
    compositions: list[VisualComposition] = field(default_factory=list)
    history: VisualHistory | None = None
    timing_bindings: list[TimingBinding] = field(default_factory=list)
    geometry_plans: list[GeometryPlan] = field(default_factory=list)
    motion: MotionPlan | None = None
    timeline: dict = field(default_factory=dict)
    ok: bool = True
    validation: dict = field(default_factory=dict)


class PipelineRunner:
    """Orchestrates pipeline execution, state machine, and artifact storage."""

    def __init__(
        self,
        store: ArtifactStore,
        mode: str = "final",
        force: bool = False,
        policy: ExecutionPolicy | None = None,
        planner_config: PlanningConfig | None = None,
        media_config: MediaAcquisitionConfig | None = None,
        timing_provider: Any | None = None,
        timing_policy: EditorialTimingPolicy | None = None,
    ):
        self.store = store
        self.policy = policy or ExecutionPolicy(
            mode=mode,
            force=force,
            max_family_streak=planner_config.max_family_streak if planner_config else 2,
        )
        self.planner_config = planner_config or PlanningConfig(
            max_family_streak=self.policy.max_family_streak
        )
        self.beat_analyzer = HeuristicBeatAnalyzer()
        self.art_director = HeuristicArtDirector()
        self.planner = StrategyPlanner(self.planner_config)
        self._media_config_override = media_config
        self.timing_provider = (
            timing_provider or DeterministicNarrationTimingProvider()
        )
        self.timing_policy = timing_policy or EditorialTimingPolicy()
        self.geometry_builder = SemanticGeometryBuilder()

        self.registry = StageRegistry()
        self.executor = StageExecutor()

        # Run logging
        self._meta: dict = {}
        self._statuses: dict = {}
        self._repairs: list[dict] = []

    @property
    def mode(self) -> str:
        return self.policy.mode

    @mode.setter
    def mode(self, val: str) -> None:
        self.policy = ExecutionPolicy(
            mode=val,
            force=self.policy.force,
            max_family_streak=self.policy.max_family_streak,
            cache_enabled=self.policy.cache_enabled,
        )

    @property
    def force(self) -> bool:
        return self.policy.force

    @force.setter
    def force(self, val: bool) -> None:
        self.policy = ExecutionPolicy(
            mode=self.policy.mode,
            force=val,
            max_family_streak=self.policy.max_family_streak,
            cache_enabled=self.policy.cache_enabled,
        )

    def _media_config(self, ep: EpisodeInput) -> MediaAcquisitionConfig:
        cfg = self._media_config_override or MediaAcquisitionConfig()
        if cfg.provider == "fixture" and ep.catalog:
            cfg = MediaAcquisitionConfig(**{**cfg.to_dict(), "provider": "fixture"})
        return cfg

    def _build_media_provider(self, ep: EpisodeInput, cfg: MediaAcquisitionConfig):
        if cfg.provider == "fixture":
            return build_provider("fixture", catalog=ep.catalog)
        return build_provider(
            cfg.provider,
            timeout_sec=cfg.timeout_sec,
            retries=cfg.retries,
            user_agent=cfg.user_agent,
        )

    def _repair_log(self, stage: str, issue: str, action: str) -> None:
        self._repairs.append({"stage": stage, "issue": issue, "action": action})

    def run(self, ep: EpisodeInput) -> PipelineResult:
        res = PipelineResult(
            episode_id=ep.episode_id,
            manifest={"stages": {}, "repairs": []},
        )
        self._meta, self._statuses, self._repairs = {}, {}, []

        # Construct execution context
        ctx = PipelineContext(
            episode=ep,
            store=self.store,
            policy=self.policy,
            planner_config=self.planner_config,
            media_config=self._media_config(ep),
            timing_provider=self.timing_provider,
            timing_policy=self.timing_policy,
            beat_analyzer=self.beat_analyzer,
            art_director=self.art_director,
            planner=self.planner,
            geometry_builder=self.geometry_builder,
        )

        media_config = ctx.media_config
        ctx.state["media_provider"] = self._build_media_provider(ep, media_config)
        ctx.state["media_cache"] = MediaCache(
            media_config.cache_dir or (self.store.root / "media_cache")
        )

        # 1. Narration Timing Stage
        timing_stage = self.registry.get_stage("narration_timing")
        timing_payload = self.executor.execute_stage(timing_stage, ctx)
        res.narration_timing = NarrationTiming.from_dict(timing_payload)
        ctx.state["narration_timing"] = res.narration_timing
        ctx.state["timing_hash"] = stable_hash(timing_payload)

        timed_narration = Narration(
            text=ep.narration.text,
            words=res.narration_timing.words,
            language=ep.narration.language,
        )
        ctx.state["timed_narration"] = timed_narration
        self.store.save(ep.episode_id, "narration", ep.narration.to_dict())

        semantic_narration_payload = {
            "text": ep.narration.text,
            "language": ep.narration.language,
            "words": [word.text for word in res.narration_timing.words],
        }
        ctx.state["semantic_narration_payload"] = semantic_narration_payload
        ctx.state["semantic_narration"] = Narration(
            text=ep.narration.text,
            words=synthetic_word_timings(
                " ".join(semantic_narration_payload["words"])
            ),
            language=ep.narration.language,
        )

        # 2. Semantic Beats Stage
        beats_stage = self.registry.get_stage("semantic_beats")
        beats_payload = self.executor.execute_stage(beats_stage, ctx)
        res.beats = [SemanticBeat.from_dict(b) for b in beats_payload]
        for beat in res.beats:
            beat.start_sec = res.narration_timing.words[beat.word_start].start_sec
            beat.end_sec = res.narration_timing.words[beat.word_end - 1].end_sec
        ctx.state["beats"] = res.beats
        ctx.state["beats_semantic_hash"] = stable_hash(
            SEMANTIC_BEAT_IDENTITY_VERSION, semantic_beats_identity(res.beats)
        )

        # 3. Semantic Anchors Stage
        anchors_stage = self.registry.get_stage("semantic_anchors")
        anchors_payload = self.executor.execute_stage(anchors_stage, ctx)
        res.semantic_anchors = [SemanticAnchor.from_dict(a) for a in anchors_payload]
        ctx.state["semantic_anchors"] = res.semantic_anchors
        ctx.state["anchors_hash"] = stable_hash(anchors_payload)
        ctx.state["fp_anchors"] = anchors_stage.fingerprint(ctx)

        # 4. Episode Art Direction Stage
        art_stage = self.registry.get_stage("episode_art_direction")
        art_payload = self.executor.execute_stage(art_stage, ctx)
        res.art_direction = EpisodeArtDirection.from_dict(art_payload)
        ctx.state["art_direction"] = res.art_direction
        ctx.state["art_hash"] = stable_hash(art_payload)

        # 5. Visual Strategy Plan (Preliminary)
        strategy_stage = self.registry.get_stage("visual_strategy_plan")
        strategy_payload = self.executor.execute_stage(strategy_stage, ctx)
        res.preliminary_strategy_plan = [
            SelectionRecord.from_dict(r) for r in strategy_payload
        ]
        ctx.state["preliminary_strategy_plan"] = res.preliminary_strategy_plan
        ctx.state["strategy_hash"] = stable_hash(strategy_payload)

        # 6. Asset Requirements Stage
        reqs_stage = self.registry.get_stage("asset_requirements")
        reqs_payload = self.executor.execute_stage(reqs_stage, ctx)
        res.requirements = [AssetRequirement.from_dict(r) for r in reqs_payload]
        ctx.state["requirements"] = res.requirements
        ctx.state["reqs_hash"] = stable_hash(reqs_payload)

        # 7. Media Search Plan Stage
        search_plan_stage = self.registry.get_stage("media_search_plan")
        search_plan_payload = self.executor.execute_stage(search_plan_stage, ctx)
        res.media_search_plan = [
            MediaSearchPlan.from_dict(p) for p in search_plan_payload
        ]
        ctx.state["media_search_plan"] = res.media_search_plan
        ctx.state["search_plan_hash"] = stable_hash(search_plan_payload)
        ctx.state["fp_search_plan"] = search_plan_stage.fingerprint(ctx)

        # 8. Media Candidates Stage
        candidates_stage = self.registry.get_stage("media_candidates")
        candidates_payload = self.executor.execute_stage(candidates_stage, ctx)
        res.media_candidates = {
            rid: [MediaCandidate.from_dict(c) for c in items]
            for rid, items in candidates_payload["by_requirement"].items()
        }
        ctx.state["media_candidates"] = res.media_candidates
        ctx.state["candidates_payload"] = candidates_payload
        ctx.state["candidates_hash"] = stable_hash(candidates_payload)
        ctx.state["fp_candidates"] = candidates_stage.fingerprint(ctx)

        # 9. Media Acquisition Result Stage
        acquisition_stage = self.registry.get_stage("media_acquisition_result")
        acquisition_payload = self.executor.execute_stage(acquisition_stage, ctx)
        ctx.state["acquisition_payload"] = acquisition_payload
        ctx.state["acquisition_hash"] = stable_hash(acquisition_payload)
        ctx.state["fp_acquisition"] = acquisition_stage.fingerprint(ctx)

        # 10. Media Assets Stage
        media_stage = self.registry.get_stage("media_assets")
        media_payload = self.executor.execute_stage(media_stage, ctx)
        res.assets = [MediaAsset.from_dict(a) for a in media_payload]
        ctx.state["assets"] = res.assets
        ctx.state["media_hash"] = stable_hash(media_payload)
        ctx.state["fp_media"] = media_stage.fingerprint(ctx)

        # 11. Media Acquisition Trace Stage
        trace_stage = self.registry.get_stage("media_acquisition_trace")
        trace_payload = self.executor.execute_stage(trace_stage, ctx)
        res.acquisition_traces = [
            AcquisitionTrace.from_dict(t) for t in trace_payload
        ]
        ctx.state["acquisition_traces"] = res.acquisition_traces

        # 12. Media Attribution Stage
        attr_stage = self.registry.get_stage("media_attribution")
        self.executor.execute_stage(attr_stage, ctx)

        # 13. Strategy Feasibility Stage
        feas_stage = self.registry.get_stage("strategy_feasibility")
        feas_payload = self.executor.execute_stage(feas_stage, ctx)
        res.strategy_plan = [
            SelectionRecord.from_dict(r) for r in feas_payload["records"]
        ]
        res.feasibility = {"adjustments": feas_payload.get("adjustments", [])}
        ctx.state["strategy_plan"] = res.strategy_plan
        ctx.state["feasibility"] = res.feasibility
        ctx.state["plan_hash"] = stable_hash(feas_payload)

        # 14. Visual Compositions Stage
        comps_stage = self.registry.get_stage("visual_compositions")
        comps_payload = self.executor.execute_stage(comps_stage, ctx)
        res.compositions = [VisualComposition.from_dict(c) for c in comps_payload]
        ctx.state["compositions"] = res.compositions
        ctx.state["comps_hash"] = stable_hash(comps_payload)

        # 15. Visual History Stage
        hist_stage = self.registry.get_stage("visual_history")
        hist_payload = self.executor.execute_stage(hist_stage, ctx)
        res.history = VisualHistory.from_dict(hist_payload)
        ctx.state["history"] = res.history

        # 16. Timing Bindings Stage
        bindings_stage = self.registry.get_stage("timing_bindings")
        bindings_payload = self.executor.execute_stage(bindings_stage, ctx)
        res.timing_bindings = [
            TimingBinding.from_dict(binding) for binding in bindings_payload
        ]
        ctx.state["timing_bindings"] = res.timing_bindings
        ctx.state["bindings_hash"] = stable_hash(bindings_payload)
        ctx.state["fp_bindings"] = bindings_stage.fingerprint(ctx)

        # 17. Semantic Geometry Stage
        geometry_stage = self.registry.get_stage("semantic_geometry")
        geometry_payload = self.executor.execute_stage(geometry_stage, ctx)
        res.geometry_plans = [
            GeometryPlan.from_dict(item) for item in geometry_payload
        ]
        ctx.state["geometry_plans"] = res.geometry_plans

        # 18. Motion Plan Stage
        motion_stage = self.registry.get_stage("motion_plan")
        motion_payload = self.executor.execute_stage(motion_stage, ctx)
        res.motion = MotionPlan.from_dict(motion_payload)
        ctx.state["motion"] = res.motion
        ctx.state["motion_hash"] = stable_hash(motion_payload)
        ctx.state["fp_motion"] = motion_stage.fingerprint(ctx)

        # 19. Timeline Stage
        timeline_stage = self.registry.get_stage("timeline")
        timeline_payload = self.executor.execute_stage(timeline_stage, ctx)
        res.timeline = timeline_payload
        ctx.state["timeline"] = res.timeline

        # 20. Editorial QC Validation Gate
        timing_errors = validate_narration_timing(res.narration_timing)
        anchor_errors = validate_anchors(
            res.semantic_anchors, res.beats, res.narration_timing
        )
        binding_errors = validate_timing_bindings(
            res.timing_bindings, res.beats, res.compositions, res.semantic_anchors
        )
        geometry_report = validate_geometry_plans(
            res.geometry_plans,
            {beat.beat_id for beat in res.beats},
            {asset.asset_id for asset in res.assets},
        )
        beats_report = validation.validate_beats(
            res.beats, res.narration_timing.duration_sec
        )
        comps_report = validation.validate_compositions(
            res.compositions,
            res.beats,
            res.assets,
            mode=self.mode,
            allow_timing_independent_duration=True,
        )
        plan_report = validation.validate_strategy_plan(res.strategy_plan, res.beats)
        motion_report = validation.validate_motion(
            res.motion,
            res.beats,
            res.compositions,
            res.semantic_anchors,
            res.timing_bindings,
        )
        timeline_report = validation.validate_timeline(
            res.timeline, res.beats, res.compositions, self.mode
        )
        media_report = validation.validate_media_completeness(
            res.beats, res.requirements, res.assets, res.strategy_plan, self.mode
        )

        res.validation = {
            "narration_timing": {
                "ok": not timing_errors,
                "errors": timing_errors,
                "warnings": [],
            },
            "semantic_anchors": {
                "ok": not anchor_errors,
                "errors": anchor_errors,
                "warnings": [],
            },
            "timing_bindings": {
                "ok": not binding_errors,
                "errors": binding_errors,
                "warnings": [],
            },
            "semantic_geometry": {
                "ok": geometry_report.ok,
                "errors": geometry_report.errors,
                "warnings": geometry_report.warnings,
            },
            "beats": {
                "ok": beats_report.ok,
                "errors": beats_report.errors,
                "warnings": beats_report.warnings,
            },
            "compositions": {
                "ok": comps_report.ok,
                "errors": comps_report.errors,
                "warnings": comps_report.warnings,
            },
            "strategy_plan": {
                "ok": plan_report.ok,
                "errors": plan_report.errors,
                "warnings": plan_report.warnings,
            },
            "motion_plan": {
                "ok": motion_report.ok,
                "errors": motion_report.errors,
                "warnings": motion_report.warnings,
            },
            "timeline": {
                "ok": timeline_report.ok,
                "errors": timeline_report.errors,
                "warnings": timeline_report.warnings,
            },
            "media_completeness": {
                "ok": media_report.ok,
                "errors": media_report.errors,
                "warnings": media_report.warnings,
            },
        }
        res.ok = all(v["ok"] for v in res.validation.values())

        # Populate statuses and repairs from context
        self._statuses = dict(ctx._statuses)
        self._repairs = list(ctx._repairs)
        res.manifest["stages"] = self._statuses
        res.manifest["repairs"] = self._repairs
        res.manifest["feasibility"] = res.feasibility["adjustments"]
        res.manifest["ok"] = res.ok
        self.store.save(ep.episode_id, "pipeline_manifest", res.manifest)
        return res
