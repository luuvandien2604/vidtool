"""Pipeline orchestration with integrity-checked resume (Phase 1.2).

Stage order:
  semantic_beats -> episode_art_direction -> visual_strategy_plan ->
  asset_requirements -> media_assets -> strategy_feasibility ->
  visual_compositions -> visual_history -> motion_plan -> timeline

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

from dataclasses import asdict, dataclass, field

from videotool.ai.heuristic import HeuristicArtDirector, HeuristicBeatAnalyzer
from videotool.artifacts import ArtifactStore
from videotool.domain.art_direction import EpisodeArtDirection
from videotool.domain.assets import AssetRequirement, MediaAsset
from videotool.domain.composition import VisualComposition
from videotool.domain.motion import MotionPlan
from videotool.domain.narration import Narration
from videotool.domain.semantic_beat import SemanticBeat
from videotool.domain.strategy import SelectionRecord
from videotool.domain.visual_history import VisualHistory
from videotool.editorial import validation
from videotool.editorial.composition import (FAMILIES_VERSION, assets_for_beat,
                                             compose_beat,
                                             history_from_compositions,
                                             semantic_asset_requirements)
from videotool.editorial.feasibility import run_feasibility_pass
from videotool.editorial.media import (AcquisitionTrace, MediaAcquisitionConfig,
                                       MediaCandidate, MediaSearchPlan)
from videotool.editorial.motion import build_motion_plan
from videotool.editorial.strategies import (FUNCTION_CANDIDATES, STRATEGY_CATALOG,
                                             PlanningConfig, StrategyPlanner)
from videotool.editorial.timeline import build_timeline
from videotool.pipeline.fingerprints import STAGE_VERSIONS, stable_hash
from videotool.providers.media import build_provider

STAGES = ["semantic_beats", "episode_art_direction", "visual_strategy_plan",
          "asset_requirements", "media_search_plan", "media_candidates",
          "media_assets", "media_acquisition_trace", "media_attribution",
          "strategy_feasibility", "visual_compositions", "visual_history",
          "motion_plan", "timeline"]


@dataclass
class EpisodeInput:
    episode_id: str
    subject: str
    narration: Narration
    catalog: list[dict] = field(default_factory=list)
    # NOTE: execution mode (draft/final) is owned by PipelineRunner, the
    # single source of truth. EpisodeInput carries episode DATA only.


@dataclass
class PipelineResult:
    episode_id: str
    manifest: dict
    beats: list[SemanticBeat] = field(default_factory=list)
    art_direction: EpisodeArtDirection | None = None
    strategy_plan: list[SelectionRecord] = field(default_factory=list)   # plan-of-record (post-feasibility)
    preliminary_strategy_plan: list[SelectionRecord] = field(default_factory=list)
    feasibility: dict = field(default_factory=dict)
    requirements: list[AssetRequirement] = field(default_factory=list)
    media_search_plan: list = field(default_factory=list)
    media_candidates: dict = field(default_factory=dict)
    assets: list[MediaAsset] = field(default_factory=list)
    acquisition_traces: list = field(default_factory=list)
    compositions: list[VisualComposition] = field(default_factory=list)
    history: VisualHistory | None = None
    motion: MotionPlan | None = None
    timeline: dict | None = None
    validation: dict = field(default_factory=dict)
    ok: bool = False


class PipelineRunner:
    def __init__(self, store: ArtifactStore, mode: str = "final",
                 force: bool = False, planner_config: PlanningConfig | None = None,
                 media_config: MediaAcquisitionConfig | None = None):
        self.store = store
        self.mode = mode            # single source of truth for draft/final
        self.force = force
        self.planner_config = planner_config or PlanningConfig()
        self.beat_analyzer = HeuristicBeatAnalyzer()
        self.art_director = HeuristicArtDirector()
        self.planner = StrategyPlanner(self.planner_config)
        self._media_config_override = media_config
        # per-run state
        self._meta: dict = {}
        self._statuses: dict = {}
        self._repairs: list[dict] = []
        self._last_acquisition = None

    # ---- media plumbing ---------------------------------------------------
    def _media_config(self, ep: EpisodeInput) -> MediaAcquisitionConfig:
        """Config resolution: explicit override wins; catalog rides along as
        provider data for the fixture provider."""
        cfg = self._media_config_override or MediaAcquisitionConfig()
        if cfg.provider == "fixture" and ep.catalog:
            # keep catalog isolated to the provider; never fingerprint-scattered
            cfg = MediaAcquisitionConfig(**{**cfg.to_dict(),
                                            "provider": "fixture"})
        return cfg

    def _build_media_provider(self, ep: EpisodeInput,
                              cfg: MediaAcquisitionConfig):
        if cfg.provider == "fixture":
            return build_provider("fixture", catalog=ep.catalog)
        return build_provider(cfg.provider, timeout_sec=cfg.timeout_sec,
                              retries=cfg.retries, user_agent=cfg.user_agent)

    # ---- stage plumbing --------------------------------------------------
    def _load_meta(self, ep: EpisodeInput) -> dict:
        if not self._meta:
            loaded = self.store.load(ep.episode_id, "stage_meta")
            self._meta = dict(loaded) if isinstance(loaded, dict) else {}
        return self._meta

    def _record(self, name: str, status: str, fingerprint: str) -> None:
        self._statuses[name] = {"status": status, "fingerprint": fingerprint}

    def _repair_log(self, stage: str, issue: str, action: str) -> None:
        self._repairs.append({"stage": stage, "issue": issue, "action": action})

    def _stage(self, ep: EpisodeInput, name: str, fingerprint: str, compute,
               resume_valid=None):
        """Integrity-checked resume (Phase 1.2).

        Resume requires: input fingerprint match -> artifact loads ->
        output hash matches -> resume validator passes. Any failure
        recomputes the stage and overwrites its metadata.
        """
        meta = self._load_meta(ep)
        prior = meta.get(name)
        if (not self.force and isinstance(prior, dict)
                and prior.get("input_fingerprint") == fingerprint
                and prior.get("stage_version") == STAGE_VERSIONS.get(name)):
            payload = self.store.load(ep.episode_id, name)
            if payload is not None and stable_hash(payload) == prior.get("output_hash"):
                try:
                    valid = resume_valid is None or resume_valid(payload)
                except Exception:
                    valid = False
                if valid:
                    self._record(name, "resumed", fingerprint)
                    return payload
        status = "invalidated" if (prior is not None and not self.force) else "computed"
        payload = compute()
        self.store.save(ep.episode_id, name, payload)
        meta[name] = {
            "input_fingerprint": fingerprint,
            "output_hash": stable_hash(payload),
            "stage_version": STAGE_VERSIONS.get(name, 1),
        }
        self.store.save(ep.episode_id, "stage_meta", meta)
        self._record(name, status, fingerprint)
        return payload

    # ---- entry -------------------------------------------------------------
    def run(self, ep: EpisodeInput) -> PipelineResult:
        res = PipelineResult(episode_id=ep.episode_id,
                             manifest={"stages": {}, "repairs": []})
        self._meta, self._statuses, self._repairs = {}, {}, []
        self._last_acquisition = None

        narration_payload = ep.narration.to_dict()
        planner_cfg = asdict(self.planner_config)

        # 1. semantic beats -------------------------------------------------
        def beats_ok(payload) -> bool:
            try:
                beats = [SemanticBeat.from_dict(b) for b in payload]
            except Exception:
                return False
            return bool(beats) and validation.validate_beats(
                beats, ep.narration.duration_sec).ok

        def compute_beats():
            beats = self.beat_analyzer.analyze(ep.narration, ep.episode_id)
            for b in beats:
                if b.semantic_function is None:
                    self._repair_log("semantic_beats",
                                     f"{b.beat_id}: missing semantic function",
                                     "default function assigned (repair)")
            beats = [validation.repair_beat(b) for b in beats]
            kept = [b for b in beats
                    if validation.validate_beats([b], ep.narration.duration_sec).ok]
            for dropped in [b for b in beats if b not in kept]:
                self._repair_log("semantic_beats", f"{dropped.beat_id} invalid",
                                 "dropped beat")
            return [b.to_dict() for b in kept]

        fp_beats = stable_hash(STAGE_VERSIONS["semantic_beats"], ep.episode_id,
                               narration_payload)
        beats_payload = self._stage(ep, "semantic_beats", fp_beats, compute_beats,
                                    resume_valid=beats_ok)
        res.beats = [SemanticBeat.from_dict(b) for b in beats_payload]
        beats_hash = stable_hash(beats_payload)

        # 2. art direction ------------------------------------------------------
        def art_ok(payload) -> bool:
            try:
                ad = EpisodeArtDirection.from_dict(payload)
            except Exception:
                return False
            return bool(ad.visual_motifs) and bool(ad.accent.get("primary"))

        def compute_art():
            ad = self.art_director.generate(ep.episode_id, ep.subject,
                                            ep.narration, res.beats)
            if not ad.visual_motifs or not ad.accent.get("primary"):
                self._repair_log("episode_art_direction",
                                 "generated identity incomplete",
                                 "deterministic fallback art direction")
                ad = validation.fallback_art_direction(ep.episode_id, ep.subject)
            return ad.to_dict()

        fp_art = stable_hash(STAGE_VERSIONS["episode_art_direction"], ep.episode_id,
                             ep.subject, narration_payload, beats_hash)
        art_payload = self._stage(ep, "episode_art_direction", fp_art, compute_art,
                                  resume_valid=art_ok)
        res.art_direction = EpisodeArtDirection.from_dict(art_payload)
        art_hash = stable_hash(art_payload)

        # 3. preliminary strategy plan (intent; feasibility pass adjusts later) --
        def strategy_ok(payload) -> bool:
            try:
                records = [SelectionRecord.from_dict(r) for r in payload]
            except Exception:
                return False
            return validation.validate_strategy_plan(records, res.beats).ok

        def compute_strategy():
            records = self.planner.select(res.beats, VisualHistory())
            records = self._repair_strategy_records(records, res.beats)
            return [r.to_dict() for r in records]

        fp_strategy = stable_hash(STAGE_VERSIONS["visual_strategy_plan"],
                                  ep.episode_id, beats_hash, planner_cfg)
        strategy_payload = self._stage(ep, "visual_strategy_plan", fp_strategy,
                                       compute_strategy, resume_valid=strategy_ok)
        res.preliminary_strategy_plan = [SelectionRecord.from_dict(r)
                                         for r in strategy_payload]
        strategy_hash = stable_hash(strategy_payload)

        # 4. asset requirements -------------------------------------------------
        def reqs_ok(payload) -> bool:
            beat_ids = {b.beat_id for b in res.beats}
            try:
                reqs = [AssetRequirement.from_dict(r) for r in payload]
            except Exception:
                return False
            return bool(reqs) and all(r.beat_id in beat_ids and r.description
                                      for r in reqs)

        def compute_requirements():
            reqs = semantic_asset_requirements(res.beats)
            kept = [r for r in reqs if r.beat_id and r.description]
            if len(kept) != len(reqs):
                self._repair_log("asset_requirements", "invalid requirements",
                                 "dropped")
            return [r.to_dict() for r in kept]

        fp_reqs = stable_hash(STAGE_VERSIONS["asset_requirements"], ep.episode_id,
                              beats_hash)
        reqs_payload = self._stage(ep, "asset_requirements", fp_reqs,
                                   compute_requirements, resume_valid=reqs_ok)
        res.requirements = [AssetRequirement.from_dict(r) for r in reqs_payload]
        reqs_hash = stable_hash(reqs_payload)

        # 5. media acquisition ---------------------------------------------------
        def media_ok(payload) -> bool:
            try:
                assets = [MediaAsset.from_dict(a) for a in payload]
            except Exception:
                return False
            return all(a.asset_id for a in assets)

        # 5a. media search plan (deterministic, semantic) ------------------------
        from videotool.editorial.media import (LICENSE_POLICY_VERSION,
                                               MEDIA_QUERY_VERSION,
                                               MEDIA_RANKING_VERSION,
                                               MEDIA_DOWNLOAD_VERSION,
                                               ACQUISITION_SERVICE_VERSION)
        from videotool.editorial.media import (MediaAcquisitionConfig,
                                               MediaAcquisitionService,
                                               MediaCache, plan_search,
                                               search_candidates)

        def search_plan_ok(payload) -> bool:
            known = {r.requirement_id for r in res.requirements}
            try:
                plans = [MediaSearchPlan.from_dict(p) for p in payload]
            except Exception:
                return False
            return bool(plans) and all(
                p.requirement_id in known and p.primary_query.strip()
                and p.primary_query.lower() not in
                ("historical photo", "war image", "documentary image")
                for p in plans)

        def compute_search_plan():
            return [p.to_dict() for p in
                    plan_search(res.requirements, res.beats)]

        fp_search_plan = stable_hash(STAGE_VERSIONS["media_search_plan"],
                                     ep.episode_id, reqs_hash, beats_hash,
                                     MEDIA_QUERY_VERSION)
        search_plan_payload = self._stage(ep, "media_search_plan", fp_search_plan,
                                          compute_search_plan,
                                          resume_valid=search_plan_ok)
        res.media_search_plan = [MediaSearchPlan.from_dict(p)
                                 for p in search_plan_payload]
        search_plan_hash = stable_hash(search_plan_payload)

        # 5b. candidate search (the ONLY network stage) ---------------------------
        media_config = self._media_config(ep)
        provider = self._build_media_provider(ep, media_config)

        def candidates_ok(payload) -> bool:
            try:
                cand_map = payload["by_requirement"]
                for items in cand_map.values():
                    for c in items:
                        MediaCandidate.from_dict(c)
            except Exception:
                return False
            return True

        def compute_candidates():
            found = search_candidates(res.media_search_plan, provider,
                                      media_config.max_candidates_per_query)
            return {"provider": media_config.provider,
                    "by_requirement": {rid: [c.to_dict() for c in cands]
                                       for rid, cands in found.items()}}

        fp_candidates = stable_hash(
            STAGE_VERSIONS["media_candidates"], ep.episode_id,
            search_plan_hash, media_config.provider, provider.provider_version,
            media_config.max_candidates_per_query, media_config.timeout_sec,
            media_config.retries, ep.catalog)
        candidates_payload = self._stage(ep, "media_candidates", fp_candidates,
                                         compute_candidates,
                                         resume_valid=candidates_ok)
        res.media_candidates = {
            rid: [MediaCandidate.from_dict(c) for c in items]
            for rid, items in candidates_payload["by_requirement"].items()}
        candidates_hash = stable_hash(candidates_payload)

        # 5c. media assets (rank -> license -> fetch -> validate -> cache) ---------
        def media_ok(payload) -> bool:
            try:
                assets = [MediaAsset.from_dict(a) for a in payload]
            except Exception:
                return False
            return all(a.asset_id for a in assets)

        def compute_media():
            cache = MediaCache(media_config.cache_dir
                               or (self.store.root / "media_cache"))
            service = MediaAcquisitionService(provider, cache, media_config)
            outcome = service.acquire(res.requirements, res.media_search_plan,
                                      res.media_candidates, mode=self.mode)
            self._last_acquisition = outcome
            return [a.to_dict() for a in outcome.assets]

        fp_media = stable_hash(
            STAGE_VERSIONS["media_assets"], ep.episode_id, candidates_hash,
            MEDIA_RANKING_VERSION, LICENSE_POLICY_VERSION,
            MEDIA_DOWNLOAD_VERSION, ACQUISITION_SERVICE_VERSION,
            media_config.to_dict(), self.mode)
        media_payload = self._stage(ep, "media_assets", fp_media, compute_media,
                                    resume_valid=media_ok)
        res.assets = [MediaAsset.from_dict(a) for a in media_payload]
        media_hash = stable_hash(media_payload)

        # 5d. acquisition trace ------------------------------------------------------
        def trace_ok(payload) -> bool:
            known = {r.requirement_id for r in res.requirements}
            try:
                traces = [AcquisitionTrace.from_dict(t) for t in payload]
            except Exception:
                return False
            return bool(traces) and all(t.requirement_id in known for t in traces)

        def compute_trace():
            outcome = self._last_acquisition
            if outcome is not None:
                return [t.to_dict() for t in outcome.traces]
            # assets resumed: rebuild a faithful trace from persisted state
            plan_by_req = {p.requirement_id: p for p in res.media_search_plan}
            asset_by_req = {a.requirement_id: a for a in res.assets}
            rebuilt = []
            for req in res.requirements:
                plan = plan_by_req.get(req.requirement_id)
                asset = asset_by_req.get(req.requirement_id)
                rebuilt.append(AcquisitionTrace(
                    requirement_id=req.requirement_id,
                    provider=media_config.provider,
                    queries_attempted=([plan.primary_query] +
                                       list(plan.alternate_queries)
                                       if plan else []),
                    selected_candidate_id=(asset.candidate_id
                                           if asset and not asset.is_placeholder
                                           else None),
                    unresolved_reason="" if asset is not None else "unresolved",
                ).to_dict())
            return rebuilt

        fp_trace = stable_hash(STAGE_VERSIONS["media_acquisition_trace"],
                               ep.episode_id, candidates_hash, media_hash)
        trace_payload = self._stage(ep, "media_acquisition_trace", fp_trace,
                                    compute_trace, resume_valid=trace_ok)
        res.acquisition_traces = [AcquisitionTrace.from_dict(t)
                                  for t in trace_payload]

        # 5e. attribution manifest ---------------------------------------------------
        def attribution_ok(payload) -> bool:
            asset_ids = {a.asset_id for a in res.assets}
            try:
                entries = payload["assets"]
            except Exception:
                return False
            return all(e["asset_id"] in asset_ids for e in entries)

        def compute_attribution():
            entries = []
            for a in res.assets:
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

        fp_attr = stable_hash(STAGE_VERSIONS["media_attribution"], ep.episode_id,
                              media_hash)
        self._stage(ep, "media_attribution", fp_attr, compute_attribution,
                    resume_valid=attribution_ok)

        # 6. strategy feasibility (plan-of-record) --------------------------------
        def feasibility_ok(payload) -> bool:
            try:
                records = [SelectionRecord.from_dict(r)
                           for r in payload.get("records", [])]
            except Exception:
                return False
            return validation.validate_strategy_plan(records, res.beats).ok

        def compute_feasibility():
            complete = self._repair_strategy_records(res.preliminary_strategy_plan,
                                                     res.beats)
            result = run_feasibility_pass(complete, res.beats, res.requirements,
                                          res.assets,
                                          self.planner_config.max_family_streak)
            return {"adjustments": result.adjustments,
                    "records": [r.to_dict() for r in result.records]}

        fp_feas = stable_hash(STAGE_VERSIONS["strategy_feasibility"], ep.episode_id,
                              strategy_hash, media_hash, self.mode,
                              self.planner_config.max_family_streak)
        feas_payload = self._stage(ep, "strategy_feasibility", fp_feas,
                                   compute_feasibility, resume_valid=feasibility_ok)
        res.strategy_plan = [SelectionRecord.from_dict(r)
                             for r in feas_payload["records"]]
        res.feasibility = {"adjustments": feas_payload.get("adjustments", [])}
        plan_hash = stable_hash(feas_payload)

        # 7. compositions ----------------------------------------------------------
        def comps_ok(payload) -> bool:
            beat_ids = {b.beat_id for b in res.beats}
            try:
                comps = [VisualComposition.from_dict(c) for c in payload]
            except Exception:
                return False
            if not comps or any(c.beat_id not in beat_ids for c in comps):
                return False
            report = validation.validate_compositions(comps, res.beats,
                                                      res.assets, mode=self.mode)
            return report.ok

        def compute_compositions():
            history = VisualHistory()
            used: set[str] = set()
            sel_by_beat = {r.beat_id: r for r in res.strategy_plan}
            comps: list[VisualComposition] = []
            for beat in res.beats:
                sel = sel_by_beat.get(beat.beat_id)
                if sel is None:
                    continue
                beat_assets = assets_for_beat(res.assets, res.requirements,
                                              beat.beat_id)
                try:
                    strat_def = STRATEGY_CATALOG[sel.selected_strategy]
                    comps.append(compose_beat(
                        beat, sel, strat_def, res.art_direction,
                        beat_assets, history, used, ep.episode_id))
                except Exception as exc:  # family crash -> deterministic fallback
                    self._repair_log("visual_compositions",
                                     f"{beat.beat_id}: family "
                                     f"'{sel.visual_family}' raised {type(exc).__name__}",
                                     "deterministic fallback composition")
                    comps.append(validation.deterministic_fallback_composition(
                        beat, len(comps), beat_assets,
                        family=sel.visual_family))
            comps = self._fallback_invalid_compositions(comps, res.beats, res.assets)
            return [c.to_dict() for c in comps]

        fp_comps = stable_hash(STAGE_VERSIONS["visual_compositions"], ep.episode_id,
                               beats_hash, plan_hash, media_hash, art_hash,
                               self.mode, FAMILIES_VERSION)
        comps_payload = self._stage(ep, "visual_compositions", fp_comps,
                                    compute_compositions, resume_valid=comps_ok)
        res.compositions = [VisualComposition.from_dict(c) for c in comps_payload]
        comps_hash = stable_hash(comps_payload)

        # 8. visual history (derived; rebuildable) ----------------------------------
        def history_ok(payload) -> bool:
            try:
                hist = VisualHistory.from_dict(payload)
            except Exception:
                return False
            return len(hist.entries) == len(res.compositions)

        def compute_history():
            return history_from_compositions(res.compositions).to_dict()

        fp_hist = stable_hash(STAGE_VERSIONS["visual_history"], ep.episode_id,
                              comps_hash)
        hist_payload = self._stage(ep, "visual_history", fp_hist, compute_history,
                                   resume_valid=history_ok)
        res.history = VisualHistory.from_dict(hist_payload)

        # 9. motion plan ------------------------------------------------------------
        def motion_ok(payload) -> bool:
            try:
                motion = MotionPlan.from_dict(payload)
            except Exception:
                return False
            return validation.validate_motion(motion, res.beats,
                                              res.compositions).ok

        def compute_motion():
            return build_motion_plan(ep.episode_id, res.beats,
                                     res.compositions).to_dict()

        fp_motion = stable_hash(STAGE_VERSIONS["motion_plan"], ep.episode_id,
                                beats_hash, comps_hash)
        motion_payload = self._stage(ep, "motion_plan", fp_motion, compute_motion,
                                     resume_valid=motion_ok)
        res.motion = MotionPlan.from_dict(motion_payload)
        motion_hash = stable_hash(motion_payload)

        # 10. timeline ------------------------------------------------------------
        def timeline_ok(payload) -> bool:
            if not isinstance(payload, dict) or not payload.get("segments"):
                return False
            return validation.validate_timeline(payload, res.beats,
                                                 res.compositions,
                                                 self.mode).ok

        def compute_timeline():
            return build_timeline(ep.episode_id, ep.narration, res.beats,
                                  res.compositions, res.motion)

        fp_timeline = stable_hash(STAGE_VERSIONS["timeline"], ep.episode_id,
                                  narration_payload, beats_hash, comps_hash,
                                  motion_hash)
        res.timeline = self._stage(ep, "timeline", fp_timeline, compute_timeline,
                                   resume_valid=timeline_ok)

        # 11. editorial QC (final gate; never hides failures) ------------------------
        beats_report = validation.validate_beats(res.beats, ep.narration.duration_sec)
        comps_report = validation.validate_compositions(
            res.compositions, res.beats, res.assets, mode=self.mode)
        plan_report = validation.validate_strategy_plan(res.strategy_plan, res.beats)
        motion_report = validation.validate_motion(res.motion, res.beats,
                                                   res.compositions)
        timeline_report = validation.validate_timeline(res.timeline, res.beats,
                                                       res.compositions, self.mode)
        media_report = validation.validate_media_completeness(
            res.beats, res.requirements, res.assets, res.strategy_plan, self.mode)
        res.validation = {
            "beats": {"ok": beats_report.ok, "errors": beats_report.errors,
                      "warnings": beats_report.warnings},
            "compositions": {"ok": comps_report.ok, "errors": comps_report.errors,
                             "warnings": comps_report.warnings},
            "strategy_plan": {"ok": plan_report.ok, "errors": plan_report.errors,
                              "warnings": plan_report.warnings},
            "motion_plan": {"ok": motion_report.ok, "errors": motion_report.errors,
                            "warnings": motion_report.warnings},
            "timeline": {"ok": timeline_report.ok, "errors": timeline_report.errors,
                         "warnings": timeline_report.warnings},
            "media_completeness": {"ok": media_report.ok,
                                   "errors": media_report.errors,
                                   "warnings": media_report.warnings},
        }
        res.ok = all(v["ok"] for v in res.validation.values())
        res.manifest["stages"] = self._statuses
        res.manifest["repairs"] = self._repairs
        res.manifest["feasibility"] = res.feasibility["adjustments"]
        res.manifest["ok"] = res.ok
        self.store.save(ep.episode_id, "pipeline_manifest", res.manifest)
        return res

    # ---- repair helpers -----------------------------------------------------
    def _repair_strategy_records(self, records: list[SelectionRecord],
                                 beats: list[SemanticBeat]) -> list[SelectionRecord]:
        """Repair malformed records AND create records for missing beats."""
        beat_map = {b.beat_id: b for b in beats}
        by_beat: dict[str, SelectionRecord] = {}
        for rec in records:
            beat = beat_map.get(rec.beat_id)
            if (beat is not None and rec.selected_strategy in STRATEGY_CATALOG
                    and len(rec.reason) >= 20):
                by_beat[rec.beat_id] = rec
            else:
                default_id = self._default_strategy(beat, rec)
                self._repair_log("visual_strategy_plan",
                                 f"{rec.beat_id}: unusable selection",
                                 f"fallback strategy '{default_id}'")
                by_beat[rec.beat_id] = SelectionRecord(
                    beat_id=rec.beat_id,
                    semantic_function=rec.semantic_function,
                    selected_strategy=default_id,
                    visual_family=STRATEGY_CATALOG[default_id].visual_family,
                    reason=("deterministic fallback: planner output failed "
                            "stage validation; first catalog candidate used."),
                    is_fallback=True)
        for beat in beats:  # beats with no record at all
            if beat.beat_id not in by_beat:
                default_id = self._default_strategy(beat, None)
                self._repair_log("visual_strategy_plan",
                                 f"{beat.beat_id}: missing selection record",
                                 f"created fallback strategy '{default_id}'")
                by_beat[beat.beat_id] = SelectionRecord(
                    beat_id=beat.beat_id,
                    semantic_function=beat.semantic_function.value,
                    selected_strategy=default_id,
                    visual_family=STRATEGY_CATALOG[default_id].visual_family,
                    reason=("deterministic fallback: no selection existed for "
                            "this beat; first catalog candidate used."),
                    is_fallback=True)
        return [by_beat[b.beat_id] for b in beats if b.beat_id in by_beat]

    @staticmethod
    def _default_strategy(beat: SemanticBeat | None,
                          rec: SelectionRecord | None) -> str:
        from videotool.domain.semantic_beat import SemanticFunction
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

    # ---- composition fallback flow -----------------------------------------
    def _fallback_invalid_compositions(self, comps: list[VisualComposition],
                                       beats: list[SemanticBeat],
                                       assets: list[MediaAsset]) -> list[VisualComposition]:
        report = validation.validate_compositions(comps, beats, assets,
                                                  mode=self.mode)
        if report.ok:
            return comps
        beat_map = {b.beat_id: b for b in beats}
        bad_ids: set[str] = set()
        for err in report.errors:
            for comp in comps:
                if err.startswith(f"{comp.composition_id}:") or \
                        err.startswith(f"{comp.composition_id}/") or \
                        err.startswith(f"{comp.beat_id}:"):
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
            self._repair_log("visual_compositions",
                             f"{comp.composition_id}: {report.errors[0]}",
                             "deterministic fallback composition")
            rebuilt.append(validation.deterministic_fallback_composition(
                beat, fallback_index, assets, family=comp.visual_family))
            fallback_index += 1
        second = validation.validate_compositions(rebuilt, beats, assets,
                                                  mode=self.mode)
        if not second.ok:
            # still broken: surface loudly at final QC, never hide
            self._repair_log("visual_compositions",
                             "fallback compositions still invalid",
                             "kept for final QC to fail loudly")
        return rebuilt
