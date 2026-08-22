"""Strategy planner + anti-repetition tests (spec sections 6, 10, 21)."""
from videotool.domain.semantic_beat import SemanticFunction
from videotool.domain.visual_history import VisualHistory
from videotool.editorial.strategies import (FUNCTION_CANDIDATES, STRATEGY_CATALOG,
                                             PlanningConfig, StrategyPlanner)


def test_every_semantic_function_has_multiple_candidates():
    for fn in SemanticFunction:
        ids = FUNCTION_CANDIDATES[fn]
        assert len(ids) >= 2, f"{fn} has only {len(ids)} candidates"
        assert all(i in STRATEGY_CATALOG for i in ids)


def test_no_single_function_to_single_layout_mapping():
    """One function must never collapse to one family (spec section 6)."""
    for fn, ids in FUNCTION_CANDIDATES.items():
        families = {STRATEGY_CATALOG[i].visual_family for i in ids}
        assert len(families) >= 2, f"{fn} maps only to {families}"


def test_every_beat_gets_scored_selection_with_reason(berlin_run):
    records = berlin_run["result"].strategy_plan
    beats = berlin_run["result"].beats
    assert len(records) == len(beats)
    for rec in records:
        assert rec.selected_strategy in STRATEGY_CATALOG
        assert len(rec.reason) > 40
        assert 0.0 <= rec.novelty_score <= 1.0
        assert rec.candidates, "scored candidates must be persisted"


def test_selection_reason_explains_why(berlin_run):
    rec = berlin_run["result"].strategy_plan[0]
    assert rec.semantic_function in rec.reason
    assert rec.selected_strategy in rec.reason


def test_family_streak_never_exceeds_limit(berlin_run):
    families = [c.visual_family for c in berlin_run["result"].compositions]
    streak = 1
    for prev, cur in zip(families, families[1:]):
        streak = streak + 1 if prev == cur else 1
        assert streak <= PlanningConfig().max_family_streak


def test_novelty_penalty_pushes_away_from_immediately_used_family(berlin_run):
    planner = StrategyPlanner()
    history = VisualHistory()
    from videotool.domain.visual_history import HistoryEntry
    history.record(HistoryEntry(beat_id="b0", visual_family="document_evidence",
                                strategy="single_document_focus",
                                composition_signature="planned:x"))
    beats = berlin_run["result"].beats
    rec = planner._select_one(
        next(b for b in beats if b.semantic_function == SemanticFunction.EVIDENCE),
        None, history)
    doc_candidates = [c for c in rec.candidates
                      if c.visual_family == "document_evidence"]
    if rec.visual_family == "document_evidence":
        # allowed (streak < limit) but only if it still wins despite penalty
        assert doc_candidates[0].total < 0.95
    # and the reason records the rejected recent family context
    assert rec.rejected_recent_family == "document_evidence"


def test_hard_streak_limit_is_enforced(berlin_run):
    planner = StrategyPlanner(PlanningConfig(max_family_streak=1))
    history = VisualHistory()
    from videotool.domain.visual_history import HistoryEntry
    history.record(HistoryEntry(beat_id="b0", visual_family="document_evidence",
                                strategy="single_document_focus",
                                composition_signature="planned:x"))
    beats = berlin_run["result"].beats
    rec = planner._select_one(
        next(b for b in beats if b.semantic_function == SemanticFunction.EVIDENCE),
        None, history)
    assert rec.visual_family != "document_evidence"


def test_weights_are_configurable():
    cfg = PlanningConfig(weights={"semantic_match": 1.0})
    assert cfg.weights["semantic_match"] == 1.0
    assert "visual_novelty" in cfg.weights


def test_transition_quality_uses_actual_previous_family():
    """Verify transition scoring uses actual previous selection rather than default."""
    from videotool.editorial.strategies import _transition_quality

    # No previous history -> neutral high quality 1.0
    assert _transition_quality(None, "archival_subject") == 1.0

    # Same family -> lower transition score (encourages mode shifts)
    assert _transition_quality("archival_subject", "archival_subject") == 0.55

    # Different family -> higher transition score (good editorial pace)
    assert _transition_quality("document_evidence", "archival_subject") == 0.90
    assert _transition_quality("geographic_map", "causal_network") == 0.90
