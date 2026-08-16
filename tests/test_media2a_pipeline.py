"""Phase 2A pipeline integration tests: new stages, artifacts, fingerprints,
version invalidation, resume, opaque ids end-to-end, mode semantics."""
import json

import videotool.pipeline.runner as runner_module
import videotool.editorial.media as media_pkg
from videotool.artifacts import ArtifactStore
from videotool.fixtures.berlin_wall import load_episode
from videotool.pipeline.runner import EpisodeInput, PipelineRunner

MEDIA_STAGES = ["media_search_plan", "media_candidates", "media_assets",
                "media_acquisition_trace", "media_attribution"]


def run_ep(tmp_path, mode="final", **kw):
    data = load_episode()
    return PipelineRunner(ArtifactStore(tmp_path / "artifacts"), mode=mode,
                          **kw).run(EpisodeInput(**data))


def statuses(res):
    return {s: v["status"] for s, v in res.manifest["stages"].items()}


def load_artifact(tmp_path, name):
    with open(ArtifactStore(tmp_path / "artifacts")
              .path_for("berlin_wall_phase1", name)) as f:
        return json.load(f)


# ---- stages + artifacts --------------------------------------------------------

def test_media_stages_exist_and_artifacts_persist(berlin_run):
    store = berlin_run["store"]
    existing = store.existing("berlin_wall_phase1")
    for stage in MEDIA_STAGES:
        assert f"{stage}.json" and stage in existing, f"missing {stage}"
    meta = store.load("berlin_wall_phase1", "stage_meta")
    for stage in MEDIA_STAGES:
        assert stage in meta  # full fingerprint chain participation


def test_search_plan_artifact_is_semantic(berlin_run):
    plans = load_artifact_from(berlin_run, "media_search_plan")
    assert plans and all(p["primary_query"] for p in plans)
    forbidden = {"historical photo", "war image", "documentary image",
                 "old city"}
    assert all(p["primary_query"].lower() not in forbidden for p in plans)
    portrait = next(p for p in plans if p["requirement_kind"] == "portrait")
    assert "schabowski" in portrait["primary_query"].lower()


def load_artifact_from(berlin_run, name):
    return berlin_run["store"].load("berlin_wall_phase1", name)


def test_candidates_artifact_carries_normalized_models(berlin_run):
    payload = load_artifact_from(berlin_run, "media_candidates")
    assert payload["provider"] == "fixture"
    total = sum(len(v) for v in payload["by_requirement"].values())
    assert total > 0
    for cands in payload["by_requirement"].values():
        for c in cands:
            assert c["media_type"] in ("PHOTO", "PORTRAIT", "DOCUMENT",
                                       "MAP", "ILLUSTRATION")
            assert c["license_name"]  # normalized model, provider dicts hidden


def test_assets_artifact_has_provenance_and_scores(berlin_run):
    assets = load_artifact_from(berlin_run, "media_assets")
    real = [a for a in assets if not a.get("is_placeholder")]
    assert real
    for a in real:
        assert a["checksum"] and len(a["checksum"]) == 64
        assert a["provider"] == "fixture"
        assert a["candidate_id"]
        assert a["score_components"]
        assert a["selection_reason"]
        assert a["attribution"]["license_name"]


def test_trace_and_attribution_artifacts(berlin_run):
    traces = load_artifact_from(berlin_run, "media_acquisition_trace")
    assert traces and all(t["queries_attempted"] for t in traces)
    attr = load_artifact_from(berlin_run, "media_attribution")
    assert attr["assets"]
    asset_ids = {a["asset_id"] for a in
                 load_artifact_from(berlin_run, "media_assets")}
    assert all(e["asset_id"] in asset_ids for e in attr["assets"])
    assert all(e["license"] for e in attr["assets"])


def test_acquired_media_actually_cached_and_valid(berlin_run):
    import hashlib
    assets = load_artifact_from(berlin_run, "media_assets")
    real = [a for a in assets if not a.get("is_placeholder")]
    cache_root = berlin_run["store"].root / "media_cache"
    blobs = list(cache_root.glob("*/*.png"))
    assert blobs, "content-addressed cache must hold the fetched bytes"
    for blob in blobs:
        assert hashlib.sha256(blob.read_bytes()).hexdigest()[:2] == \
            blob.parent.name  # content-addressed layout


# ---- fingerprints + invalidation ------------------------------------------------

