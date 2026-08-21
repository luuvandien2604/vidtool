"""Unit tests for ASS subtitle generation (subtitles.py).

Pure Python tests: validate ASS file structure, style headers, safe zone
margins, timing precision, and determinism without FFmpeg.
"""
from __future__ import annotations

from videotool.fixtures.berlin_wall import load_episode
from videotool.pipeline.runner import EpisodeInput, PipelineRunner
from videotool.artifacts import ArtifactStore
from videotool.render.subtitles import (
    calculate_safe_zone_margins,
    generate_node_text_dialogue,
    generate_subtitles_ass,
    sec_to_ass_time,
)


def test_sec_to_ass_time_formatting():
    """Verify ASS timestamp formatting H:MM:SS.cc with rounding."""
    assert sec_to_ass_time(0.0) == "0:00:00.00"
    assert sec_to_ass_time(3.52) == "0:00:03.52"
    assert sec_to_ass_time(65.123) == "0:01:05.12"
    assert sec_to_ass_time(3661.05) == "1:01:01.05"
    assert sec_to_ass_time(59.999) == "0:01:00.00"


def test_safe_zone_margins_calculation():
    """Verify normalized safe zone converts accurately to pixel margins."""
    # Default safe zone: (0.05, 0.84, 0.90, 0.15) on 1920x1080 canvas
    ml, mr, mv = calculate_safe_zone_margins((0.05, 0.84, 0.90, 0.15), 1920, 1080)
    assert ml == 96
    assert mr == 96
    assert mv > 0  # vertical bottom margin


def test_generate_subtitles_ass_structure(tmp_path):
    """Verify generated ASS subtitle string has valid header, styles, and dialogue lines."""
    timeline = {
        "episode_id": "test_ep",
        "canvas": {"width": 1920, "height": 1080},
        "subtitle_safe_zone": {"x": 0.05, "y": 0.84, "width": 0.90, "height": 0.15},
        "subtitles": [
            {"start_sec": 0.0, "end_sec": 3.2, "text": "First line of documentary narration."},
            {"start_sec": 3.5, "end_sec": 7.0, "text": "Second line with critical historical context."},
        ],
    }

    ass_text = generate_subtitles_ass(timeline)
    assert "[Script Info]" in ass_text
    assert "PlayResX: 1920" in ass_text
    assert "PlayResY: 1080" in ass_text
    assert "[V4+ Styles]" in ass_text
    assert "Style: Default," in ass_text
    assert "Style: NodeLabel," in ass_text
    assert "[Events]" in ass_text

    dialogue_lines = [l for l in ass_text.splitlines() if l.startswith("Dialogue:")]
    assert len(dialogue_lines) == 2
    assert "0:00:00.00" in dialogue_lines[0]
    assert "First line of documentary narration." in dialogue_lines[0]
    assert "0:00:03.50" in dialogue_lines[1]
    assert "Second line with critical historical context." in dialogue_lines[1]


def test_subtitles_determinism():
    """Identical timeline inputs produce byte-identical ASS outputs."""
    timeline = {
        "episode_id": "test_ep",
        "canvas": {"width": 1920, "height": 1080},
        "subtitles": [
            {"start_sec": 1.25, "end_sec": 4.5, "text": "Deterministic test line."},
        ],
    }
    out1 = generate_subtitles_ass(timeline)
    out2 = generate_subtitles_ass(timeline)
    assert out1 == out2


def test_node_text_dialogue_positioning():
    """Verify positioned node text creates valid ASS dialogue with pos tags."""
    line = generate_node_text_dialogue("Gunter Schabowski", 2.0, 5.5, 960, 540, "NodeLabel")
    assert line.startswith("Dialogue: 1,0:00:02.00,0:00:05.50,NodeLabel")
    assert "{\\an5\\pos(960,540)}Gunter Schabowski" in line
