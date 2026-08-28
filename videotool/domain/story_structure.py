"""Story Structure & Chapter Outline Domain Model (Stage 2).

Defines macro-narrative structure: 4-5 chapters for a 10-minute documentary,
time budget allocation, emotional arc, and key narrative milestones.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ChapterOutline:
    chapter_index: int  # 1-indexed (e.g. 1, 2, 3, 4, 5)
    chapter_id: str  # e.g. "chapter_01_exodus"
    title: str  # e.g. "Bối cảnh chia cắt và làn sóng tháo chạy"
    narrative_goal: str
    target_duration_sec: float  # e.g. 120.0 (2 minutes)
    start_time_sec: float
    end_time_sec: float
    emotional_tone: str  # "investigative" | "dramatic" | "tense" | "reflective"
    core_fact_ids: list[str] = field(default_factory=list)
    key_headline: str = ""
    date_milestone: str | None = None


@dataclass
class MacroStoryArc:
    project_id: str
    title: str
    target_total_duration_sec: float  # e.g. 600.0 (10 minutes)
    chapters: list[ChapterOutline] = field(default_factory=list)
    central_theme: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "title": self.title,
            "target_total_duration_sec": self.target_total_duration_sec,
            "central_theme": self.central_theme,
            "chapters": [
                {
                    "chapter_index": c.chapter_index,
                    "chapter_id": c.chapter_id,
                    "title": c.title,
                    "narrative_goal": c.narrative_goal,
                    "target_duration_sec": c.target_duration_sec,
                    "start_time_sec": c.start_time_sec,
                    "end_time_sec": c.end_time_sec,
                    "emotional_tone": c.emotional_tone,
                    "core_fact_ids": c.core_fact_ids,
                    "key_headline": c.key_headline,
                    "date_milestone": c.date_milestone,
                }
                for c in self.chapters
            ],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MacroStoryArc:
        chapters = [
            ChapterOutline(
                chapter_index=int(c.get("chapter_index", idx + 1)),
                chapter_id=c.get("chapter_id", f"chapter_{idx+1:02d}"),
                title=c.get("title", ""),
                narrative_goal=c.get("narrative_goal", ""),
                target_duration_sec=float(c.get("target_duration_sec", 120.0)),
                start_time_sec=float(c.get("start_time_sec", 0.0)),
                end_time_sec=float(c.get("end_time_sec", 120.0)),
                emotional_tone=c.get("emotional_tone", "investigative"),
                core_fact_ids=c.get("core_fact_ids", []),
                key_headline=c.get("key_headline", ""),
                date_milestone=c.get("date_milestone"),
            )
            for idx, c in enumerate(data.get("chapters", []))
        ]
        return cls(
            project_id=data.get("project_id", "project"),
            title=data.get("title", ""),
            target_total_duration_sec=float(data.get("target_total_duration_sec", 600.0)),
            chapters=chapters,
            central_theme=data.get("central_theme", ""),
        )
