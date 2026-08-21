"""Narration audio provider abstraction and deterministic placeholder provider.

Audio synthesis is a render-time concern: this module establishes the provider
seam, exact duration matching against NarrationTiming, and load-bearing
placeholder provenance.
"""
from __future__ import annotations

import math
import struct
import wave
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from videotool.domain.narration import Narration, NarrationAudio
from videotool.domain.timing import NarrationTiming

if TYPE_CHECKING:
    pass


class NarrationAudioProvider(Protocol):
    """Protocol for narration audio synthesis providers (placeholder or real TTS)."""
    provider_id: str
    provider_version: int

    def synthesize(self, narration: Narration, timing: NarrationTiming,
                   out_path: Path, timeline: dict | None = None) -> NarrationAudio:
        """Synthesize audio matching the timing duration and write to out_path."""
        ...


class SyntheticSilenceAudioProvider:
    """Pure-Python deterministic placeholder audio provider.

    Generates a WAV file with exact duration matching `timing.duration_sec`.
    Default content is silence; optional `click_track=True` emits an audible
    880 Hz tone at each beat boundary.
    """
    provider_id: str = "synthetic_silence"
    provider_version: int = 1
    is_placeholder: bool = True

    def __init__(self, sample_rate: int = 48000, channels: int = 1,
                 sample_width: int = 2, click_track: bool = False):
        self.sample_rate = sample_rate
        self.channels = channels
        self.sample_width = sample_width  # 2 bytes = 16-bit PCM
        self.click_track = click_track

    def synthesize(self, narration: Narration, timing: NarrationTiming,
                   out_path: Path, timeline: dict | None = None) -> NarrationAudio:
        """Generate a deterministic WAV audio file of exact duration."""
        out_path = Path(out_path).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)

        duration_sec = float(timing.duration_sec)
        total_samples = int(round(duration_sec * self.sample_rate))

        # 16-bit signed PCM buffer (initialized to silence)
        buffer = bytearray(total_samples * self.sample_width * self.channels)

        if self.click_track:
            beat_starts: list[float] = []
            if timeline and "segments" in timeline:
                beat_starts = [float(s["start_sec"]) for s in timeline["segments"]]
            elif narration.words:
                beat_starts = [0.0]

            tone_freq = 880.0  # A5 note
            tone_dur_sec = 0.05  # 50ms pulse
            tone_samples = int(round(tone_dur_sec * self.sample_rate))
            amplitude = 6000  # ~18% full scale (clean and audible)

            for b_start in beat_starts:
                start_sample = int(round(b_start * self.sample_rate))
                if start_sample >= total_samples:
                    continue
                pulse_len = min(tone_samples, total_samples - start_sample)
                for k in range(pulse_len):
                    idx = start_sample + k
                    val = int(amplitude * math.sin(2.0 * math.pi * tone_freq * (k / self.sample_rate)))
                    struct.pack_into("<h", buffer, idx * self.sample_width, val)

        # Write WAV file using standard library wave module
        with wave.open(str(out_path), "wb") as wav_file:
            wav_file.setnchannels(self.channels)
            wav_file.setsampwidth(self.sample_width)
            wav_file.setframerate(self.sample_rate)
            wav_file.writeframes(buffer)

        return NarrationAudio(
            audio_path=out_path,
            duration_sec=duration_sec,
            sample_rate=self.sample_rate,
            channels=self.channels,
            provider=self.provider_id,
            provider_version=self.provider_version,
            is_placeholder=True,
        )


AUDIO_PROVIDERS: dict[str, type] = {}


def register_audio_provider(name: str, cls: type) -> None:
    """Register an audio provider implementation under a canonical name."""
    AUDIO_PROVIDERS[name] = cls


# Register standard silence provider
register_audio_provider("silence", SyntheticSilenceAudioProvider)


def build_audio_provider(name: str, **kwargs) -> NarrationAudioProvider:
    """Build an audio provider instance from registry."""
    if name not in AUDIO_PROVIDERS:
        raise KeyError(
            f"unknown audio provider '{name}' (have: {sorted(AUDIO_PROVIDERS)})"
        )
    return AUDIO_PROVIDERS[name](**kwargs)
