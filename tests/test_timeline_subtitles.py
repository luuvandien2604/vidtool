"""Regression tests for timeline subtitles and ASS escaping (Phase 1)."""
from __future__ import annotations

import pytest

from videotool.domain.narration import WordTiming
from videotool.domain.timing import NarrationTiming
from videotool.editorial.timeline import SUBTITLE_MAX_WORDS, build_subtitles
from videotool.render.subtitles import escape_ass_text, generate_subtitles_ass


def _make_timing(words_and_times: list[tuple[str, float, float]]) -> NarrationTiming:
    timed_words = tuple(
        WordTiming(index=i, text=w, start_sec=s, end_sec=e)
        for i, (w, s, e) in enumerate(words_and_times)
    )
    total_dur = timed_words[-1].end_sec if timed_words else 0.0
    return NarrationTiming(
        words=timed_words,
        duration_sec=total_dur,
        source="test",
        provider="synthetic",
        provider_version=1,
    )


def test_build_subtitles_exactly_seven_words():
    """Verify that exactly 7 words without punctuation form a single caption."""
    words = [(f"word{i}", float(i * 0.3), float((i + 1) * 0.3)) for i in range(7)]
    timing = _make_timing(words)
    subs = build_subtitles(timing)
    assert len(subs) == 1
    assert len(subs[0]["text"].split()) == 7
    assert subs[0]["text"] == "word0 word1 word2 word3 word4 word5 word6"


def test_build_subtitles_eight_words():
    """Verify that 8 words never overflow into an 8-word caption, but split into 7 and 1."""
    words = [(f"word{i}", float(i * 0.3), float((i + 1) * 0.3)) for i in range(8)]
    timing = _make_timing(words)
    subs = build_subtitles(timing)
    assert len(subs) == 2
    assert len(subs[0]["text"].split()) == 7
    assert len(subs[1]["text"].split()) == 1
    assert subs[0]["text"] == "word0 word1 word2 word3 word4 word5 word6"
    assert subs[1]["text"] == "word7"
    for s in subs:
        assert len(s["text"].split()) <= SUBTITLE_MAX_WORDS


def test_build_subtitles_fourteen_words():
    """Verify that 14 words split cleanly into two 7-word captions."""
    words = [(f"word{i}", float(i * 0.2), float((i + 1) * 0.2)) for i in range(14)]
    timing = _make_timing(words)
    subs = build_subtitles(timing)
    assert len(subs) == 2
    assert len(subs[0]["text"].split()) == 7
    assert len(subs[1]["text"].split()) == 7
    for s in subs:
        assert len(s["text"].split()) <= SUBTITLE_MAX_WORDS


def test_build_subtitles_punctuation_boundary():
    """Verify that sentence-ending punctuation flushes immediately even if under word limit."""
    words = [
        ("Hello.", 0.0, 0.5),
        ("This", 0.6, 0.9),
        ("is", 1.0, 1.2),
        ("a", 1.3, 1.4),
        ("test.", 1.5, 2.0),
        ("Done!", 2.1, 2.5),
    ]
    timing = _make_timing(words)
    subs = build_subtitles(timing)
    assert len(subs) == 3
    assert subs[0]["text"] == "Hello."
    assert subs[1]["text"] == "This is a test."
    assert subs[2]["text"] == "Done!"


def test_build_subtitles_duration_boundary():
    """Verify that caption splits when duration exceeds SUBTITLE_MAX_SEC (3.5s)."""
    words = [
        ("Slow", 0.0, 1.8),
        ("spoken", 1.8, 3.7),  # span = 3.7 - 0.0 = 3.7s > 3.5s
        ("words", 3.8, 4.5),
    ]
    timing = _make_timing(words)
    subs = build_subtitles(timing)
    assert len(subs) == 2
    assert subs[0]["text"] == "Slow"
    assert subs[1]["text"] == "spoken words"


def test_build_subtitles_final_partial_caption():
    """Verify that leftover words at the end are properly preserved."""
    words = [
        ("One", 0.0, 0.3),
        ("two", 0.3, 0.6),
        ("three", 0.6, 0.9),
    ]
    timing = _make_timing(words)
    subs = build_subtitles(timing)
    assert len(subs) == 1
    assert subs[0]["text"] == "One two three"


def test_escape_ass_text_comprehensive():
    """Verify ASS text escaping handles all edge cases safely."""
    # Normal text
    assert escape_ass_text("Simple text") == "Simple text"

    # Braces (ASS override delimiters) converted to proportional small brackets
    escaped_braces = escape_ass_text("{quoted text}")
    assert "{" not in escaped_braces and "}" not in escaped_braces
    assert escaped_braces == "\ufe5bquoted text\ufe5c"

    # Backslashes before regular characters stay literal
    escaped_bs = escape_ass_text("Path\\to\\file")
    assert escaped_bs == "Path\\to\\file"

    # Backslashes before N/n/h are protected with zero-width space to prevent accidental ASS breaks
    escaped_n = escape_ass_text("Step \\Notes and \\help")
    assert "\\\u200bNotes" in escaped_n
    assert "\\\u200bhelp" in escaped_n

    # Newlines converted to \N
    assert escape_ass_text("Line 1\nLine 2\r\nLine 3") == "Line 1\\NLine 2\\NLine 3"

    # Vietnamese Unicode preserved perfectly
    vi_text = "Sự sụp đổ của Bức tường Berlin năm 1989"
    assert escape_ass_text(vi_text) == vi_text

    # English punctuation, quotes, colon
    eng_text = "Breaking: \"The wall is open!\", said the official."
    assert escape_ass_text(eng_text) == eng_text

    # Empty / None handling
    assert escape_ass_text("") == ""
    assert escape_ass_text(None) == ""
