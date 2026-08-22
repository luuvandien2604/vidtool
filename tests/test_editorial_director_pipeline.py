"""Integration tests for AI Editorial Director within PipelineRunner (Phase 3A)."""
from __future__ import annotations

from pathlib import Path

from videotool.fixtures.berlin_wall import load_episode
from videotool.pipeline.artifact_store import ArtifactStore
from videotool.pipeline.context import EpisodeInput
from videotool.pipeline.policy import ExecutionPolicy
from videotool.pipeline.runner import PipelineRunner


def test_pipeline_with_mock_editorial_director(tmp_path: Path):
    store = ArtifactStore(tmp_path / "artifacts")
    policy = ExecutionPolicy(
        mode="draft",
        force=True,
        editorial_ai_enabled=True,
        editorial_ai_provider="mock",
    )
    runner = PipelineRunner(store=store, policy=policy)

    ep_data = load_episode()
    ep = EpisodeInput(**ep_data)

    res = runner.run(ep)
    assert res.ok is True
    assert len(res.strategy_plan) > 0
    assert len(res.compositions) > 0

    # Verify editorial_intents artifact was persisted
    assert store.exists("berlin_wall_phase1", "editorial_intents")
    intents_artifact = store.load("berlin_wall_phase1", "editorial_intents")
    assert intents_artifact["provider"] == "mock"
    assert intents_artifact["schema_version"] == 1
    assert len(intents_artifact["items"]) == len(res.beats)


def test_editorial_ai_disabled_parity(tmp_path: Path):
    """Verify that when editorial_ai_enabled=False, pipeline behaves 100% identically."""
    store = ArtifactStore(tmp_path / "artifacts")
    policy = ExecutionPolicy(
        mode="draft",
        force=True,
        editorial_ai_enabled=False,
    )
    runner = PipelineRunner(store=store, policy=policy)

    ep_data = load_episode()
    ep = EpisodeInput(**ep_data)

    res = runner.run(ep)
    assert res.ok is True
    # Artifact editorial_intents should NOT be created when AI is disabled
    assert not store.exists("berlin_wall_phase1", "editorial_intents")
