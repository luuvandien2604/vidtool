"""Chapter Outline pipeline stage (Stage 2).

Allocates 4-5 chapters for a 10-minute documentary with narrative goals and time budgets.
"""
from __future__ import annotations

from typing import Any

from videotool.domain.story_structure import ChapterOutline, MacroStoryArc
from videotool.pipeline.context import PipelineContext
from videotool.pipeline.fingerprints import stable_hash
from videotool.pipeline.stage import BasePipelineStage


class ChapterOutlineStage(BasePipelineStage):
    id = "chapter_outline"

    def fingerprint(self, ctx: PipelineContext) -> str:
        fact_payload = ctx.state.get("fact_registry_payload", {})
        return stable_hash(self.version, ctx.episode_id, fact_payload)

    def execute(self, ctx: PipelineContext) -> dict[str, Any]:
        topic = ctx.state.get("topic", ctx.episode_id)
        existing_arc = ctx.state.get("story_arc") or ctx.state.get("chapter_outline")
        if existing_arc and isinstance(existing_arc, dict) and "chapters" in existing_arc and len(existing_arc["chapters"]) >= 1:
            return existing_arc

        fact_payload = ctx.state.get("fact_registry_payload") or ctx.state.get("fact_registry") or {}
        entities = [e.get("name") for e in fact_payload.get("entities", []) if isinstance(e, dict) and e.get("name")]
        facts = [f.get("statement") for f in fact_payload.get("facts", []) if isinstance(f, dict) and f.get("statement")]

        e1 = entities[0] if len(entities) > 0 else topic
        e2 = entities[1] if len(entities) > 1 else "Nhân chứng lịch sử"

        # Topic-tailored dynamic chapters
        chapters = [
            ChapterOutline(
                chapter_index=1,
                chapter_id="chapter_01_setup",
                title=f"Phần 1: Khởi nguồn & Bối cảnh {topic}",
                narrative_goal=f"Thiết lập bối cảnh lịch sử và nguyên nhân hình thành {topic}.",
                target_duration_sec=120.0,
                start_time_sec=0.0,
                end_time_sec=120.0,
                emotional_tone="investigative",
                key_headline=f"KHỞI NGUỒN",
            ),
            ChapterOutline(
                chapter_index=2,
                chapter_id="chapter_02_escalation",
                title=f"Phần 2: Diễn biến leo thang & Những dấu hiệu cảnh báo",
                narrative_goal=f"Mô tả chi tiết tiến trình phát triển và các sự kiện then chốt của {e1}.",
                target_duration_sec=180.0,
                start_time_sec=120.0,
                end_time_sec=300.0,
                emotional_tone="tense",
                key_headline=f"DIỄN BIẾN LEO THANG",
            ),
            ChapterOutline(
                chapter_index=3,
                chapter_id="chapter_03_climax",
                title=f"Phần 3: Thời khắc định mệnh & Biến cố trung tâm",
                narrative_goal=f"Tái hiện khoảnh khắc đỉnh điểm và tác động trực tiếp tới {e2}.",
                target_duration_sec=180.0,
                start_time_sec=300.0,
                end_time_sec=480.0,
                emotional_tone="dramatic",
                key_headline=f"THỜI KHẮC ĐỊNH MỆNH",
            ),
            ChapterOutline(
                chapter_index=4,
                chapter_id="chapter_04_legacy",
                title=f"Phần 4: Hậu quả, Bài học & Di sản lịch sử",
                narrative_goal=f"Đánh giá ý nghĩa lịch sử sâu sắc và bài học nhân loại từ {topic}.",
                target_duration_sec=120.0,
                start_time_sec=480.0,
                end_time_sec=600.0,
                emotional_tone="reflective",
                key_headline=f"DI SẢN LỊCH SỬ",
            ),
        ]

        arc = MacroStoryArc(
            project_id=ctx.episode_id,
            title=topic,
            target_total_duration_sec=600.0,
            chapters=chapters,
            central_theme=f"Phim tài liệu chuyên sâu: {topic}",
        )
        return arc.to_dict()

    def validate(self, payload: Any, ctx: PipelineContext) -> bool:
        if not isinstance(payload, dict):
            return False
        return "project_id" in payload and "chapters" in payload and len(payload["chapters"]) >= 1
