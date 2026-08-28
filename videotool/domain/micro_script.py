"""Micro-Scripting & Beat Chunking Domain Model (Stage 3).

Structures chapter narration into atomic 4-12 second semantic beats
with keyword highlighting, pacing pauses, and visual intent cues.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class BeatScript:
    beat_id: str  # e.g. "ch01_beat01"
    beat_index: int
    narration_text: str
    target_duration_sec: float  # e.g. 6.5s
    semantic_function: str  # "ESTABLISHING_CONTEXT" | "EVIDENCE" | "MOVEMENT" | "CRISIS" | "QUOTE" | "REFLECTION"
    emphasis_keywords: list[str] = field(default_factory=list)  # Words highlighted in gold (#E1B400)
    fact_id_ref: str | None = None
    historical_date: str | None = None
    pause_after_sec: float = 0.5
    visual_strategy_recommendation: str = "paper_collage_hero"  # "paper_collage_hero" | "geographic_map" | "archival_subject" | "document_evidence" | "quote_banner"
    search_queries: list[str] = field(default_factory=list)


@dataclass
class ChapterScript:
    chapter_id: str
    chapter_index: int
    title: str
    beats: list[BeatScript] = field(default_factory=list)
    total_words: int = 0
    estimated_duration_sec: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "chapter_id": self.chapter_id,
            "chapter_index": self.chapter_index,
            "title": self.title,
            "total_words": self.total_words,
            "estimated_duration_sec": self.estimated_duration_sec,
            "beats": [
                {
                    "beat_id": b.beat_id,
                    "beat_index": b.beat_index,
                    "narration_text": b.narration_text,
                    "target_duration_sec": b.target_duration_sec,
                    "semantic_function": b.semantic_function,
                    "emphasis_keywords": b.emphasis_keywords,
                    "fact_id_ref": b.fact_id_ref,
                    "historical_date": b.historical_date,
                    "pause_after_sec": b.pause_after_sec,
                    "visual_strategy_recommendation": b.visual_strategy_recommendation,
                    "search_queries": b.search_queries,
                }
                for b in self.beats
            ],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ChapterScript:
        beats = [
            BeatScript(
                beat_id=b.get("beat_id", f"beat_{idx+1:02d}"),
                beat_index=int(b.get("beat_index", idx + 1)),
                narration_text=b.get("narration_text", ""),
                target_duration_sec=float(b.get("target_duration_sec", 6.0)),
                semantic_function=b.get("semantic_function", "ESTABLISHING_CONTEXT"),
                emphasis_keywords=b.get("emphasis_keywords", []),
                fact_id_ref=b.get("fact_id_ref"),
                historical_date=b.get("historical_date"),
                pause_after_sec=float(b.get("pause_after_sec", 0.5)),
                visual_strategy_recommendation=b.get("visual_strategy_recommendation", "paper_collage_hero"),
                search_queries=b.get("search_queries", []),
            )
            for idx, b in enumerate(data.get("beats", []))
        ]
        return cls(
            chapter_id=data.get("chapter_id", "chapter_01"),
            chapter_index=int(data.get("chapter_index", 1)),
            title=data.get("title", ""),
            beats=beats,
            total_words=int(data.get("total_words", 0)),
            estimated_duration_sec=float(data.get("estimated_duration_sec", 0.0)),
        )
