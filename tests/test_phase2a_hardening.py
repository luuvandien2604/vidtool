"""Regression coverage for the Phase 2A production hardening patch."""
import copy

import pytest

from videotool.artifacts import ArtifactStore
from videotool.domain.assets import AssetRequirement
from videotool.editorial.media.acquisition import (MediaAcquisitionService,
                                                    search_candidates)
from videotool.editorial.media.cache import MediaCache
from videotool.editorial.media.models import (MediaAcquisitionConfig,
                                              MediaCandidate, MediaSearchPlan)
from videotool.editorial.media.ranking import score_candidate
from videotool.fixtures.berlin_wall import load_episode
from videotool.pipeline.fingerprints import STAGE_VERSIONS, stable_hash
from videotool.pipeline.runner import EpisodeInput, PipelineRunner
from videotool.providers.media import FixtureMediaProvider, ProviderError
from videotool.providers.media.fixture import synthesize_png


def _candidate(candidate_id="good", provider="fixture", media_url=None):
    return MediaCandidate(
        candidate_id=candidate_id, provider=provider,
        title="Apollo 13 mission control photograph 1970",
        description="Apollo 13 mission control photograph 1970",
        media_type="PHOTO", width=1400, height=1000,
        license_name="CC0 1.0",
        license_url="https://creativecommons.org/publicdomain/zero/1.0/",
        media_url=media_url or f"fixture://{candidate_id}")


def _plan(requirement_id, primary, alternates=()):
    return MediaSearchPlan(
        requirement_id=requirement_id, requirement_kind="photo",
        primary_query=primary, alternate_queries=list(alternates),
        entity_terms=["Apollo 13"], date_terms=["1970"],
        event_terms=["mission control"])


class SearchFailureProvider(FixtureMediaProvider):
    def __init__(self, failures, answers):
        super().__init__([])
        self.failures = set(failures)
        self.answers = answers
        self.attempted = []

    def search(self, query_text, limit):
        self.attempted.append(query_text)
        if query_text in self.failures:
            raise ProviderError(f"outage for {query_text}")
        return list(self.answers.get(query_text, []))[:limit]


def test_search_failure_then_alternate_recovers_and_is_traced(tmp_path):
    provider = SearchFailureProvider({"primary"}, {"alternate": [_candidate()]})
    plan = _plan("opaque-a", "primary", ["alternate"])
    diagnostics = {}
    found = search_candidates([plan], provider, 10, diagnostics)
    req = AssetRequirement("opaque-a", "beat-a", "Apollo 13 photo", "photo",
                           "REQUIRED", ["Apollo 13"])
    result = MediaAcquisitionService(
        provider, MediaCache(tmp_path), MediaAcquisitionConfig()).acquire(
            [req], [plan], found, search_diagnostics=diagnostics)
    assert result.assets[0].candidate_id == "good"
    assert result.traces[0].errors[0]["stage"] == "search"
    assert result.traces[0].errors[0]["recoverable"] is True
    assert provider.attempted == ["primary", "alternate"]


def test_all_searches_fail_for_one_requirement_but_others_continue():
    provider = SearchFailureProvider(
        {"bad-1", "bad-2"}, {"good-query": [_candidate("survivor")]})
    plans = [_plan("opaque-failed", "bad-1", ["bad-2"]),
             _plan("opaque-good", "good-query")]
    diagnostics = {}
    found = search_candidates(plans, provider, 10, diagnostics)
    assert found["opaque-failed"] == []
    assert [c.candidate_id for c in found["opaque-good"]] == ["survivor"]
    assert len(diagnostics["opaque-failed"]) == 2
    assert all(row.get("error") for row in diagnostics["opaque-failed"])


def test_timeout_isolated_without_catching_programming_errors():
    class TimeoutProvider(SearchFailureProvider):
        def search(self, query_text, limit):
            if query_text == "timeout":
                raise TimeoutError("timed out")
            if query_text == "bug":
                raise ValueError("programming bug")
            return [_candidate()]

    diagnostics = {}
    found = search_candidates([_plan("r", "timeout", ["ok"])],
                              TimeoutProvider(set(), {}), 10, diagnostics)
    assert found["r"]
    with pytest.raises(ValueError):
        search_candidates([_plan("r", "bug")], TimeoutProvider(set(), {}), 10)


def _run(tmp_path):
    return PipelineRunner(ArtifactStore(tmp_path / "artifacts"), mode="final").run(
        EpisodeInput(**load_episode()))


@pytest.mark.parametrize("corrupt", ["license", "checksum", "requirement",
                                     "placeholder"])
def test_meta_consistent_media_corruption_is_not_resumed(tmp_path, corrupt):
    _run(tmp_path)
    store = ArtifactStore(tmp_path / "artifacts")
    episode_id = "berlin_wall_phase1"
    payload = store.load(episode_id, "media_assets")
    if corrupt == "license":
        payload[0]["license_name"] = "All Rights Reserved"
        payload[0]["attribution"]["license_name"] = "All Rights Reserved"
    elif corrupt == "checksum":
        payload[0]["checksum"] = "not-a-sha256"
    elif corrupt == "requirement":
        payload[0]["requirement_id"] = "unknown-opaque-binding"
    else:
        payload[0]["is_placeholder"] = True
    store.save(episode_id, "media_assets", payload)
    meta = store.load(episode_id, "stage_meta")
    meta["media_assets"]["output_hash"] = stable_hash(payload)
    store.save(episode_id, "stage_meta", meta)

    result = _run(tmp_path)
    assert result.manifest["stages"]["media_assets"]["status"] == "invalidated"
    assert result.ok
    assert all(a.license_name != "All Rights Reserved" for a in result.assets)
    assert all(a.requirement_id != "unknown-opaque-binding" for a in result.assets)
    assert all(not a.is_placeholder for a in result.assets)


