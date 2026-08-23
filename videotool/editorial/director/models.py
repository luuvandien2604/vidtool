"""Domain and DTO models for the AI Editorial Director (Phase 3A).

Provides strongly typed representations for editorial requests, intents,
strategy descriptors, and validation results.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from videotool.pipeline.fingerprints import stable_hash


@dataclass(frozen=True)
class StrategyDescriptor:
    """Compact, sanitized strategy metadata projected for the AI Director."""
    strategy_id: str
    visual_family: str
    compatible_functions: list[str]
    storytelling_note: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "visual_family": self.visual_family,
            "compatible_functions": list(self.compatible_functions),
            "storytelling_note": self.storytelling_note,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "StrategyDescriptor":
        return cls(
            strategy_id=d["strategy_id"],
            visual_family=d["visual_family"],
            compatible_functions=list(d.get("compatible_functions", [])),
            storytelling_note=d.get("storytelling_note", ""),
        )


@dataclass
class EditorialIntent:
    """AI Editorial Director proposal for a single semantic beat."""
    beat_id: str
    story_role: str
    visual_goal: str
    information_priority: list[str] = field(default_factory=list)
    information_density: float = 0.5
    emotional_goal: str = ""
    candidate_strategies: list[str] = field(default_factory=list)
    preferred_visual_families: list[str] = field(default_factory=list)
    avoid_visual_families: list[str] = field(default_factory=list)
    must_show: list[str] = field(default_factory=list)
    must_not_show: list[str] = field(default_factory=list)
    emphasis: str = ""
    reason: str = ""
    confidence: float = 1.0  # 0.0 .. 1.0
    captions: dict[str, str] = field(default_factory=dict)
    schema_version: int = 1
    is_fallback: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "beat_id": self.beat_id,
            "story_role": self.story_role,
            "visual_goal": self.visual_goal,
            "information_priority": list(self.information_priority),
            "information_density": round(float(self.information_density), 3),
            "emotional_goal": self.emotional_goal,
            "candidate_strategies": list(self.candidate_strategies),
            "preferred_visual_families": list(self.preferred_visual_families),
            "avoid_visual_families": list(self.avoid_visual_families),
            "must_show": list(self.must_show),
            "must_not_show": list(self.must_not_show),
            "emphasis": self.emphasis,
            "reason": self.reason,
            "confidence": round(float(self.confidence), 3),
            "captions": dict(self.captions),
            "is_fallback": self.is_fallback,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "EditorialIntent":
        return cls(
            beat_id=d["beat_id"],
            story_role=d.get("story_role", "UNKNOWN"),
            visual_goal=d.get("visual_goal", ""),
            information_priority=list(d.get("information_priority", [])),
            information_density=float(d.get("information_density", 0.5)),
            emotional_goal=d.get("emotional_goal", ""),
            candidate_strategies=list(d.get("candidate_strategies", [])),
            preferred_visual_families=list(d.get("preferred_visual_families", [])),
            avoid_visual_families=list(d.get("avoid_visual_families", [])),
            must_show=list(d.get("must_show", [])),
            must_not_show=list(d.get("must_not_show", [])),
            emphasis=d.get("emphasis", ""),
            reason=d.get("reason", ""),
            confidence=float(d.get("confidence", 1.0)),
            captions=dict(d.get("captions", {})),
            schema_version=int(d.get("schema_version", 1)),
            is_fallback=bool(d.get("is_fallback", False)),
        )


@dataclass(frozen=True)
class EditorialDirectorRequest:
    """Projected, sanitized request context provided to the AI Director for a beat."""
    beat_id: str
    semantic_function: str
    narration_text: str
    entities: list[str]
    locations: list[str]
    dates: list[str]
    information_density: float
    art_direction_motifs: list[str]
    accent_color: str
    recent_families: list[str]
    recent_strategies: list[str]
    family_streak: tuple[str, int]
    candidate_descriptors: list[StrategyDescriptor]
    available_families: list[str]
    text_nodes: list[dict[str, Any]] = field(default_factory=list)

    def fingerprint(self) -> str:
        """Deterministic fingerprint of the request context."""
        descriptors_payload = [d.to_dict() for d in self.candidate_descriptors]
        return stable_hash(
            self.beat_id,
            self.semantic_function,
            self.narration_text,
            self.entities,
            self.locations,
            self.dates,
            round(self.information_density, 3),
            self.art_direction_motifs,
            self.accent_color,
            self.recent_families,
            self.recent_strategies,
            self.family_streak,
            descriptors_payload,
            self.available_families,
            self.text_nodes,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "beat_id": self.beat_id,
            "semantic_function": self.semantic_function,
            "narration_text": self.narration_text,
            "entities": list(self.entities),
            "locations": list(self.locations),
            "dates": list(self.dates),
            "information_density": round(self.information_density, 3),
            "art_direction_motifs": list(self.art_direction_motifs),
            "accent_color": self.accent_color,
            "recent_families": list(self.recent_families),
            "recent_strategies": list(self.recent_strategies),
            "family_streak": list(self.family_streak),
            "candidate_descriptors": [d.to_dict() for d in self.candidate_descriptors],
            "available_families": list(self.available_families),
            "text_nodes": list(self.text_nodes),
        }


@dataclass(frozen=True)
class ValidationResult:
    """Outcome of validating an AI proposal against deterministic domain gates."""
    is_valid: bool
    accepted_strategies: list[str]
    rejected_strategies: list[tuple[str, str]] = field(default_factory=list)
    rejection_reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "accepted_strategies": list(self.accepted_strategies),
            "rejected_strategies": [[k, v] for k, v in self.rejected_strategies],
            "rejection_reasons": list(self.rejection_reasons),
        }