def test_ranking_version_change_invalidates_media_chain(tmp_path, monkeypatch):
    run_ep(tmp_path)
    monkeypatch.setattr(media_pkg, "MEDIA_RANKING_VERSION", 99)
    # runner imports names inside run(); patch the package attrs it reads
    import videotool.pipeline.runner as rm
    monkeypatch.setattr(rm, "MEDIA_RANKING_VERSION", 99, raising=False)
    res2 = run_ep(tmp_path)
    st = statuses(res2)
    assert st["media_assets"] == "invalidated"
    assert st["media_acquisition_trace"] == "invalidated"
    assert st["media_attribution"] == "invalidated"
    assert st["media_candidates"] == "resumed"    # search itself unchanged
    assert st["media_search_plan"] == "resumed"
    assert res2.ok


def test_provider_config_change_invalidates_candidates_and_assets(tmp_path):
    from videotool.editorial.media import MediaAcquisitionConfig
    run_ep(tmp_path)
    res2 = run_ep(tmp_path,
                  media_config=MediaAcquisitionConfig(max_candidates_per_query=3))
    st = statuses(res2)
    assert st["media_candidates"] == "invalidated"
    assert st["media_assets"] == "invalidated"
    assert st["media_search_plan"] == "resumed"  # query planning untouched
    assert res2.ok


def test_mode_switch_recomputes_assets_not_search(tmp_path):
    run_ep(tmp_path, mode="draft")
    res2 = run_ep(tmp_path, mode="final")
    st = statuses(res2)
    assert st["media_assets"] == "invalidated"   # mode in asset fingerprint
    assert st["media_search_plan"] == "resumed"
    assert st["media_candidates"] == "resumed"
    assert res2.ok


def test_media_artifacts_resume_untouched(tmp_path):
    run_ep(tmp_path)
    res2 = run_ep(tmp_path)
    st = statuses(res2)
    for stage in MEDIA_STAGES:
        assert st[stage] == "resumed", stage
    assert res2.ok


def test_corrupt_candidates_artifact_recomputes(tmp_path):
    run_ep(tmp_path)
    store = ArtifactStore(tmp_path / "artifacts")
    store.path_for("berlin_wall_phase1", "media_candidates").write_text(
        "not json", encoding="utf-8")
    res2 = run_ep(tmp_path)
    assert statuses(res2)["media_candidates"] == "invalidated"
    assert res2.ok


# ---- opaque ids + strength semantics e2e ------------------------------------------

def test_opaque_requirement_ids_flow_through_real_acquisition(tmp_path, monkeypatch):
    from videotool.editorial.composition import semantic_asset_requirements

    def weird_reqs(beats):
        reqs = semantic_asset_requirements(beats)
        for r in reqs:
            r.requirement_id = f"ACQ::{r.beat_id}::{r.kind}/2026"
        return reqs

    monkeypatch.setattr(runner_module, "semantic_asset_requirements",
                        weird_reqs)
    res = run_ep(tmp_path)
    assert res.ok
    assert all("::" in r.requirement_id for r in res.requirements)
    plans = {p.requirement_id: p for p in res.media_search_plan}
    assert set(plans) == {r.requirement_id for r in res.requirements}
    assets = [a for a in res.assets if not a.is_placeholder]
    assert assets
    for a in assets:
        assert a.requirement_id in plans  # mapping, never parsed


def test_final_mode_never_binds_placeholder_or_unlicensed(berlin_run):
    assets = load_artifact_from(berlin_run, "media_assets")
    assert all(not a.get("is_placeholder") for a in assets)
    from videotool.editorial.media.licensing import license_allowed
    for a in assets:
        assert license_allowed(a["license_name"])


def test_required_unresolved_still_gates_final(tmp_path):
    data = load_episode()
    data["catalog"] = []
    res = PipelineRunner(ArtifactStore(tmp_path / "a"), mode="final").run(
        EpisodeInput(**data))
    assert not res.ok
    assert res.validation["media_completeness"]["errors"]


def test_draft_mode_placeholders_labelled(tmp_path):
    data = load_episode()
    data["catalog"] = []
    res = PipelineRunner(ArtifactStore(tmp_path / "a"), mode="draft").run(
        EpisodeInput(**data))
    assert res.ok
    placeholders = [a for a in res.assets if a.is_placeholder]
    assert placeholders
    assert all(a.description.startswith("PLACEHOLDER") for a in placeholders)
