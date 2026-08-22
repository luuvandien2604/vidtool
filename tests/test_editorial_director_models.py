"""Unit tests for AI Editorial Director models and context projector (Phase 3A)."""
from __future__ import annotations

from videotool.domain.art_direction import EpisodeArtDirection
from videotool.domain.semantic_beat import SemanticBeat, SemanticFunction
from videotool.domain.visual_history import EpisodeVisualMemory, HistoryEntry
from videotool.editorial.director.models import (
    EditorialDirectorRequest,
    EditorialIntent,
    StrategyDescriptor,
    ValidationResult,
)
from videotool.editorial.director.projector import EditorialContextProjector


def test_strategy_descriptor_roundtrip():
    desc = StrategyDescriptor(
        strategy_id="archival_portrait",
        visual_family="archival_subject",
        compatible_functions=["CHARACTER_INTRODUCTION", "QUOTE"],
        storytelling_note="Portrait with identity metadata.",
    )
    d = desc.to_dict()
    restored = StrategyDescriptor.from_dict(d)
    assert restored.strategy_id == desc.strategy_id
    assert restored.visual_family == desc.visual_family
    assert restored.compatible_functions == desc.compatible_functions
    assert restored.storytelling_note == desc.storytelling_note


def test_editorial_intent_roundtrip():
    intent = EditorialIntent(
        beat_id="beat_001",
        story_role="TURNING_POINT",
        visual_goal="Show dramatic crowd gathering",
        information_priority=["crowd", "border"],
        information_density=0.75,
        emotional_goal="tension_release",
        candidate_strategies=["archival_crowd", "full_frame_cinematic"],
        preferred_visual_families=["archival_subject", "full_frame_cinematic"],
        avoid_visual_families=["document_evidence"],
        must_show=["Bornholmer checkpoint"],
        must_not_show=["modern vehicles"],
        emphasis="Crowd surge",
        reason="Turning point demands arresting visual scale.",
        confidence=0.95,
    )
    d = intent.to_dict()
    assert d["schema_version"] == 1
    assert d["beat_id"] == "beat_001"
    assert d["confidence"] == 0.95

    restored = EditorialIntent.from_dict(d)
    assert restored.beat_id == intent.beat_id
    assert restored.story_role == intent.story_role
    assert restored.information_priority == ["crowd", "border"]
    assert restored.candidate_strategies == ["archival_crowd", "full_frame_cinematic"]
    assert restored.confidence == 0.95


def test_context_projector_and_request_fingerprint():
    beat = SemanticBeat(
        beat_id="beat_002",
        start_sec=0.0,
        end_sec=3.5,
        narration_text="At the Brandenburg Gate, soldiers stood guard.",
        word_start=0,
        word_end=8,
        semantic_function=SemanticFunction.LOCATION_INTRODUCTION,
        visual_intent="Show Brandenburg Gate",
        entities=["soldiers"],
        locations=["Brandenburg Gate"],
        dates=["1989"],
        information_density=0.6,
    )
    art_dir = EpisodeArtDirection(
        episode_id="berlin",
        subject="Berlin Wall",
        visual_motifs=["concrete", "barbed_wire"],
        accent={"primary": "#C84B31"},
    )
    memory = EpisodeVisualMemory()
    memory.record(HistoryEntry(
        beat_id="beat_001",
        visual_family="archival_subject",
        strategy="archival_portrait",
        composition_signature="sig_1",
    ))

    req = EditorialContextProjector.project_beat(
        beat=beat,
        art_direction=art_dir,
        visual_memory=memory,
    )

    assert req.beat_id == "beat_002"
    assert req.semantic_function == "LOCATION_INTRODUCTION"
    assert "Brandenburg Gate" in req.locations
    assert "concrete" in req.art_direction_motifs
    assert req.recent_families == ["archival_subject"]
    assert len(req.candidate_descriptors) > 0

    # Test request fingerprint determinism
    fp1 = req.fingerprint()
    fp2 = req.fingerprint()
    assert fp1 == fp2
    assert isinstance(fp1, str) and len(fp1) == 16


def test_validation_result_structure():
    res = ValidationResult(
        is_valid=True,
        accepted_strategies=["archival_portrait"],
        rejected_strategies=[("fake_strategy", "Unknown ID")],
        rejection_reasons=["Unknown ID"],
    )
    d = res.to_dict()
    assert d["is_valid"] is True
    assert d["accepted_strategies"] == ["archival_portrait"]
    assert d["rejected_strategies"] == [["fake_strategy", "Unknown ID"]]
