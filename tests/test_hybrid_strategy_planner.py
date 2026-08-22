"""Tests for StrategyPlanner hybrid scoring and legacy parity (Phase 3A)."""
from __future__ import annotations

from videotool.domain.semantic_beat import SemanticBeat, SemanticFunction
from videotool.domain.visual_history import VisualHistory
from videotool.editorial.director.models import EditorialIntent
from videotool.editorial.strategies import StrategyPlanner


def _build_test_beats() -> list[SemanticBeat]:
    return [
        SemanticBeat(
            beat_id="beat_001",
            start_sec=0.0,
            end_sec=3.0,
            narration_text="In November 1989, the world changed overnight.",
            word_start=0,
            word_end=7,
            semantic_function=SemanticFunction.HOOK,
            visual_intent="Arresting opening",
            entities=[],
            locations=[],
            dates=["November 1989"],
            information_density=0.2,
        ),
        SemanticBeat(
            beat_id="beat_002",
            start_sec=3.0,
            end_sec=6.5,
            narration_text="The Berlin Wall divided the city for twenty-eight years.",
            word_start=8,
            word_end=16,
            semantic_function=SemanticFunction.LOCATION_INTRODUCTION,
            visual_intent="Introduce divided Berlin",
            entities=[],
            locations=["Berlin"],
            dates=[],
            information_density=0.5,
        ),
        SemanticBeat(
            beat_id="beat_003",
            start_sec=6.5,
            end_sec=10.0,
            narration_text="Erich Honecker vowed the wall would stand for a hundred years.",
            word_start=17,
            word_end=27,
            semantic_function=SemanticFunction.CHARACTER_INTRODUCTION,
            visual_intent="Introduce East German leader Honecker",
            entities=["Erich Honecker"],
            locations=[],
            dates=[],
            information_density=0.6,
        ),
    ]


def test_legacy_deterministic_exact_parity():
    """Verify that StrategyPlanner with intents=None produces exact byte-for-byte legacy parity."""
    beats = _build_test_beats()
    planner = StrategyPlanner()

    # 1. Deterministic run without intents parameter
    res_legacy = planner.select(beats, history=VisualHistory())

    # 2. Deterministic run with intents=None explicitly
    res_hybrid_none = planner.select(beats, history=VisualHistory(), intents=None)

    assert len(res_legacy) == len(res_hybrid_none)
    for r_leg, r_hyb in zip(res_legacy, res_hybrid_none):
        assert r_leg.beat_id == r_hyb.beat_id
        assert r_leg.selected_strategy == r_hyb.selected_strategy
        assert r_leg.visual_family == r_hyb.visual_family
        assert r_leg.reason == r_hyb.reason
        assert r_leg.novelty_score == r_hyb.novelty_score
        assert len(r_leg.candidates) == len(r_hyb.candidates)
        for c_leg, c_hyb in zip(r_leg.candidates, r_hyb.candidates):
            assert c_leg.strategy_id == c_hyb.strategy_id
            assert c_leg.total == c_hyb.total
            assert c_leg.scores == c_hyb.scores
            assert c_leg.rejected_reason == c_hyb.rejected_reason


def test_bounded_ai_nudge_boosts_candidate():
    """Verify that a valid AI proposal nudges a close candidate within bounded MAX_AI_DELTA (0.10)."""
    beats = _build_test_beats()
    planner = StrategyPlanner()

    # For beat_001 (HOOK), default candidates are cinematic_hold, full_frame_archival, silhouette_to_archive_reveal
    intent = EditorialIntent(
        beat_id="beat_001",
        story_role="HOOK",
        visual_goal="Arresting opening with silhouette reveal",
        candidate_strategies=["silhouette_to_archive_reveal"],
        confidence=1.0,
    )

    records = planner.select(beats, history=VisualHistory(), intents={"beat_001": intent})
    record_001 = records[0]

    # Find silhouette_to_archive_reveal in candidates
    cand = next(c for c in record_001.candidates if c.strategy_id == "silhouette_to_archive_reveal")
    assert "ai_alignment" in cand.scores
    assert cand.scores["ai_alignment"] == 0.10


def test_ai_cannot_override_streak_limit():
    """Verify that AI proposal cannot select a strategy whose family is at streak limit."""
    beats = _build_test_beats()
    planner = StrategyPlanner()

    # Manually pre-seed history with 2 consecutive archival_subject entries
    history = VisualHistory()
    from videotool.domain.visual_history import HistoryEntry
    history.record(HistoryEntry("b0", "archival_subject", "archival_portrait", "sig0"))
    history.record(HistoryEntry("b1", "archival_subject", "archival_portrait", "sig1"))

    # For beat_003 (CHARACTER_INTRODUCTION), AI strongly prefers archival_portrait (family archival_subject)
    intent = EditorialIntent(
        beat_id="beat_003",
        story_role="CHARACTER_INTRODUCTION",
        visual_goal="Force archival portrait despite streak",
        candidate_strategies=["archival_portrait"],
        confidence=1.0,
    )

    records = planner.select([beats[2]], history=history, intents={"beat_003": intent})
    record_003 = records[0]

    # archival_subject must NOT be selected because streak limit = 2
    assert record_003.visual_family != "archival_subject"
    cand_portrait = next(c for c in record_003.candidates if c.strategy_id == "archival_portrait")
    assert "family streak limit" in cand_portrait.rejected_reason
