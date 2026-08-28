"""Media acquisition service (Phase 2A spec sections 21-25, 32, 34).

Orchestration only - providers, ranking, licensing, cache and validation
live behind their own modules. Guarantees:

* never take the first result: primary query, then alternates
* minimum_candidate_score: a missing asset beats a semantically wrong one
* failure isolation: one failed requirement never crashes the episode
* every selection is explainable (components + reason persisted)
* provenance (provider/page/url/license/checksum/timestamp) never lost
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field

from videotool.domain.assets import AssetRequirement, MediaAsset
from videotool.editorial.media.cache import MediaCache
from videotool.editorial.media.licensing import license_allowed
from videotool.editorial.media.models import (MediaAcquisitionConfig,
                                              MediaAttribution,
                                              MediaCandidate, MediaSearchPlan,
                                              ScoredCandidate, AcquisitionTrace)
from videotool.editorial.media.ranking import RankingPolicy, rank_candidates
from videotool.editorial.media.validation import validate_media
from videotool.providers.media.base import MediaProvider, ProviderError

ACQUISITION_SERVICE_VERSION = 2  # 2: isolated search + complete trace semantics


from concurrent.futures import ThreadPoolExecutor, as_completed
import logging

logger = logging.getLogger(__name__)


def search_candidates(plans: list[MediaSearchPlan], provider: MediaProvider,
                      max_per_query: int,
                      diagnostics: dict[str, list[dict]] | None = None
                      ) -> dict[str, list[MediaCandidate]]:
    """Run every plan's queries through the provider concurrently in parallel.

    Failure-isolated per query: one ProviderError marks that query failed
    but never aborts the stage; candidates already found are preserved.
    """
    by_req: dict[str, list[MediaCandidate]] = {}

    def _search_single_plan(plan: MediaSearchPlan) -> tuple[str, list[MediaCandidate], list[dict]]:
        seen: dict[str, MediaCandidate] = {}
        query_results: list[dict] = []
        for query in [plan.primary_query] + plan.alternate_queries:
            if not query or not query.strip():
                continue
            try:
                found = provider.search(query, max_per_query)
            except (ProviderError, TimeoutError) as exc:
                query_results.append({
                    "query": query, "candidate_count": 0,
                    "error": {"requirement_id": plan.requirement_id,
                              "query": query, "stage": "search",
                              "error_type": type(exc).__name__,
                              "message": _safe_error_message(exc),
                              "recoverable": True}})
                continue
            query_results.append({"query": query,
                                  "candidate_count": len(found)})
            for cand in found:
                seen.setdefault(cand.candidate_id, cand)
        return plan.requirement_id, list(seen.values()), query_results

    if len(plans) <= 1:
        for plan in plans:
            req_id, cands, diag = _search_single_plan(plan)
            by_req[req_id] = cands
            if diagnostics is not None:
                diagnostics[req_id] = diag
    else:
        with ThreadPoolExecutor(max_workers=min(8, len(plans))) as executor:
            futures = [executor.submit(_search_single_plan, plan) for plan in plans]
            for fut in as_completed(futures):
                try:
                    req_id, cands, diag = fut.result()
                    by_req[req_id] = cands
                    if diagnostics is not None:
                        diagnostics[req_id] = diag
                except Exception as exc:
                    logger.warning(f"Error in candidate search worker: {exc}")

    return by_req


def _safe_error_message(exc: Exception) -> str:
    """Bound diagnostics and remove URL query strings that may hold secrets."""
    return re.sub(r"(https?://[^?\s]+)\?\S+", r"\1?<redacted>", str(exc))[:500]


@dataclass
class AcquisitionResult:
    assets: list[MediaAsset] = field(default_factory=list)
    traces: list[AcquisitionTrace] = field(default_factory=list)
    attributions: list[MediaAttribution] = field(default_factory=list)


class MediaAcquisitionService:
    def __init__(self, provider: MediaProvider, cache: MediaCache,
                 config: MediaAcquisitionConfig | None = None):
        self.provider = provider
        self.cache = cache
        self.config = config or MediaAcquisitionConfig()
        self.policy = RankingPolicy(
            min_photo_width=self.config.min_photo_width,
            min_document_width=self.config.min_document_width,
            minimum_score=self.config.minimum_candidate_score)

    def acquire(self, requirements: list[AssetRequirement],
                plans: list[MediaSearchPlan],
                candidates_by_req: dict[str, list[MediaCandidate]],
                mode: str = "final",
                search_diagnostics: dict[str, list[dict]] | None = None
                ) -> AcquisitionResult:
        plan_by_req = {p.requirement_id: p for p in plans}
        result = AcquisitionResult()
        usage_counts: dict[str, int] = {}
        last_candidate_id: str | None = None

        for req in requirements:
            plan = plan_by_req.get(req.requirement_id)
            if plan is None:
                # never crash the episode over one odd requirement
                result.traces.append(AcquisitionTrace(
                    requirement_id=req.requirement_id,
                    unresolved_reason="no search plan"))
                if mode == "draft":
                    result.assets.append(self._placeholder(req))
                continue
            candidates = candidates_by_req.get(req.requirement_id, [])
            try:
                asset, trace = self._acquire_one(
                    req, plan, candidates, mode, usage_counts, last_candidate_id,
                    (search_diagnostics or {}).get(req.requirement_id, []))
            except ProviderError as exc:
                asset, trace = None, AcquisitionTrace(
                    requirement_id=req.requirement_id,
                    provider=self.provider.provider_id,
                    queries_attempted=[plan.primary_query] + plan.alternate_queries,
                    unresolved_reason=f"provider error: {exc}",
                    errors=[{"stage": "fetch", "error_type": type(exc).__name__,
                             "message": _safe_error_message(exc),
                             "recoverable": True}])
            result.traces.append(trace)
            if asset is None and mode == "draft":
                asset = self._placeholder(req)
            if asset is not None:
                result.assets.append(asset)
                if asset.candidate_id:
                    usage_counts[asset.candidate_id] = \
                        usage_counts.get(asset.candidate_id, 0) + 1
                    last_candidate_id = asset.candidate_id
                if not asset.is_placeholder:
                    result.attributions.append(MediaAttribution(
                        asset_id=asset.asset_id,
                        creator=asset.attribution.get("creator", ""),
                        source_name=self.provider.provider_id,
                        source_page=asset.source_page,
                        license_name=asset.attribution.get("license_name", ""),
                        license_url=asset.attribution.get("license_url", "")))
        return result

    # ---- one requirement ------------------------------------------------
    def _acquire_one(self, req: AssetRequirement, plan: MediaSearchPlan,
                     candidates: list[MediaCandidate],
                     mode: str, usage_counts: dict[str, int],
                     last_candidate_id: str | None,
                     search_results: list[dict]
                     ) -> tuple[MediaAsset | None, AcquisitionTrace]:
        trace = AcquisitionTrace(requirement_id=req.requirement_id,
                                 provider=self.provider.provider_id,
                                 queries_attempted=[plan.primary_query] +
                                 list(plan.alternate_queries),
                                 search_results=list(search_results))
        trace.errors = [dict(item["error"]) for item in search_results
                        if item.get("error")]
        all_candidates = {c.candidate_id: c for c in candidates}
        trace.candidates_seen = len(all_candidates)
        trace.candidate_ids = sorted(all_candidates)
        if not all_candidates:
            trace.unresolved_reason = "no candidates found"
            return None, trace

        scored = rank_candidates(plan, list(all_candidates.values()),
                                 policy=self.policy,
                                 usage_counts=usage_counts,
                                 last_selected=last_candidate_id)
        threshold = self.policy.minimum_score
        trace.candidate_scores = [entry.to_dict() for entry in scored]

        for position, entry in enumerate(scored):
            cand = all_candidates[entry.candidate_id]
            if not license_allowed(cand.license_name):
                trace.rejections.append({
                    "candidate_id": cand.candidate_id,
                    "reason": f"license not allowed: {cand.license_name or 'missing'}"})
                continue
            if entry.components.get("media_type_match", 0.0) < 0.5:
                # a document scan must never satisfy a portrait requirement
                # (semantic correctness outranks a lucky entity overlap)
                trace.rejections.append({
                    "candidate_id": cand.candidate_id,
                    "reason": f"type mismatch: {cand.media_type} not usable "
                              f"for {plan.requirement_kind}"})
                continue
            if entry.score < threshold:
                trace.rejections.append({
                    "candidate_id": cand.candidate_id,
                    "reason": f"score {entry.score:.3f} below threshold {threshold}",
                    "score": entry.score})
                continue
            asset, reject, cache_status = self._materialize(req, cand, entry)
            if asset is None:
                trace.rejections.append({
                    "candidate_id": cand.candidate_id,
                    "reason": reject or "download validation failed",
                    "score": entry.score,
                    "cache_status": cache_status})
                continue
            trace.selected_candidate_id = cand.candidate_id
            trace.selected_score = entry.score
            trace.selected_reason = entry.reason
            trace.cache_status = cache_status
            for lower in scored[position + 1:]:
                trace.rejections.append({
                    "candidate_id": lower.candidate_id,
                    "reason": "not selected: lower-ranked than accepted candidate",
                    "score": lower.score})
            return asset, trace

        if scored:
            trace.unresolved_reason = (
                f"no acceptable candidate ({len(trace.rejections)} rejected, "
                f"best score {scored[0].score:.3f}, threshold {threshold})")
        else:
            trace.unresolved_reason = "no candidates found"
        return None, trace

    # ---- materialization --------------------------------------------------
    def _materialize(self, req: AssetRequirement, cand: MediaCandidate,
                     entry: ScoredCandidate
                     ) -> tuple[MediaAsset | None, str, str]:
        revision = (cand.provider_metadata.get("revision")
                    or cand.provider_metadata.get("sha1")
                    or cand.provider_metadata.get("timestamp") or "")
        cached = self.cache.find_by_candidate(
            cand.candidate_id, provider=cand.provider,
            media_url=cand.media_url, revision=str(revision))
        if cached is not None:
            sha, data = cached
            checked = validate_media(data,
                                     min_bytes=self.config.min_bytes,
                                     max_bytes=self.config.max_bytes)
            if not checked.ok:
                return None, f"cached content invalid: {checked.reason}", "hit"
            cache_status = "hit"
        else:
            try:
                fetched = self.provider.fetch(cand)
            except ProviderError as exc:
                return None, f"download failed: {exc}", "miss"
            data = fetched.data
            checked = validate_media(data,
                                     min_bytes=self.config.min_bytes,
                                     max_bytes=self.config.max_bytes)
            if not checked.ok:
                return None, f"download validation failed: {checked.reason}", "miss"
            sha, _ = self.cache.put(
                data, checked.extension,
                {"candidate_id": cand.candidate_id,
                 "provider": cand.provider,
                 "media_url": cand.media_url,
                 "revision": str(revision),
                 "source_page": cand.source_page,
                 "license_name": cand.license_name,
                 "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
            cache_status = "miss"

        return MediaAsset(
            asset_id=f"media:{sha[:16]}",
            requirement_id=req.requirement_id,
            description=cand.title or cand.description,
            kind=req.kind,
            entity_match=entry.components.get("entity_match", 0.0),
            date_match=entry.components.get("date_match", 0.0),
            location_match=entry.components.get("location_match", 0.0),
            context_match=entry.components.get("event_match", 0.0),
            visual_quality=entry.components.get("resolution", 0.5),
            source_quality=entry.components.get("source_quality", 0.5),
            score_components=dict(entry.components),
            score_penalties=dict(entry.penalties),
            selection_reason=entry.reason,
            candidate_id=cand.candidate_id,
            provider=cand.provider,
            source_page=cand.source_page,
            media_url=cand.media_url,
            checksum=sha,
            width=checked.width or cand.width,
            height=checked.height or cand.height,
            license_name=cand.license_name,
            retrieval_ts=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            attribution={"creator": cand.creator,
                         "license_name": cand.license_name,
                         "license_url": cand.license_url},
        ), "", cache_status

    @staticmethod
    def _placeholder(req: AssetRequirement) -> MediaAsset:
        return MediaAsset(
            asset_id=f"placeholder:{req.kind}:{req.requirement_id}",
            requirement_id=req.requirement_id,
            description=f"PLACEHOLDER - {req.description}",
            kind=req.kind, is_placeholder=True)
