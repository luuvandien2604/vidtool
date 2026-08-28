"""Fact Registry Domain Model (Stage 1).

Locks ground-truth historical facts, entities, dates, and citations
to eliminate AI hallucination before scriptwriting and scene planning.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class HistoricalEntity:
    name: str
    category: str  # "person" | "location" | "organization" | "artifact" | "event"
    role: str
    aliases: list[str] = field(default_factory=list)
    verified: bool = True


@dataclass
class FactItem:
    id: str
    statement: str
    historical_date: str | None = None  # e.g. "1961-08-13" or "13/08/1961"
    entities_involved: list[str] = field(default_factory=list)
    confidence: float = 1.0
    source_citation: str = ""
    verified: bool = True


@dataclass
class FactRegistry:
    project_id: str
    topic: str
    central_thesis: str
    entities: list[HistoricalEntity] = field(default_factory=list)
    facts: list[FactItem] = field(default_factory=list)
    verified_at: str | None = None
    created_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "topic": self.topic,
            "central_thesis": self.central_thesis,
            "entities": [
                {
                    "name": e.name,
                    "category": e.category,
                    "role": e.role,
                    "aliases": e.aliases,
                    "verified": e.verified,
                }
                for e in self.entities
            ],
            "facts": [
                {
                    "id": f.id,
                    "statement": f.statement,
                    "historical_date": f.historical_date,
                    "entities_involved": f.entities_involved,
                    "confidence": f.confidence,
                    "source_citation": f.source_citation,
                    "verified": f.verified,
                }
                for f in self.facts
            ],
            "verified_at": self.verified_at,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FactRegistry:
        entities = [
            HistoricalEntity(
                name=e.get("name", ""),
                category=e.get("category", "event"),
                role=e.get("role", ""),
                aliases=e.get("aliases", []),
                verified=e.get("verified", True),
            )
            for e in data.get("entities", [])
        ]
        facts = [
            FactItem(
                id=f.get("id", f"fact_{idx}"),
                statement=f.get("statement", ""),
                historical_date=f.get("historical_date"),
                entities_involved=f.get("entities_involved", []),
                confidence=float(f.get("confidence", 1.0)),
                source_citation=f.get("source_citation", ""),
                verified=f.get("verified", True),
            )
            for idx, f in enumerate(data.get("facts", []))
        ]
        return cls(
            project_id=data.get("project_id", "project"),
            topic=data.get("topic", ""),
            central_thesis=data.get("central_thesis", ""),
            entities=entities,
            facts=facts,
            verified_at=data.get("verified_at"),
            created_at=data.get("created_at"),
        )
