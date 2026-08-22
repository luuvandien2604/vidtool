"""Media acquisition pipeline stages (search plan, candidates, assets, trace, attribution)."""
from __future__ import annotations

from typing import Any

from videotool.domain.assets import MediaAsset
from videotool.editorial.media import (
    ACQUISITION_SERVICE_VERSION,
    LICENSE_POLICY_VERSION,
    MEDIA_CACHE_VERSION,
    MEDIA_DOWNLOAD_VERSION,
    MEDIA_QUERY_VERSION,
    MEDIA_RANKING_VERSION,
    AcquisitionTrace,
    MediaAcquisitionService,
    MediaCandidate,
    MediaSearchPlan,
    plan_search,
    search_candidates,
    validate_media_assets,
)
from videotool.pipeline.context import PipelineContext
from videotool.pipeline.fingerprints import stable_hash
from videotool.pipeline.stage import BasePipelineStage


# ---------------------------------------------------------------------------
# Stage 7: Media Search Plan
# ---------------------------------------------------------------------------
class MediaSearchPlanStage(BasePipelineStage):
    id = "media_search_plan"

    def fingerprint(self, ctx: PipelineContext) -> str:
        import videotool.editorial.media as media_pkg
        import videotool.pipeline.runner as runner_module
        q_ver = getattr(
            runner_module,
            "MEDIA_QUERY_VERSION",
            getattr(media_pkg, "MEDIA_QUERY_VERSION", MEDIA_QUERY_VERSION),
        )
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
        ranking_ver = getattr(
            runner_module,
            "MEDIA_RANKING_VERSION",
            getattr(media_pkg, "MEDIA_RANKING_VERSION", MEDIA_RANKING_VERSION),
        )
        license_ver = getattr(
            runner_module,
            "LICENSE_POLICY_VERSION",
            getattr(media_pkg, "LICENSE_POLICY_VERSION", LICENSE_POLICY_VERSION),
        )
        dl_ver = getattr(
            runner_module,
            "MEDIA_DOWNLOAD_VERSION",
            getattr(media_pkg, "MEDIA_DOWNLOAD_VERSION", MEDIA_DOWNLOAD_VERSION),
        )
        cache_ver = getattr(
            runner_module,
            "MEDIA_CACHE_VERSION",
            getattr(media_pkg, "MEDIA_CACHE_VERSION", MEDIA_CACHE_VERSION),
        )
        svc_ver = getattr(
            runner_module,
            "ACQUISITION_SERVICE_VERSION",
            getattr(media_pkg, "ACQUISITION_SERVICE_VERSION", ACQUISITION_SERVICE_VERSION),
        )
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
