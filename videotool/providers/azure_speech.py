"""Azure Speech TTS integration with word-boundary timestamp extraction and caching.

Provides real speech synthesis via Azure Cognitive Services Speech SDK,
extracts word-level / syllable-level alignment, and caches synthesis artifacts
to prevent redundant API billing.
"""
from __future__ import annotations

import json
import os
import shutil
import wave
from pathlib import Path
from typing import Any

from videotool.domain.narration import Narration, NarrationAudio, WordTiming
from videotool.domain.timing import NarrationTiming
from videotool.pipeline.fingerprints import stable_hash


def _get_azure_credentials() -> tuple[str, str]:
    """Retrieve Azure Speech credentials from environment variables."""
    key = os.environ.get("AZURE_SPEECH_KEY", "").strip()
    region = os.environ.get("AZURE_SPEECH_REGION", "").strip()
    if not key or not region:
        raise ValueError(
            "Azure Speech credentials missing: Please set AZURE_SPEECH_KEY "
            "and AZURE_SPEECH_REGION environment variables."
        )
    return key, region


def synthesize_azure_speech(
    narration: Narration,
    voice: str = "vi-VN-HoaiMyNeural",
    cache_dir: str | Path | None = None,
) -> tuple[Path, NarrationTiming]:
    """Synthesize speech using Azure Cognitive Services Speech SDK with local cache.

    Returns:
        (audio_wav_path, narration_timing)
    """
    cache_root = Path(cache_dir or "artifacts/tts_cache").resolve()
    cache_root.mkdir(parents=True, exist_ok=True)

    text = narration.text.strip()
    lang = narration.language or ("vi" if voice.startswith("vi") else "en")

    cache_key = stable_hash("azure_speech_v1", voice, text, lang)
    cached_wav = cache_root / f"{cache_key}.wav"
    cached_json = cache_root / f"{cache_key}.json"

    # 1. Return cached synthesis if present
    if cached_wav.exists() and cached_json.exists():
        try:
            meta = json.loads(cached_json.read_text(encoding="utf-8"))
            timing = NarrationTiming.from_dict(meta["timing"])
            return cached_wav, timing
        except Exception:
            pass  # Corrupt cache -> recompute

    # 2. Invoke Azure Speech SDK
    key, region = _get_azure_credentials()

    try:
        import azure.cognitiveservices.speech as speechsdk
    except ImportError as err:
        raise ImportError(
            "azure-cognitiveservices-speech is required for Azure Speech TTS. "
            "Please install it via `pip install azure-cognitiveservices-speech`."
        ) from err

    speech_config = speechsdk.SpeechConfig(subscription=key, region=region)
    speech_config.speech_synthesis_voice_name = voice
    speech_config.set_speech_synthesis_output_format(
        speechsdk.SpeechSynthesisOutputFormat.Riff48Khz16BitMonoPcm
    )

    collected_events: list[dict[str, Any]] = []

    def on_word_boundary(evt: speechsdk.SpeechSynthesisWordBoundaryEventArgs):
        # 0 = Word, 1 = Punctuation, 2 = Sentence
        b_type = getattr(evt.boundary_type, "value", evt.boundary_type)
        if b_type == 0:  # Word boundary
            offset_sec = evt.audio_offset / 10_000_000.0
            if hasattr(evt.duration, "total_seconds"):
                dur_sec = evt.duration.total_seconds()
            elif isinstance(evt.duration, (int, float)):
                dur_sec = evt.duration / 10_000_000.0
            else:
                dur_sec = 0.25

            collected_events.append({
                "text": evt.text,
                "start_sec": round(offset_sec, 3),
                "end_sec": round(offset_sec + max(0.05, dur_sec), 3),
            })

    audio_config = speechsdk.audio.AudioOutputConfig(filename=str(cached_wav))
    synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config)
    synthesizer.synthesis_word_boundary.connect(on_word_boundary)

    result = synthesizer.speak_text_async(text).get()

    if result.reason != speechsdk.ResultReason.SynthesizingAudioCompleted:
        err_details = getattr(result, "error_details", str(result.reason))
        raise RuntimeError(f"Azure Speech synthesis failed: {result.reason} ({err_details})")

    # Read exact audio duration from WAV header
    with wave.open(str(cached_wav), "rb") as wf:
        total_frames = wf.getnframes()
        frame_rate = wf.getframerate()
        exact_duration = round(total_frames / float(frame_rate), 3)

    # Build WordTiming tuple
    words: list[WordTiming] = []
    for i, ev in enumerate(collected_events):
        words.append(WordTiming(
            index=i,
            text=ev["text"],
            start_sec=ev["start_sec"],
            end_sec=min(exact_duration, ev["end_sec"]),
        ))

    # If word boundaries were not received, fallback to even spacing
    if not words and text:
        from videotool.domain.narration import synthetic_word_timings
        words = list(synthetic_word_timings(text, exact_duration))

    timing = NarrationTiming(
        words=tuple(words),
        duration_sec=exact_duration,
        source="azure_speech_tts",
        provider="azure_speech",
        provider_version=1,
        is_estimated=False,
    )

    # Save cache metadata
    cached_json.write_text(
        json.dumps({
            "cache_key": cache_key,
            "voice": voice,
            "language": lang,
            "timing": timing.to_dict(),
        }, indent=2),
        encoding="utf-8"
    )

    return cached_wav, timing


class AzureSpeechAudioProvider:
    """Production audio provider using Azure Cognitive Services Speech TTS."""
    provider_id: str = "azure_speech"
    provider_version: int = 1
    is_placeholder: bool = False

    def __init__(self, voice: str = "vi-VN-HoaiMyNeural", cache_dir: str | Path | None = None):
        self.voice = voice
        self.cache_dir = cache_dir

    def synthesize(self, narration: Narration, timing: NarrationTiming,
                   out_path: Path, timeline: dict | None = None) -> NarrationAudio:
        """Synthesize real speech audio and copy to out_path."""
        out_path = Path(out_path).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)

        cached_wav, azure_timing = synthesize_azure_speech(
            narration=narration,
            voice=self.voice,
            cache_dir=self.cache_dir,
        )

        if cached_wav != out_path:
            shutil.copyfile(cached_wav, out_path)

        with wave.open(str(out_path), "rb") as wf:
            sample_rate = wf.getframerate()
            channels = wf.getnchannels()
            exact_duration = round(wf.getnframes() / float(sample_rate), 3)

        return NarrationAudio(
            audio_path=out_path,
            duration_sec=exact_duration,
            sample_rate=sample_rate,
            channels=channels,
            provider=self.provider_id,
            provider_version=self.provider_version,
            is_placeholder=False,
        )


class AzureSpeechTimingProvider:
    """Production timing provider using Azure Cognitive Services Speech TTS word boundaries."""
    provider_id: str = "azure_speech"
    provider_version: int = 1

    def __init__(self, voice: str = "vi-VN-HoaiMyNeural", cache_dir: str | Path | None = None):
        self.voice = voice
        self.cache_dir = cache_dir

    def align(self, narration: Narration) -> NarrationTiming:
        """Align narration words by synthesizing with Azure Speech and extracting word boundaries."""
        _, timing = synthesize_azure_speech(
            narration=narration,
            voice=self.voice,
            cache_dir=self.cache_dir,
        )
        return timing
