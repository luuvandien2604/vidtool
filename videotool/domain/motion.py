"""Motion + transition planning models (spec sections 12-14).

Motion must have semantic purpose: every event carries the reason it moves.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class TransitionCategory(str, Enum):
    CONTINUATION = "CONTINUATION"
    CAUSE_TO_EFFECT = "CAUSE_TO_EFFECT"
    ZOOM_TO_DETAIL = "ZOOM_TO_DETAIL"
    DOCUMENT_TO_EVENT = "DOCUMENT_TO_EVENT"
    MAP_TO_LOCATION = "MAP_TO_LOCATION"
    CHARACTER_TO_ACTION = "CHARACTER_TO_ACTION"
    PAST_TO_PRESENT = "PAST_TO_PRESENT"
    BEFORE_TO_AFTER = "BEFORE_TO_AFTER"
    QUESTION_TO_EVIDENCE = "QUESTION_TO_EVIDENCE"
    EVIDENCE_TO_REVEAL = "EVIDENCE_TO_REVEAL"
    ESCALATION = "ESCALATION"
    HARD_CHAPTER_BREAK = "HARD_CHAPTER_BREAK"


class EventKind(str, Enum):
    ENTRANCE = "ENTRANCE"
    EMPHASIS = "EMPHASIS"
    EXIT = "EXIT"


@dataclass
class MotionEvent:
    layer_id: str
    kind: EventKind
    style: str
    start_sec: float   # absolute on the episode timeline
    end_sec: float
    semantic_reason: str

    def to_dict(self) -> dict:
        d = self.__dict__.copy()
        d["kind"] = self.kind.value
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "MotionEvent":
        d = dict(d)
        d["kind"] = EventKind(d["kind"])
        return cls(**d)


@dataclass
class TransitionPlan:
    from_beat: str
    to_beat: str
    category: TransitionCategory
    start_sec: float
    end_sec: float
    reason: str = ""

    @property
    def duration_sec(self) -> float:
        return round(self.end_sec - self.start_sec, 3)

    def to_dict(self) -> dict:
        return {
            "from_beat": self.from_beat,
            "to_beat": self.to_beat,
            "category": self.category.value,
            "start_sec": self.start_sec,
            "end_sec": self.end_sec,
            "duration_sec": self.duration_sec,
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "TransitionPlan":
        d = dict(d)
        d.pop("duration_sec", None)
        d["category"] = TransitionCategory(d["category"])
        return cls(**d)


@dataclass
class CompositionMotionPlan:
    composition_id: str
    beat_id: str
    camera_behavior: str = "stable"  # stable | slow_push (semantic only)
    camera_reason: str = ""
    events: list[MotionEvent] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "composition_id": self.composition_id,
            "beat_id": self.beat_id,
            "camera_behavior": self.camera_behavior,
            "camera_reason": self.camera_reason,
            "events": [e.to_dict() for e in self.events],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "CompositionMotionPlan":
        return cls(
            composition_id=d["composition_id"],
            beat_id=d["beat_id"],
            camera_behavior=d.get("camera_behavior", "stable"),
            camera_reason=d.get("camera_reason", ""),
            events=[MotionEvent.from_dict(e) for e in d.get("events", [])],
        )


@dataclass
class MotionPlan:
    episode_id: str
    plans: list[CompositionMotionPlan] = field(default_factory=list)
    transitions: list[TransitionPlan] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "episode_id": self.episode_id,
            "plans": [p.to_dict() for p in self.plans],
            "transitions": [t.to_dict() for t in self.transitions],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "MotionPlan":
        return cls(
            episode_id=d["episode_id"],
            plans=[CompositionMotionPlan.from_dict(p) for p in d.get("plans", [])],
            transitions=[TransitionPlan.from_dict(t) for t in d.get("transitions", [])],
        )
