"""Semantic asset requirements + scored media assets (spec sections 15-16).

Phase 1.2: requirements carry STRENGTH. The Media Completeness Gate checks
REQUIRED requirements against resolved assets after the strategy feasibility
pass; PREFERRED/OPTIONAL gaps may be routed around by the planner.
"""
from __future__ import annotations

from dataclasses import dataclass, field

REQUIRED = "REQUIRED"        # final mode fails if unresolved AND the
                             # plan-of-record strategy still needs it
PREFERRED = "PREFERRED"      # planner should route around if unresolved
OPTIONAL = "OPTIONAL"        # nice to have; never gates

STRENGTHS = (REQUIRED, PREFERRED, OPTIONAL)


@dataclass
class AssetRequirement:
    requirement_id: str
    beat_id: str
    description: str        # semantic, e.g. "portrait of X during Y context"
    kind: str               # portrait / document / photo / map / texture ...
    strength: str = PREFERRED
    entities: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return self.__dict__.copy()

    @classmethod
    def from_dict(cls, d: dict) -> "AssetRequirement":
        d = dict(d)
        d.pop("min_count", None)  # legacy Phase 1 field
        if d.get("strength") not in STRENGTHS:
            d["strength"] = PREFERRED
        return cls(**d)


@dataclass
class MediaAsset:
    asset_id: str
    requirement_id: str | None
    description: str
    kind: str
    entity_match: float = 0.0
    event_match: float = 0.0
    date_match: float = 0.0
    location_match: float = 0.0
    context_match: float = 0.0
    visual_quality: float = 0.5
    source_quality: float = 0.5
    is_placeholder: bool = False
    duplication_penalty: float = 0.0

    def relevance_score(self) -> float:
        base = (self.entity_match * 0.30 + self.event_match * 0.15 +
                self.date_match * 0.10 + self.location_match * 0.15 +
                self.context_match * 0.15 + self.visual_quality * 0.10 +
                self.source_quality * 0.05)
        return round(max(0.0, base - self.duplication_penalty), 3)

    def to_dict(self) -> dict:
        d = self.__dict__.copy()
        d["relevance_score"] = self.relevance_score()
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "MediaAsset":
        d = dict(d)
        d.pop("relevance_score", None)
        return cls(**d)
