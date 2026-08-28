"""Chapter Scriptwriting pipeline stage (Stage 3).

Generates beat-by-beat narration per chapter with gold emphasis keywords and pacing pauses.
"""
from __future__ import annotations

import re
from typing import Any

from videotool.domain.micro_script import BeatScript, ChapterScript
from videotool.domain.story_structure import MacroStoryArc
from videotool.pipeline.context import PipelineContext
from videotool.pipeline.fingerprints import stable_hash
from videotool.pipeline.stage import BasePipelineStage


class ChapterScriptwritingStage(BasePipelineStage):
    id = "chapter_scripts"

    def fingerprint(self, ctx: PipelineContext) -> str:
        outline_payload = ctx.state.get("chapter_outline_payload", {})
        return stable_hash(self.version, ctx.episode_id, outline_payload)

    def execute(self, ctx: PipelineContext) -> list[dict[str, Any]]:
        outline_data = ctx.state.get("chapter_outline", {})
        if isinstance(outline_data, dict):
            arc = MacroStoryArc.from_dict(outline_data)
        else:
            arc = outline_data

        existing_scripts = ctx.state.get("chapter_scripts")
        if existing_scripts and isinstance(existing_scripts, list) and len(existing_scripts) >= 1:
            if any(len(cs.get("beats", [])) > 0 for cs in existing_scripts if isinstance(cs, dict)):
                return existing_scripts

        raw_narration = ctx.state.get("raw_script_text") or getattr(ctx.episode.narration, "text", "")
        sentences = [s.strip() for s in re.split(r"[.!?]+", raw_narration) if len(s.strip()) > 8]

        fact_payload = ctx.state.get("fact_registry_payload") or ctx.state.get("fact_registry") or {}
        facts = [f.get("statement") for f in fact_payload.get("facts", []) if isinstance(f, dict) and f.get("statement")]
        entities = [e.get("name") for e in fact_payload.get("entities", []) if isinstance(e, dict) and e.get("name")]

        chapter_scripts: list[ChapterScript] = []
        num_ch = len(arc.chapters) or 1
        s_per_ch = max(1, len(sentences) // num_ch)

        for i, ch in enumerate(arc.chapters):
            start_s = i * s_per_ch
            end_s = (i + 1) * s_per_ch if i < num_ch - 1 else len(sentences)
            ch_sentences = sentences[start_s:end_s]
            if not ch_sentences:
                ch_sentences = [f"Những diễn biến trọng tâm của {ch.title}."]

            beats = []
            for b_idx, st in enumerate(ch_sentences):
                # Extract emphasis words
                words = st.split()
                emp = [w for w in words if len(w) > 4][:3]
                if not emp:
                    emp = words[:2]

                strat = "paper_collage_hero" if b_idx == 0 else ("document_evidence" if b_idx == 1 else "archival_subject")
                beats.append(BeatScript(
                    beat_id=f"{ch.chapter_id}_b{b_idx+1:02d}",
                    beat_index=b_idx + 1,
                    narration_text=st + ".",
                    target_duration_sec=max(4.0, min(12.0, len(words) * 0.45)),
                    semantic_function="ESTABLISHING_CONTEXT" if b_idx == 0 else "EVIDENCE",
                    emphasis_keywords=emp,
                    pause_after_sec=0.5,
                    visual_strategy_recommendation=strat,
                ))

            words = sum(len(b.narration_text.split()) for b in beats)
            dur = sum(b.target_duration_sec + b.pause_after_sec for b in beats)

            ch_script = ChapterScript(
                chapter_id=ch.chapter_id,
                chapter_index=ch.chapter_index,
                title=ch.title,
                beats=beats,
                total_words=words,
                estimated_duration_sec=dur,
            )
            chapter_scripts.append(ch_script)

        return [cs.to_dict() for cs in chapter_scripts]

    def validate(self, payload: Any, ctx: PipelineContext) -> bool:
        if not isinstance(payload, list):
            return False
        return len(payload) >= 1 and all("chapter_id" in cs and "beats" in cs for cs in payload)
