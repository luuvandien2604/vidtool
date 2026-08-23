"""Tests for feedback-driven revision loop and durable editorial overrides."""
from __future__ import annotations

from pathlib import Path
import pytest

from videotool.artifacts import ArtifactStore
from videotool.fixtures import berlin_wall
from videotool.editorial.director.revision import RevisionService
from videotool.pipeline.runner import EpisodeInput, PipelineRunner
from videotool.pipeline.policy import ExecutionPolicy


@pytest.fixture
def planned_artifacts(tmp_path: Path):
    store = ArtifactStore(str(tmp_path / "artifacts"))
    runner = PipelineRunner(store=store, mode="draft")
    ep_data = berlin_wall.load_episode()
    runner.run(EpisodeInput(**ep_data))
    return store, ep_data["episode_id"]


def test_feedback_proposal_generation(planned_artifacts):
    store, episode_id = planned_artifacts
    service = RevisionService(provider_name="mock")

    # Structured revision on Beat 4 Hungary caption (literal RHS parsing)
    prop = service.propose_revision(
        episode_id=episode_id,
        feedback_text="Beat 4: caption Hungary -> Escape route begins",
        store=store,
    )

    assert prop.proposal_id.startswith("prop_")
    assert prop.beat_id == "beat_0004"
    assert prop.target_type == "node_caption"
    assert prop.is_valid is True
    assert prop.old_value == "Hungary"
    assert prop.new_value == "Escape route begins"  # Verbatim RHS, not a hardcoded substitute


def test_feedback_proposal_rejected_ungrounded(planned_artifacts):
    store, episode_id = planned_artifacts
    service = RevisionService(provider_name="mock")

    # Structured revision proposing ungrounded proper noun 'London'
    prop = service.propose_revision(
        episode_id=episode_id,
        feedback_text="Beat 4: caption Hungary -> Escape to London",
        store=store,
    )

    assert prop.is_valid is False
    assert "London" in prop.rejection_reason


def test_reject_nonexistent_target(planned_artifacts):
    store, episode_id = planned_artifacts
    service = RevisionService(provider_name="mock")

    # Nonexistent beat 99
    prop = service.propose_revision(
        episode_id=episode_id,
        feedback_text="Beat 99: caption should be changed",
        store=store,
    )
    assert prop.is_valid is False
    assert "Target beat could not be identified" in prop.rejection_reason or "does not exist" in prop.rejection_reason


def test_reject_timing_feedback(planned_artifacts):
    store, episode_id = planned_artifacts
    service = RevisionService(provider_name="mock")

    # Timing change request
    prop = service.propose_revision(
        episode_id=episode_id,
        feedback_text="Beat 4: kéo dài thời lượng thêm 3 giây",
        store=store,
    )
    assert prop.is_valid is False
    assert "timing changes aren't supported yet" in prop.rejection_reason


def test_mock_declines_unstructured_free_text(planned_artifacts):
    store, episode_id = planned_artifacts
    service = RevisionService(provider_name="mock")

    # Unstructured text that mock cannot parse
    prop = service.propose_revision(
        episode_id=episode_id,
        feedback_text="Beat 2: hãy làm cho nó trông hoành tráng và kỳ bí hơn nữa nhé",
        store=store,
    )
    assert prop.is_valid is False
    assert "Mock provider cannot interpret arbitrary free-text feedback" in prop.rejection_reason


def test_apply_override_persists_and_modifies_frame_plan(planned_artifacts):
    store, episode_id = planned_artifacts
    service = RevisionService(provider_name="mock")

    prop = service.propose_revision(
        episode_id=episode_id,
        feedback_text="Beat 4: caption 'Hungary' -> 'Hungary border'",
        store=store,
    )
    assert prop.is_valid is True

    # Apply override
    overrides = service.apply_revision(
        episode_id=episode_id,
        proposal_id=prop.proposal_id,
        store=store,
    )
    assert len(overrides) == 1
    assert overrides[0]["new_value"] == "Hungary border"

    # Verify frame plan picks up the override
    from videotool.render.frame_plan import build_episode_frame_plan
    timeline = store.load(episode_id, "timeline")
    geo_plans = store.load(episode_id, "semantic_geometry") or []
    semantic_beats = store.load(episode_id, "semantic_beats") or []

    plan = build_episode_frame_plan(
        timeline=timeline,
        geometry_plans=geo_plans,
        semantic_beats=semantic_beats,
        editorial_overrides=overrides,
    )

    beat_4_plan = next(b for b in plan.beats if b.beat_id == "beat_0004")
    hungary_elem = next((e for e in beat_4_plan.text_elements if "hungary" in e.text.lower()), None)
    assert hungary_elem is not None
    assert hungary_elem.text == "Hungary border"
    assert hungary_elem.content_source == "override"
