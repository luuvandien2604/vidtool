"""Artifact persistence + resume tests (spec sections 20, 23-H, 23-I)."""
import json

from videotool.artifacts import ArtifactStore
from videotool.pipeline.runner import STAGES, EpisodeInput, PipelineRunner
from videotool.fixtures.berlin_wall import load_episode


def run_pipeline(tmp_path, mode="final"):
    data = load_episode()
    runner = PipelineRunner(ArtifactStore(tmp_path / "artifacts"), mode=mode)
    return runner.run(EpisodeInput(**data))


def test_all_stage_artifacts_persisted(berlin_run):
    existing = berlin_run["store"].existing("berlin_wall_phase1")
    for stage in STAGES:
        assert stage in existing, f"missing artifact: {stage}.json"


def test_manifest_records_computed_on_first_run(tmp_path):
    res = run_pipeline(tmp_path)
    statuses = res.manifest["stages"]
    assert all(v["status"] == "computed" for v in statuses.values()), statuses


def test_resume_reuses_earlier_stages(tmp_path):
    run_pipeline(tmp_path)
    store = ArtifactStore(tmp_path / "artifacts")
    store.delete("berlin_wall_phase1", "timeline")
    store.delete("berlin_wall_phase1", "motion_plan")

    res2 = run_pipeline(tmp_path)
    statuses = res2.manifest["stages"]
    assert statuses["semantic_beats"]["status"] == "resumed"
    assert statuses["episode_art_direction"]["status"] == "resumed"
    assert statuses["visual_strategy_plan"]["status"] == "resumed"
    assert statuses["media_assets"]["status"] == "resumed"
    assert statuses["motion_plan"]["status"] == "invalidated"
    assert statuses["timeline"]["status"] == "invalidated"
    assert res2.ok


def test_recomputed_stages_are_deterministic(tmp_path):
    """A resumed run must reproduce the exact artifact content (spec 20)."""
    run_pipeline(tmp_path)
    store = ArtifactStore(tmp_path / "artifacts")
    before = store.load("berlin_wall_phase1", "timeline")
    store.delete("berlin_wall_phase1", "timeline")
    run_pipeline(tmp_path)
    after = store.load("berlin_wall_phase1", "timeline")
    assert before == after


def test_corrupt_artifact_is_recomputed(tmp_path):
    run_pipeline(tmp_path)
    store = ArtifactStore(tmp_path / "artifacts")
    p = store.path_for("berlin_wall_phase1", "visual_compositions")
    p.write_text("{ this is not json", encoding="utf-8")
    res = run_pipeline(tmp_path)
    assert res.manifest["stages"]["visual_compositions"]["status"] == "invalidated"
    assert res.ok


def test_force_reruns_everything(tmp_path):
    run_pipeline(tmp_path)
    data = load_episode()
    runner = PipelineRunner(ArtifactStore(tmp_path / "artifacts"), force=True)
    res = runner.run(EpisodeInput(**data))
    assert all(v["status"] == "computed" for v in res.manifest["stages"].values())
    assert res.ok


def test_draft_mode_yields_placeholders(tmp_path):
    data = load_episode()
    data["catalog"] = []  # nothing acquirable
    runner = PipelineRunner(ArtifactStore(tmp_path / "a"), mode="draft")
    res = runner.run(EpisodeInput(**data))
    assert any(a.is_placeholder for a in res.assets)
    # draft-mode compositions may bind placeholders explicitly...
    placeholder_layers = [(c.composition_id, l.id)
                          for c in res.compositions for l in c.layers
                          if l.asset_id and l.asset_id.startswith("placeholder:")]
    assert placeholder_layers, "draft mode should expose holes, not hide them"
    # ...and draft validation tolerates them, while final mode would not
    assert res.ok
