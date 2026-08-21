"""Pure-Python unit tests for speech pacing and rhythm auditor."""
from __future__ import annotations

import pytest

from videotool.domain.narration import WordTiming
from videotool.domain.timing import NarrationTiming
from videotool.editorial.pacing import audit_speech_pacing


def _make_timing(words_data: list[tuple[str, float, float]]) -> NarrationTiming:
    words = tuple(
        WordTiming(index=i, text=text, start_sec=start, end_sec=end)
        for i, (text, start, end) in enumerate(words_data)
    )
    duration = words[-1].end_sec if words else 0.0
    return NarrationTiming(
        words=words,
        duration_sec=duration,
        source="test",
        provider="test",
        provider_version=1,
    )


def test_pacing_optimal_english():
    """Verify optimal English narration pacing calculation."""
    # 6 words in 2.0s = 3.0 WPS (optimal for English 2.0 - 3.4)
    words_data = [
        ("The", 0.1, 0.3),
        ("Berlin", 0.4, 0.7),
        ("Wall", 0.8, 1.1),
        ("fell", 1.2, 1.4),
        ("in", 1.5, 1.6),
        ("autumn", 1.7, 1.9),
    ]
    timing = _make_timing(words_data)
    timeline = {
        "episode_id": "test_ep",
        "total_duration_sec": 2.0,
        "segments": [
            {"beat_id": "b1", "start_sec": 0.0, "end_sec": 2.0},
        ],
    }

    report = audit_speech_pacing(timeline, timing, language="en")
    assert report.total_tokens == 6
    assert report.avg_token_rate == 3.0
    assert report.beat_metrics[0].status == "OPTIMAL"
    assert report.cut_alignment_score == 1.0
    assert report.overall_pacing_score == 1.0


def test_pacing_vietnamese_syllables():
    """Verify Vietnamese speech pacing using SPS (Syllables Per Second)."""
    # 8 syllables in 2.0s = 4.0 SPS (optimal for Vietnamese 2.4 - 4.8 SPS)
    words_data = [
        ("Bức", 0.1, 0.3),
        ("tường", 0.35, 0.55),
        ("Béc", 0.6, 0.8),
        ("lin", 0.85, 1.05),
        ("đã", 1.1, 1.25),
        ("sụp", 1.3, 1.45),
        ("đổ", 1.5, 1.65),
        ("xuống", 1.7, 1.9),
    ]
    timing = _make_timing(words_data)
    timeline = {
        "episode_id": "test_vi",
        "total_duration_sec": 2.0,
        "segments": [
            {"beat_id": "b1", "start_sec": 0.0, "end_sec": 2.0},
        ],
    }

    report = audit_speech_pacing(timeline, timing, language="vi")
    assert report.total_tokens == 8
    assert report.avg_token_rate == 4.0
    assert report.beat_metrics[0].status == "OPTIMAL"


def test_pacing_rushed_and_dragging_detection():
    """Verify detection of rushed and dragging speech density."""
    words_data = [
        # Beat 1: Rushed (10 syllables in 1.5s = 6.67 SPS > 5.2)
        ("Một", 0.1, 0.2), ("hai", 0.2, 0.3), ("ba", 0.3, 0.4), ("bốn", 0.4, 0.5),
        ("năm", 0.5, 0.6), ("sáu", 0.6, 0.7), ("bảy", 0.7, 0.8), ("tám", 0.8, 0.9),
        ("chín", 0.9, 1.0), ("mười", 1.0, 1.2),
        # Beat 2: Dragging (1 syllable in 2.0s = 0.5 SPS < 1.8)
        ("Xong", 2.0, 2.3),
    ]
    timing = _make_timing(words_data)
    timeline = {
        "episode_id": "test_anomaly",
        "total_duration_sec": 3.5,
        "segments": [
            {"beat_id": "b1", "start_sec": 0.0, "end_sec": 1.5},
            {"beat_id": "b2", "start_sec": 1.5, "end_sec": 3.5},
        ],
    }

    report = audit_speech_pacing(timeline, timing, language="vi")
    assert report.beat_metrics[0].status == "RUSHED"
    assert report.beat_metrics[1].status == "DRAGGING"
    assert report.overall_pacing_score < 1.0


def test_pacing_mid_word_cut_detection():
    """Verify warning when a visual beat cuts through the middle of a spoken word."""
    words_data = [
        ("WordOne", 0.0, 1.0),
        # Word spans from 1.5s to 2.5s, while beat 1 ends at 2.0s (mid-word cut)
        ("StraddlingWord", 1.5, 2.5),
        ("WordThree", 2.6, 3.0),
    ]
    timing = _make_timing(words_data)
    timeline = {
        "episode_id": "test_cut",
        "total_duration_sec": 3.0,
        "segments": [
            {"beat_id": "b1", "start_sec": 0.0, "end_sec": 2.0},
            {"beat_id": "b2", "start_sec": 2.0, "end_sec": 3.0},
        ],
    }

    report = audit_speech_pacing(timeline, timing, language="en")
    assert any("cuts through a spoken word" in w for w in report.beat_metrics[0].warnings)
    assert report.cut_alignment_score < 1.0
