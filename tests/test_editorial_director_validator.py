"""Unit tests for AI Editorial Director validation, fallback, and coordinator (Phase 3A)."""
from __future__ import annotations

from unittest.mock import MagicMock

from videotool.domain.semantic_beat import SemanticBeat, SemanticFunction
from videotool.domain.visual_history import EpisodeVisualMemory, HistoryEntry
from videotool.editorial.director.director import EditorialDirector
from videotool.editorial.director.fallback import build_fallback_intent
from videotool.editorial.director.models import (
    EditorialDirectorRequest,
    EditorialIntent,
)
from videotool.editorial.director.projector import EditorialContextProjector
from videotool.editorial.director.validator import validate_editorial_intent


def _sample_request(streak_family: str = "", streak_len: int = 0) -> EditorialDirectorRequest:
    beat = SemanticBeat(
        beat_id="beat_003",
        start_sec=0.0,
        end_sec=3.0,
        narration_text="Erich Honecker was the general secretary.",
        word_start=0,
        word_end=6,
        semantic_function=SemanticFunction.CHARACTER_INTRODUCTION,
        visual_intent="Introduce party leader Honecker",
        entities=["Erich Honecker"],
        locations=[],
        dates=[],
        information_density=0.5,
    )
    memory = EpisodeVisualMemory()
    for i in range(streak_len):
        memory.record(HistoryEntry(
            beat_id=f"prev_{i}",
            visual_family=streak_family,
            strategy="archival_portrait",
            composition_signature=f"sig_{i}",
        ))
    return EditorialContextProjector.project_beat(beat, visual_memory=memory)


def test_validator_accepts_valid_proposal():
    req = _sample_request()
    intent = EditorialIntent(
        beat_id="beat_003",
        story_role="CHARACTER_INTRODUCTION",
        visual_goal="Introduce leader",
        candidate_strategies=["archival_portrait", "portrait_plus_document"],
        preferred_visual_families=["archival_subject"],
    )
    val_res = validate_editorial_intent(intent, req)
    assert val_res.is_valid is True
    assert val_res.accepted_strategies == ["archival_portrait", "portrait_plus_document"]
    assert len(val_res.rejected_strategies) == 0


def test_validator_rejects_unknown_strategy_and_preserves_valid():
    req = _sample_request()
    intent = EditorialIntent(
        beat_id="beat_003",
        story_role="CHARACTER_INTRODUCTION",
        visual_goal="Introduce leader",
        candidate_strategies=["archival_portrait", "non_existent_3d_render"],
        preferred_visual_families=["archival_subject"],
    )
    val_res = validate_editorial_intent(intent, req)
    assert val_res.is_valid is True
    assert val_res.accepted_strategies == ["archival_portrait"]
    assert len(val_res.rejected_strategies) == 1
    assert val_res.rejected_strategies[0][0] == "non_existent_3d_render"


def test_validator_rejects_streak_limit_family():
    # Streak limit reached for archival_subject (len=2)
    req = _sample_request(streak_family="archival_subject", streak_len=2)
    intent = EditorialIntent(
        beat_id="beat_003",
        story_role="CHARACTER_INTRODUCTION",
        visual_goal="Introduce leader",
        candidate_strategies=["archival_portrait"],
        preferred_visual_families=["archival_subject"],
    )
    val_res = validate_editorial_intent(intent, req)
    # Since archival_portrait belongs to archival_subject, it is rejected
    assert val_res.is_valid is False
    assert len(val_res.accepted_strategies) == 0
    assert "streak limit" in val_res.rejected_strategies[0][1]


def test_fallback_intent_generation():
    req = _sample_request()
    fallback = build_fallback_intent(req, reason="AI provider timeout")
    assert fallback.beat_id == "beat_003"
    assert fallback.is_fallback is True
    assert fallback.confidence == 0.0
    assert len(fallback.candidate_strategies) > 0


def test_editorial_director_fallback_on_provider_exception():
    bad_provider = MagicMock()
    bad_provider.provider_id = "failing_mock"
    bad_provider.generate_intent.side_effect = TimeoutError("Remote server timed out")

    director = EditorialDirector(provider=bad_provider)
    req = _sample_request()

    intent, val_res = director.propose(req)
    assert intent.is_fallback is True
    assert intent.confidence == 0.0
    assert val_res.is_valid is False
    assert "TimeoutError" in val_res.rejection_reasons[0]
