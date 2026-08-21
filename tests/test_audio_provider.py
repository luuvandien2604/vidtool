"""Pure-Python unit tests for NarrationAudio and audio providers (no FFmpeg required)."""
from __future__ import annotations

import struct
import tempfile
import wave
from pathlib import Path

import pytest

from videotool.domain.narration import Narration, NarrationAudio, WordTiming
from videotool.domain.timing import NarrationTiming
from videotool.providers.audio import (AUDIO_PROVIDERS,
                                       SyntheticSilenceAudioProvider,
                                       build_audio_provider,
                                       register_audio_provider)


def _make_timing(duration_sec: float) -> tuple[Narration, NarrationTiming]:
    words = (
        WordTiming(index=0, text="Hello", start_sec=0.0, end_sec=duration_sec / 2),
        WordTiming(index=1, text="world", start_sec=duration_sec / 2, end_sec=duration_sec),
    )
    narration = Narration(text="Hello world", words=words)
    timing = NarrationTiming(
        words=words,
        duration_sec=duration_sec,
        source="test",
        provider="deterministic",
        provider_version=1,
        is_estimated=False,
    )
    return narration, timing


def test_synthetic_silence_exact_duration():
    """Verify that SyntheticSilenceAudioProvider generates WAV files with exact sample counts."""
    provider = SyntheticSilenceAudioProvider(sample_rate=48000, channels=1)

    with tempfile.TemporaryDirectory() as tmp_dir:
        for test_dur in (0.5, 3.125, 10.0, 66.2):
            out_path = Path(tmp_dir) / f"silence_{test_dur}.wav"
            narration, timing = _make_timing(test_dur)

            audio = provider.synthesize(narration, timing, out_path)

            assert audio.audio_path == out_path
            assert audio.duration_sec == test_dur
            assert audio.sample_rate == 48000
            assert audio.channels == 1
            assert audio.is_placeholder is True
            assert audio.provider == "synthetic_silence"

            with wave.open(str(out_path), "rb") as wf:
                assert wf.getnchannels() == 1
                assert wf.getsampwidth() == 2
                assert wf.getframerate() == 48000
                expected_frames = int(round(test_dur * 48000))
                assert wf.getnframes() == expected_frames


def test_synthetic_silence_determinism():
    """Verify byte-level determinism: identical inputs produce identical WAV files."""
    provider = SyntheticSilenceAudioProvider(sample_rate=48000, channels=1)
    narration, timing = _make_timing(5.0)

    with tempfile.TemporaryDirectory() as tmp_dir:
        path1 = Path(tmp_dir) / "run1.wav"
        path2 = Path(tmp_dir) / "run2.wav"

        provider.synthesize(narration, timing, path1)
        provider.synthesize(narration, timing, path2)

        assert path1.read_bytes() == path2.read_bytes()


def test_synthetic_silence_click_track():
    """Verify click track mode emits non-zero audio pulses at beat boundaries and silence elsewhere."""
    provider = SyntheticSilenceAudioProvider(sample_rate=48000, channels=1, click_track=True)
    narration, timing = _make_timing(10.0)
    timeline = {
        "segments": [
            {"beat_id": "b1", "start_sec": 0.0, "end_sec": 4.0},
            {"beat_id": "b2", "start_sec": 4.0, "end_sec": 7.5},
            {"beat_id": "b3", "start_sec": 7.5, "end_sec": 10.0},
        ]
    }

    with tempfile.TemporaryDirectory() as tmp_dir:
        out_path = Path(tmp_dir) / "clicks.wav"
        audio = provider.synthesize(narration, timing, out_path, timeline=timeline)

        assert audio.is_placeholder is True

        with wave.open(str(out_path), "rb") as wf:
            raw_frames = wf.readframes(wf.getnframes())

        num_samples = len(raw_frames) // 2
        samples = struct.unpack(f"<{num_samples}h", raw_frames)

        # Beat 1 start (t=0.0s -> sample 0 to ~2400) should have audible non-zero samples
        beat1_samples = samples[10:100]
        assert any(s != 0 for s in beat1_samples), "Beat 1 click tone missing"

        # Silent middle region (e.g. t=2.0s -> sample 96000) should be strictly 0
        silence_region = samples[95000:97000]
        assert all(s == 0 for s in silence_region), "Expected pure silence between beats"

        # Beat 2 start (t=4.0s -> sample 192000) should have audible non-zero samples
        beat2_samples = samples[192010:192100]
        assert any(s != 0 for s in beat2_samples), "Beat 2 click tone missing"


def test_audio_provider_registry():
    """Verify registry lookup and error handling."""
    prov = build_audio_provider("silence")
    assert isinstance(prov, SyntheticSilenceAudioProvider)
    assert prov.click_track is False

    prov_click = build_audio_provider("silence", click_track=True)
    assert prov_click.click_track is True

    with pytest.raises(KeyError, match="unknown audio provider 'nonexistent'"):
        build_audio_provider("nonexistent")


def test_narration_audio_domain_model():
    """Verify serialization, deserialization, and load-bearing is_placeholder flag."""
    audio = NarrationAudio(
        audio_path=Path("/tmp/test.wav"),
        duration_sec=12.34,
        sample_rate=48000,
        channels=1,
        provider="synthetic_silence",
        provider_version=1,
        is_placeholder=True,
    )

    d = audio.to_dict()
    assert d["audio_path"] == "/tmp/test.wav"
    assert d["duration_sec"] == 12.34
    assert d["is_placeholder"] is True

    restored = NarrationAudio.from_dict(d)
    assert restored == audio
    assert restored.is_placeholder is True
