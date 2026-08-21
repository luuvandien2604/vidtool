"""Unit and live integration tests for Azure Speech TTS provider."""
from __future__ import annotations

import os
from pathlib import Path
import pytest

from videotool.domain.narration import Narration
from videotool.providers.audio import AzureSpeechAudioProvider, build_audio_provider
from videotool.providers.azure_speech import _get_azure_credentials, synthesize_azure_speech
from videotool.providers.timing import AzureSpeechTimingProvider, build_timing_provider


def test_azure_speech_missing_credentials_raises(monkeypatch):
    """Verify that missing environment variables raise a clear ValueError specifying the exact variable names."""
    monkeypatch.delenv("AZURE_SPEECH_KEY", raising=False)
    monkeypatch.delenv("AZURE_SPEECH_REGION", raising=False)
    # Prevent local .env on disk from supplying credentials during this unit test
    monkeypatch.setattr("videotool.providers.azure_speech.Path.is_file", lambda self: False)

    with pytest.raises(ValueError, match="AZURE_SPEECH_KEY and AZURE_SPEECH_REGION"):
        _get_azure_credentials()


def test_azure_speech_providers_registered():
    """Verify registry lookups for azure audio and timing providers."""
    audio_prov = build_audio_provider("azure", voice="vi-VN-HoaiMyNeural")
    assert isinstance(audio_prov, AzureSpeechAudioProvider)
    assert audio_prov.provider_id == "azure_speech"
    assert audio_prov.is_placeholder is False

    timing_prov = build_timing_provider("azure", voice="vi-VN-HoaiMyNeural")
    assert isinstance(timing_prov, AzureSpeechTimingProvider)
    assert timing_prov.provider_id == "azure_speech"


@pytest.mark.live_tts
def test_azure_speech_live_synthesis(tmp_path, monkeypatch):
    """Opt-in live synthesis test: verifies real Azure Speech audio and word boundaries.

    Excluded from default suite; runs only when AZURE_SPEECH_KEY is set and --live-tts is requested.
    """
    try:
        key, region = _get_azure_credentials()
    except Exception:
        pytest.skip("AZURE_SPEECH_KEY or AZURE_SPEECH_REGION not set in environment or .env")

    narration = Narration(
        text="Tháng mười một năm 1989, bức tường sụp đổ.",
        language="vi",
    )
    cache_dir = tmp_path / "tts_cache"
    wav_path, timing = synthesize_azure_speech(
        narration=narration,
        voice="vi-VN-HoaiMyNeural",
        cache_dir=cache_dir,
    )

    assert wav_path.exists()
    assert wav_path.stat().st_size > 1000
    assert timing.duration_sec > 1.0
    assert len(timing.words) > 0
    assert timing.provider == "azure_speech"
    assert timing.is_estimated is False

    # Second call should hit cache without network error
    wav_cached, timing_cached = synthesize_azure_speech(
        narration=narration,
        voice="vi-VN-HoaiMyNeural",
        cache_dir=cache_dir,
    )
    assert wav_cached == wav_path
    assert timing_cached.duration_sec == timing.duration_sec
