"""SemanticBeat: the smallest narration unit that drives a visual decision.

A beat is NOT a scene. A scene may contain many beats. Beats are derived from
narration meaning + word timing, not from a fixed scene count.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


SEMANTIC_BEAT_IDENTITY_VERSION = 1


class SemanticFunction(str, Enum):
    HOOK = "HOOK"
    ESTABLISHING_CONTEXT = "ESTABLISHING_CONTEXT"
    CHARACTER_INTRODUCTION = "CHARACTER_INTRODUCTION"
    LOCATION_INTRODUCTION = "LOCATION_INTRODUCTION"
    CHRONOLOGY = "CHRONOLOGY"
    CAUSAL_EXPLANATION = "CAUSAL_EXPLANATION"
    EVIDENCE = "EVIDENCE"
    COMPARISON = "COMPARISON"
    PROCESS = "PROCESS"
    TECHNICAL_EXPLANATION = "TECHNICAL_EXPLANATION"
    ESCALATION = "ESCALATION"
    TURNING_POINT = "TURNING_POINT"
    CONSEQUENCE = "CONSEQUENCE"
    QUOTE = "QUOTE"
    DATA = "DATA"
    GEOGRAPHIC_MOVEMENT = "GEOGRAPHIC_MOVEMENT"
    ATMOSPHERE = "ATMOSPHERE"
    REVEAL = "REVEAL"
    TRANSITION = "TRANSITION"
    SUMMARY = "SUMMARY"


@dataclass
class SemanticBeat:
    beat_id: str
    start_sec: float
    end_sec: float
    narration_text: str
    word_start: int  # inclusive index into Narration.words
    word_end: int    # exclusive index into Narration.words
    semantic_function: SemanticFunction
    visual_intent: str
    entities: list[str] = field(default_factory=list)
    locations: list[str] = field(default_factory=list)
    dates: list[str] = field(default_factory=list)
    events: list[str] = field(default_factory=list)
    objects: list[str] = field(default_factory=list)
    relationships: list[str] = field(default_factory=list)
    emotional_tone: str = "neutral"
    information_density: float = 0.5
    continuity_context: str = ""
    analysis_reason: str = ""

    @property
    def duration_sec(self) -> float:
        return round(self.end_sec - self.start_sec, 3)

    def to_dict(self) -> dict:
        d = self.__dict__.copy()
        d["semantic_function"] = self.semantic_function.value
        d["duration_sec"] = self.duration_sec
        return d

    def semantic_identity(self) -> dict:
        """Return the timing-independent identity used by semantic stages."""
        identity = self.to_dict()
        for field_name in ("start_sec", "end_sec", "duration_sec"):
            identity.pop(field_name, None)
        return identity

    @classmethod
    def from_dict(cls, d: dict) -> "SemanticBeat":
        d = dict(d)
        d.pop("duration_sec", None)
        d["semantic_function"] = SemanticFunction(d["semantic_function"])
        return cls(**d)


def semantic_beats_identity(beats: list[SemanticBeat]) -> list[dict]:
    """Canonical semantic identity for an ordered beat sequence."""
    return [beat.semantic_identity() for beat in beats]
