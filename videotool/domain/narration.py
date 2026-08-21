"""Narration and word-level timing models.

The pipeline is narration-driven: every downstream planning stage is anchored
to these timings. Timing data normally comes from the TTS stage; in Phase 1
fixtures provide deterministic synthetic timings.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class NarrationAudio:
    """Synthesized or placeholder audio file for episode narration.

    The ``is_placeholder`` flag is load-bearing: downstream stages and renderers
    must not treat placeholder audio as final production speech.
    """
    audio_path: Path
    duration_sec: float
    sample_rate: int
    channels: int
    provider: str
    provider_version: int
    is_placeholder: bool = False

    def to_dict(self) -> dict:
        return {
            "audio_path": str(self.audio_path),
            "duration_sec": self.duration_sec,
            "sample_rate": self.sample_rate,
            "channels": self.channels,
            "provider": self.provider,
            "provider_version": self.provider_version,
            "is_placeholder": self.is_placeholder,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "NarrationAudio":
        return cls(
            audio_path=Path(d["audio_path"]),
            duration_sec=float(d["duration_sec"]),
            sample_rate=int(d.get("sample_rate", 48000)),
            channels=int(d.get("channels", 1)),
            provider=d.get("provider", "unknown"),
            provider_version=int(d.get("provider_version", 1)),
            is_placeholder=bool(d.get("is_placeholder", False)),
        )


@dataclass(frozen=True)
class WordTiming:
    index: int
    text: str
    start_sec: float
    end_sec: float
    confidence: float = 1.0

    @property
    def word(self) -> str:
        """Canonical spoken token name; ``text`` remains backward compatible."""
        return self.text

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "text": self.text,
            "start_sec": self.start_sec,
            "end_sec": self.end_sec,
            "confidence": self.confidence,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "WordTiming":
        payload = dict(d)
        if "text" not in payload and "word" in payload:
            payload["text"] = payload.pop("word")
        payload.setdefault("confidence", 1.0)
        return cls(**payload)


@dataclass(frozen=True)
class Narration:
    text: str
    words: tuple[WordTiming, ...] = field(default_factory=tuple)
    language: str = "en"

    @property
    def duration_sec(self) -> float:
        if not self.words:
            return 0.0
        return self.words[-1].end_sec

    def words_in_range(self, start_sec: float, end_sec: float) -> list[WordTiming]:
        return [w for w in self.words if w.end_sec > start_sec and w.start_sec < end_sec]

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "language": self.language,
            "words": [w.to_dict() for w in self.words],
            "duration_sec": self.duration_sec,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Narration":
        return cls(
            text=d["text"],
            words=tuple(WordTiming.from_dict(w) for w in d.get("words", [])),
            language=d.get("language", "en"),
        )


def synthetic_word_timings(text: str, wps: float = 2.6, comma_pause: float = 0.28,
                           sentence_pause: float = 0.55) -> tuple[WordTiming, ...]:
    """Deterministic pseudo-TTS timings so fixtures need no TTS engine.

    Word duration scales with character length; punctuation adds trailing
    silence. Deterministic: same text always yields the same timings.
    """
    tokens: list[str] = text.split()
    words: list[WordTiming] = []
    t = 0.0
    for i, tok in enumerate(tokens):
        dur = max(0.14, (0.20 + 0.028 * len(tok.strip(".,;:!?\"'"))) * (2.6 / wps))
        start = t
        t += dur
        pause = 0.0
        if tok.endswith((",", ";", ":")):
            pause = comma_pause
        elif tok.endswith((".", "!", "?")):
            pause = sentence_pause
        t += pause
        words.append(WordTiming(index=i, text=tok, start_sec=round(start, 3),
                                end_sec=round(t, 3)))
    return tuple(words)
