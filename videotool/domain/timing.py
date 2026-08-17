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