def test_same_blob_keeps_two_candidate_mappings(tmp_path):
    cache = MediaCache(tmp_path)
    data = synthesize_png("shared")
    sha_a, new_a = cache.put(data, "png", {
        "provider": "wikimedia", "candidate_id": "a",
        "media_url": "https://upload.wikimedia.org/a.png", "revision": "rev1"})
    sha_b, new_b = cache.put(data, "png", {
        "provider": "wikimedia", "candidate_id": "b",
        "media_url": "https://upload.wikimedia.org/b.png", "revision": "rev2"})
    assert sha_a == sha_b and new_a and not new_b
    assert cache.find_by_candidate(
        "a", "wikimedia", "https://upload.wikimedia.org/a.png", "rev1")[0] == sha_a
    assert cache.find_by_candidate(
        "b", "wikimedia", "https://upload.wikimedia.org/b.png", "rev2")[0] == sha_a
    assert len(list(tmp_path.glob("*/*.png"))) == 1


def test_candidate_index_is_provider_scoped(tmp_path):
    cache = MediaCache(tmp_path)
    one = synthesize_png("one")
    two = synthesize_png("two")
    sha_one, _ = cache.put(one, "png", {
        "provider": "fixture", "candidate_id": "same",
        "media_url": "fixture://same"})
    sha_two, _ = cache.put(two, "png", {
        "provider": "wikimedia", "candidate_id": "same",
        "media_url": "https://upload.wikimedia.org/same.png"})
    assert cache.find_by_candidate("same", "fixture", "fixture://same")[0] == sha_one
    assert cache.find_by_candidate(
        "same", "wikimedia", "https://upload.wikimedia.org/same.png")[0] == sha_two


def test_changed_remote_identity_cannot_hit_stale_cache(tmp_path):
    cache = MediaCache(tmp_path)
    cache.put(synthesize_png("old"), "png", {
        "provider": "wikimedia", "candidate_id": "same",
        "media_url": "https://upload.wikimedia.org/old.png", "revision": "old"})
    assert cache.find_by_candidate(
        "same", "wikimedia", "https://upload.wikimedia.org/new.png", "new") is None


def test_normal_exact_identity_cache_hit(tmp_path):
    cache = MediaCache(tmp_path)
    sha, _ = cache.put(synthesize_png("exact"), "png", {
        "provider": "wikimedia", "candidate_id": "same",
        "media_url": "https://upload.wikimedia.org/exact.png", "revision": "r1"})
    assert cache.find_by_candidate(
        "same", "wikimedia", "https://upload.wikimedia.org/exact.png", "r1")[0] == sha


def test_realistic_wikimedia_provider_identity_gets_trust_but_not_dominance():
    plan = _plan("r", "Apollo 13")
    realistic = _candidate(provider="wikimedia",
                           media_url="https://upload.wikimedia.org/a.png")
    realistic.categories = ["Apollo 13 mission"]
    assert score_candidate(plan, realistic).components["source_quality"] == 1.0
    trusted_but_wrong = copy.deepcopy(realistic)
    trusted_but_wrong.candidate_id = "wrong"
    trusted_but_wrong.title = trusted_but_wrong.description = "unrelated landscape"
    relevant_unknown = _candidate("right", provider="unknown",
                                  media_url="https://example.org/right.png")
    assert score_candidate(plan, relevant_unknown).score > \
        score_candidate(plan, trusted_but_wrong).score


def test_trace_rebuild_from_resumed_acquisition_is_lossless(tmp_path):
    first = _run(tmp_path)
    expected = [trace.to_dict() for trace in first.acquisition_traces]
    store = ArtifactStore(tmp_path / "artifacts")
    store.delete("berlin_wall_phase1", "media_acquisition_trace")
    second = _run(tmp_path)
    actual = [trace.to_dict() for trace in second.acquisition_traces]
    assert second.manifest["stages"]["media_acquisition_result"]["status"] == "resumed"
    assert second.manifest["stages"]["media_assets"]["status"] == "resumed"
    assert second.manifest["stages"]["media_acquisition_trace"]["status"] == "invalidated"
    assert actual == expected
    assert all(t["candidate_scores"] for t in actual if t["candidates_seen"])


def test_old_media_stage_versions_invalidate_only_media_chain(tmp_path):
    _run(tmp_path)
    store = ArtifactStore(tmp_path / "artifacts")
    meta = store.load("berlin_wall_phase1", "stage_meta")
    for stage in ("media_candidates", "media_acquisition_result",
                  "media_assets", "media_acquisition_trace"):
        meta[stage]["stage_version"] = STAGE_VERSIONS[stage] - 1
    store.save("berlin_wall_phase1", "stage_meta", meta)
    result = _run(tmp_path)
    statuses = {name: row["status"]
                for name, row in result.manifest["stages"].items()}
    assert statuses["asset_requirements"] == "resumed"
    assert statuses["media_search_plan"] == "resumed"
    assert statuses["media_candidates"] == "invalidated"
    assert statuses["media_acquisition_result"] == "invalidated"
    assert statuses["media_assets"] == "invalidated"
    assert statuses["media_acquisition_trace"] == "invalidated"
