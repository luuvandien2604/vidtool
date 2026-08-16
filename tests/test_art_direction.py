"""Episode art direction tests: identity must change per topic (spec section 4)."""
from videotool.ai.heuristic import HeuristicArtDirector
from videotool.domain.narration import Narration, synthetic_word_timings
from videotool.domain.semantic_beat import SemanticBeat, SemanticFunction

SUBJECTS = {
    "berlin": ("The Fall of the Berlin Wall",
               "The wall divided Berlin for twenty-eight years until the "
               "border opened and the government collapsed amid protest."),
    "chernobyl": ("Chernobyl: The Reactor That Burned",
                  "The reactor exploded during a safety test, radiation "
                  "spread across Europe, and the exclusion zone remains."),
    "titanic": ("The Sinking of the Titanic",
                "The liner struck an iceberg on her maiden voyage, the "
                "wireless telegraph called for help, and the ship sank."),
    "apollo13": ("Apollo 13: The Successful Failure",
                 "The spacecraft's oxygen module failed on the way to the "
                 "lunar landing, mission control rebuilt the telemetry, and "
                 "the astronauts survived."),
}


def direction_for(key):
    subject, text = SUBJECTS[key]
    narration = Narration(text=text, words=synthetic_word_timings(text))
    beats = [SemanticBeat(beat_id="beat_0001", start_sec=0.0, end_sec=5.0,
                          narration_text=text, word_start=0, word_end=10,
                          semantic_function=SemanticFunction.ESTABLISHING_CONTEXT,
                          visual_intent="context")]
    return HeuristicArtDirector().generate(f"ep_{key}", subject, narration, beats)


def test_every_episode_gets_an_art_direction():
    for key in SUBJECTS:
        ad = direction_for(key)
        assert ad.visual_motifs
        assert ad.archival_language
        assert ad.accent.get("primary")
        assert ad.motion_character


def test_chernobyl_is_not_berlin():
    berlin, chernobyl = direction_for("berlin"), direction_for("chernobyl")
    assert berlin.concept_cluster != chernobyl.concept_cluster
    assert berlin.visual_motifs != chernobyl.visual_motifs
    assert berlin.accent["primary"] != chernobyl.accent["primary"]


def test_titanic_is_not_apollo():
    titanic, apollo = direction_for("titanic"), direction_for("apollo13")
    assert titanic.concept_cluster != apollo.concept_cluster
    assert titanic.visual_motifs != apollo.visual_motifs
    assert titanic.accent["primary"] != apollo.accent["primary"]


def test_forbidden_patterns_always_present():
    for key in SUBJECTS:
        assert "generic_slideshow" in direction_for(key).forbidden_patterns
        assert "constant_zoom" in direction_for(key).forbidden_patterns


def test_deterministic():
    assert direction_for("chernobyl").to_dict() == direction_for("chernobyl").to_dict()


def test_episode_art_direction_persisted(berlin_run):
    ad = berlin_run["result"].art_direction
    assert ad is not None
    assert ad.subject == "The Fall of the Berlin Wall"
    assert ad.concept_cluster == "political_division"
    raw = berlin_run["store"].load("berlin_wall_phase1", "episode_art_direction")
    assert raw["episode_id"] == "berlin_wall_phase1"
