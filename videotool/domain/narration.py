"""Narration and word-level timing models.

The pipeline is narration-driven: every downstream planning stage is anchored
to these timings. Timing data normally comes from the TTS stage; in Phase 1
fixtures provide deterministic synthetic timings.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class WordTiming:
    index: int
    text: str
    start_sec: float
    end_sec: float

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "text": self.text,
            "start_sec": self.start_sec,
            "end_sec": self.end_sec,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "WordTiming":
        return cls(**d)


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
