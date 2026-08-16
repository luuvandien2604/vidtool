"""Semantic beat segmentation tests."""
from videotool.ai.heuristic import HeuristicBeatAnalyzer
from videotool.domain.narration import Narration, synthetic_word_timings
from videotool.domain.semantic_beat import SemanticFunction
from videotool.fixtures.berlin_wall import NARRATION_TEXT, load_episode


def make_analyzer():
    return HeuristicBeatAnalyzer()


def narration(text):
    return Narration(text=text, words=synthetic_word_timings(text))


def test_fixture_beats_exist_and_are_sequenced(berlin_run):
    beats = berlin_run["result"].beats
    assert len(beats) >= 8
    for i, beat in enumerate(beats):
        assert beat.beat_id == f"beat_{i + 1:04d}"
        assert beat.duration_sec > 0


def test_every_beat_has_a_semantic_function(berlin_run):
    for beat in berlin_run["result"].beats:
        assert isinstance(beat.semantic_function, SemanticFunction)


def test_beats_cover_narration_without_gaps_or_overlaps(berlin_run):
    beats = berlin_run["result"].beats
    dur = berlin_run["data"]["narration"].duration_sec
    assert beats[0].start_sec == 0.0
    for prev, nxt in zip(beats, beats[1:]):
        assert abs(prev.end_sec - nxt.start_sec) < 1e-6
    assert beats[-1].end_sec <= dur + 1e-6


def test_beat_durations_stay_in_target_band(berlin_run):
    for beat in berlin_run["result"].beats:
        assert 1.5 <= beat.duration_sec <= 9.0, beat


def test_fixture_triggers_required_semantic_variety(berlin_run):
    functions = {b.semantic_function for b in berlin_run["result"].beats}
    required = {
        SemanticFunction.HOOK,
        SemanticFunction.LOCATION_INTRODUCTION,
        SemanticFunction.CHARACTER_INTRODUCTION,
        SemanticFunction.GEOGRAPHIC_MOVEMENT,
        SemanticFunction.CHRONOLOGY,
        SemanticFunction.CAUSAL_EXPLANATION,
        SemanticFunction.EVIDENCE,
        SemanticFunction.QUOTE,
        SemanticFunction.CONSEQUENCE,
        SemanticFunction.SUMMARY,
    }
    missing = required - functions
    assert not missing, f"fixture failed to trigger: {missing}"


def test_classification_is_deterministic():
    n = narration(NARRATION_TEXT)
    a = make_analyzer().analyze(n, "ep")
    b = make_analyzer().analyze(n, "ep")
    assert [x.semantic_function for x in a] == [x.semantic_function for x in b]
    assert [x.narration_text for x in a] == [x.narration_text for x in b]


def test_quote_detection():
    n = narration('He said it plainly: "This changes everything tonight."')
    beats = make_analyzer().analyze(n, "ep")
    assert beats[0].semantic_function == SemanticFunction.QUOTE


def test_long_sentence_is_split_at_clause_boundary():
    text = ("Because Moscow would not intervene, the regime in East Berlin "
            "had lost its strongest protector, and the crowds knew it, "
            "and the guards knew it too, before the evening was over.")
    n = narration(text)
    beats = make_analyzer().analyze(n, "ep")
    assert len(beats) >= 2
    for beat in beats:
        assert beat.duration_sec <= 9.0


def test_short_sentences_merge_into_beats():
    text = "Hungary had opened its border. Thousands fled the same night. The trains ran west."
    n = narration(text)
    beats = make_analyzer().analyze(n, "ep")
    assert len(beats) <= 2


def test_word_ranges_are_contiguous():
    n = narration(NARRATION_TEXT)
    beats = make_analyzer().analyze(n, "ep")
    for prev, nxt in zip(beats, beats[1:]):
        assert nxt.word_start == prev.word_end


def test_fixture_word_timings_match_text():
    data = load_episode()
    joined = " ".join(w.text for w in data["narration"].words)
    assert joined == NARRATION_TEXT
    for w in data["narration"].words:
        assert w.end_sec > w.start_sec
