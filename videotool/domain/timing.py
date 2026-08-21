"""Renderer-independent narration alignment and semantic timing models."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .narration import WordTiming


class AnchorType(str, Enum):
    ENTITY_MENTION = "ENTITY_MENTION"
    LOCATION_MENTION = "LOCATION_MENTION"
    DATE_MENTION = "DATE_MENTION"
    EVENT_MENTION = "EVENT_MENTION"
    NUMBER_MENTION = "NUMBER_MENTION"
    QUOTE_MENTION = "QUOTE_MENTION"
    RELATIONSHIP = "RELATIONSHIP"
    CAUSE = "CAUSE"
    EFFECT = "EFFECT"
    CONTRAST = "CONTRAST"
    REVEAL = "REVEAL"
    EMPHASIS = "EMPHASIS"


@dataclass(frozen=True)
class NarrationTiming:
    words: tuple[WordTiming, ...]
    duration_sec: float
    source: str
    provider: str
    provider_version: int
    is_estimated: bool = False

    def to_dict(self) -> dict:
        return {"words": [w.to_dict() for w in self.words],
                "duration_sec": self.duration_sec, "source": self.source,
                "provider": self.provider,
                "provider_version": self.provider_version,
                "is_estimated": self.is_estimated}

    @classmethod
    def from_dict(cls, d: dict) -> "NarrationTiming":
        return cls(words=tuple(WordTiming.from_dict(w)
                               for w in d.get("words", [])),
                   duration_sec=float(d.get("duration_sec", 0.0)),
                   source=d.get("source", "unknown"),
                   provider=d.get("provider", "unknown"),
                   provider_version=int(d.get("provider_version", 0)),
                   is_estimated=bool(d.get("is_estimated", False)))


@dataclass
class SemanticAnchor:
    anchor_id: str
    beat_id: str
    anchor_type: AnchorType
    text: str
    normalized_terms: list[str]
    start_sec: float
    end_sec: float
    word_start: int
    word_end: int
    entity_ids: list[str] = field(default_factory=list)
    location_ids: list[str] = field(default_factory=list)
    event_ids: list[str] = field(default_factory=list)
    relationship_ids: list[str] = field(default_factory=list)
    importance: float = 0.5
    resolution_source: str = "exact_phrase"
    confidence: float = 1.0

    def to_dict(self) -> dict:
        payload = self.__dict__.copy()
        payload["anchor_type"] = self.anchor_type.value
        return payload

    @classmethod
    def from_dict(cls, d: dict) -> "SemanticAnchor":
        payload = dict(d)
        payload["anchor_type"] = AnchorType(payload["anchor_type"])
        return cls(**payload)


@dataclass
class TimingBinding:
    binding_id: str
    beat_id: str
    composition_id: str
    layer_id: str
    semantic_refs: list[str]
    anchor_id: str | None
    start_sec: float
    end_sec: float
    source: str
    confidence: float
    reason: str

    def to_dict(self) -> dict:
        return self.__dict__.copy()

    @classmethod
    def from_dict(cls, d: dict) -> "TimingBinding":
        return cls(**d)


@dataclass(frozen=True)
class BeatPacingMetric:
    """Pacing metrics for a single visual beat.

    Note on Units:
    - For English: `token_rate` represents WPS (Words Per Second).
    - For Vietnamese: `token_rate` represents SPS (Syllables Per Second / Tiếng mỗi giây),
      as TTS word-boundary tokens correspond to individual spoken syllables.
    - `char_rate` represents CPS (Characters Per Second) for subtitle readability.
    """
    beat_id: str
    duration_sec: float
    token_count: int
    token_rate: float
    char_count: int
    char_rate: float
    pause_gap_before_sec: float
    pause_gap_after_sec: float
    status: str  # "OPTIMAL", "RUSHED", "DRAGGING", "SUBTITLE_TOO_FAST"
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "beat_id": self.beat_id,
            "duration_sec": self.duration_sec,
            "token_count": self.token_count,
            "token_rate": self.token_rate,
            "char_count": self.char_count,
            "char_rate": self.char_rate,
            "pause_gap_before_sec": self.pause_gap_before_sec,
            "pause_gap_after_sec": self.pause_gap_after_sec,
            "status": self.status,
            "warnings": list(self.warnings),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "BeatPacingMetric":
        return cls(
            beat_id=d["beat_id"],
            duration_sec=float(d["duration_sec"]),
            token_count=int(d["token_count"]),
            token_rate=float(d["token_rate"]),
            char_count=int(d["char_count"]),
            char_rate=float(d["char_rate"]),
            pause_gap_before_sec=float(d.get("pause_gap_before_sec", 0.0)),
            pause_gap_after_sec=float(d.get("pause_gap_after_sec", 0.0)),
            status=d.get("status", "OPTIMAL"),
            warnings=list(d.get("warnings", [])),
        )


@dataclass(frozen=True)
class PacingReport:
    """Complete episode speech pacing and rhythm audit report."""
    episode_id: str
    language: str
    total_duration_sec: float
    total_tokens: int
    avg_token_rate: float
    avg_char_rate: float
    beat_metrics: list[BeatPacingMetric] = field(default_factory=list)
    cut_alignment_score: float = 1.0  # Fraction of cuts landing on natural speech pauses
    overall_pacing_score: float = 1.0
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "episode_id": self.episode_id,
            "language": self.language,
            "total_duration_sec": self.total_duration_sec,
            "total_tokens": self.total_tokens,
            "avg_token_rate": self.avg_token_rate,
            "avg_char_rate": self.avg_char_rate,
            "beat_metrics": [m.to_dict() for m in self.beat_metrics],
            "cut_alignment_score": self.cut_alignment_score,
            "overall_pacing_score": self.overall_pacing_score,
            "warnings": list(self.warnings),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "PacingReport":
        return cls(
            episode_id=d["episode_id"],
            language=d.get("language", "en"),
            total_duration_sec=float(d.get("total_duration_sec", 0.0)),
            total_tokens=int(d.get("total_tokens", 0)),
            avg_token_rate=float(d.get("avg_token_rate", 0.0)),
            avg_char_rate=float(d.get("avg_char_rate", 0.0)),
            beat_metrics=[BeatPacingMetric.from_dict(m) for m in d.get("beat_metrics", [])],
            cut_alignment_score=float(d.get("cut_alignment_score", 1.0)),
            overall_pacing_score=float(d.get("overall_pacing_score", 1.0)),
            warnings=list(d.get("warnings", [])),
        )
