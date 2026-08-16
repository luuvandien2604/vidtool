"""Generalization tests (spec section 31): the architecture must not be
Berlin-specific. Runs other topics through the same pipeline machinery.
"""
import pytest

from videotool.artifacts import ArtifactStore
from videotool.domain.narration import Narration, synthetic_word_timings
from videotool.pipeline.runner import EpisodeInput, PipelineRunner

TOPICS = [
    {
        "episode_id": "chernobyl_gen",
        "subject": "Chernobyl: The Reactor That Burned",
        "text": (
            "April 1986. One reactor failed during a safety test. "
            "The plant outside Pripyat had a flawed reactor design. "
            "Anatoly Dyatlov was the supervisor in the control room that night. "
            "Because the test was delayed for hours, the reactor's core "
            "had become unstable. "
            "The emergency document log recorded every step of the procedure. "
            "Radiation spread through Ukraine and across the border into Europe. "
            "Within days, the exclusion zone was sealed, "
            "and by the end the city of Pripyat stood empty."
        ),
    },
    {
        "episode_id": "titanic_gen",
        "subject": "The Sinking of the Titanic",
        "text": (
            "April 1912. The largest liner in the world was crossing the Atlantic. "
            "The ship sailed from Southampton on her maiden voyage. "
            "Edward Smith was the captain nearing the end of his career. "
            "Because the wireless warnings about ice never reached the bridge, "
            "the liner held her speed through the night. "
            "The telegram log survived with the last messages. "
            "Passengers fled toward the lifeboats as the hull flooded. "
            "Within hours the ship sank, and by dawn the sea was silent."
        ),
    },
]


@pytest.mark.parametrize("topic", TOPICS, ids=[t["episode_id"] for t in TOPICS])
def test_pipeline_generalizes_to_other_topics(tmp_path, topic):
    narration = Narration(text=topic["text"],
                          words=synthetic_word_timings(topic["text"]))
    runner = PipelineRunner(ArtifactStore(tmp_path), mode="final")
    res = runner.run(EpisodeInput(
        episode_id=topic["episode_id"], subject=topic["subject"],
        narration=narration, catalog=[]))
    beats = res.beats
    assert len(beats) >= 6
    assert all(b.semantic_function for b in beats)
    assert res.art_direction.concept_cluster != "political_division"
    assert len(res.compositions) == len(beats)
    signatures = {c.novelty_signature for c in res.compositions}
    assert len(signatures) == len(res.compositions)
    assert len({c.visual_family for c in res.compositions}) >= 3


def test_no_berlin_hardcoded_in_architecture():
    """Berlin vocabulary must appear only in the fixture module (spec 31).

    The one allowed exception: the generic CLI fixture registry must name
    the fixture module it loads - that is discovery, not logic.
    """
    import subprocess
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        ["grep", "-ril", "--include", "*.py",
         "-e", "schabowski", "-e", "bornholmer", "-e", "berlin",
         str(root / "videotool")],
        capture_output=True, text=True)
    hits = [line for line in result.stdout.splitlines() if line]
    allowed = [p for p in hits if "fixtures" in p or p.endswith("videotool/cli.py")]
    assert sorted(hits) == sorted(allowed), f"Berlin leaked into: {hits}"
    if "videotool/cli.py" in allowed:
        cli = Path(root / "videotool/cli.py").read_text()
        berlin_lines = [l for l in cli.splitlines()
                        if "berlin" in l.lower() and "fixture" not in l.lower()
                        and "berlin_wall" not in l]
        assert not berlin_lines, f"cli.py contains Berlin logic: {berlin_lines}"
