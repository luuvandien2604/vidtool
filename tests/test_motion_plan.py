"""Motion plan + transition tests (spec sections 12-14)."""
from videotool.domain.motion import EventKind, TransitionCategory
from videotool.editorial.transitions import plan_transitions, select_transition_category
from videotool.domain.semantic_beat import SemanticBeat, SemanticFunction as SF


def test_motion_events_stay_inside_their_beat(berlin_run):
    beats = {b.beat_id: b for b in berlin_run["result"].beats}
    for plan in berlin_run["result"].motion.plans:
        beat = beats[plan.beat_id]
        for ev in plan.events:
            assert ev.start_sec >= beat.start_sec - 1e-6, ev
            assert ev.end_sec <= beat.end_sec + 1e-6, ev
            assert ev.end_sec > ev.start_sec


def test_every_motion_event_has_semantic_reason(berlin_run):
    for plan in berlin_run["result"].motion.plans:
        for ev in plan.events:
            assert ev.semantic_reason.strip(), f"{plan.composition_id}/{ev.layer_id}"


def test_camera_is_stable_by_default(berlin_run):
    stable = [p for p in berlin_run["result"].motion.plans
              if p.camera_behavior == "stable"]
    assert stable, "camera must default to stable"
    for plan in berlin_run["result"].motion.plans:
        assert plan.camera_behavior in ("stable", "slow_push")
        if plan.camera_behavior == "slow_push":
            assert plan.camera_reason.strip()


def test_entrances_precede_exits_per_layer(berlin_run):
    for plan in berlin_run["result"].motion.plans:
        by_layer: dict[str, dict[EventKind, float]] = {}
        for ev in plan.events:
            by_layer.setdefault(ev.layer_id, {})[ev.kind] = ev.start_sec
        for layer_id, kinds in by_layer.items():
            if EventKind.ENTRANCE in kinds and EventKind.EXIT in kinds:
                assert kinds[EventKind.ENTRANCE] <= kinds[EventKind.EXIT], layer_id


def test_transitions_exist_between_all_adjacent_beats(berlin_run):
    beats = berlin_run["result"].beats
    transitions = berlin_run["result"].motion.transitions
    assert len(transitions) == len(beats) - 1
    for t, (prev, nxt) in zip(transitions, zip(beats, beats[1:])):
        assert t.from_beat == prev.beat_id and t.to_beat == nxt.beat_id
        assert t.reason
        assert t.duration_sec > 0


def _beat(fn, i=1):
    return SemanticBeat(beat_id=f"beat_{i:04d}", start_sec=i * 6.0, end_sec=i * 6.0 + 5.0,
                        narration_text="x", word_start=0, word_end=2,
                        semantic_function=fn, visual_intent="t")


def test_transition_categories_follow_meaning_pairs():
    cases = [
        (SF.CAUSAL_EXPLANATION, SF.CONSEQUENCE, TransitionCategory.CAUSE_TO_EFFECT),
        (SF.EVIDENCE, SF.REVEAL, TransitionCategory.EVIDENCE_TO_REVEAL),
        (SF.CHARACTER_INTRODUCTION, SF.GEOGRAPHIC_MOVEMENT, TransitionCategory.CHARACTER_TO_ACTION),
        (SF.LOCATION_INTRODUCTION, SF.GEOGRAPHIC_MOVEMENT, TransitionCategory.MAP_TO_LOCATION),
        (SF.CHRONOLOGY, SF.SUMMARY, TransitionCategory.PAST_TO_PRESENT),
    ]
    for prev_fn, next_fn, expected in cases:
        cat, reason = select_transition_category(_beat(prev_fn, 1), _beat(next_fn, 2))
        assert cat == expected, f"{prev_fn}->{next_fn} gave {cat}"
        assert reason


def test_chapter_break_on_context_reset():
    prev = _beat(SF.EVIDENCE, 1); prev.entities = ["Schabowski"]
    nxt = _beat(SF.ESTABLISHING_CONTEXT, 2); nxt.entities = ["Reactor Four"]
    cat, _ = select_transition_category(prev, nxt)
    assert cat == TransitionCategory.HARD_CHAPTER_BREAK
    same = _beat(SF.ESTABLISHING_CONTEXT, 3); same.entities = ["Schabowski"]
    cat2, _ = select_transition_category(prev, same)
    assert cat2 != TransitionCategory.HARD_CHAPTER_BREAK


def test_transitions_never_exceed_beat_boundaries(berlin_run):
    beats = {b.beat_id: b for b in berlin_run["result"].beats}
    for t in berlin_run["result"].motion.transitions:
        assert t.start_sec >= beats[t.from_beat].start_sec
        assert t.end_sec <= beats[t.from_beat].end_sec + 1e-6
        assert t.start_sec < beats[t.to_beat].start_sec + 1e-6
