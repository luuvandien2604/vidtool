"""Semantic beats analysis pipeline stage."""
from __future__ import annotations

from typing import Any

from videotool.domain.semantic_beat import SemanticBeat
from videotool.domain.timing import NarrationTiming
from videotool.editorial import validation
from videotool.pipeline.context import PipelineContext
from videotool.pipeline.fingerprints import stable_hash
from videotool.pipeline.stage import BasePipelineStage


class SemanticBeatsStage(BasePipelineStage):
    id = "semantic_beats"

    def fingerprint(self, ctx: PipelineContext) -> str:
        semantic_narration_payload = ctx.state["semantic_narration_payload"]
        return stable_hash(self.version, ctx.episode_id, semantic_narration_payload)

    def execute(self, ctx: PipelineContext) -> list[dict]:
        semantic_narration = ctx.state["semantic_narration"]
        beats = ctx.beat_analyzer.analyze(semantic_narration, ctx.episode_id)
        for b in beats:
            if b.semantic_function is None:
                ctx.record_repair(
                    "semantic_beats",
                    f"{b.beat_id}: missing semantic function",
                    "default function assigned (repair)",
                )
        beats = [validation.repair_beat(b) for b in beats]
        kept = [
            b for b in beats
            if validation.validate_beats([b], semantic_narration.duration_sec).ok
        ]
        for dropped in [b for b in beats if b not in kept]:
            ctx.record_repair(
                "semantic_beats", f"{dropped.beat_id} invalid", "dropped beat"
            )
        return [b.to_dict() for b in kept]

    def validate(self, payload: Any, ctx: PipelineContext) -> bool:
        try:
            beats = [SemanticBeat.from_dict(b) for b in payload]
        except Exception:
            return False
        narration_timing: NarrationTiming = ctx.state["narration_timing"]
        word_count = len(narration_timing.words)
        return bool(beats) and all(
            beat.semantic_function is not None
            and beat.narration_text
            and 0 <= beat.word_start < beat.word_end <= word_count
            and beat.end_sec > beat.start_sec
            for beat in beats
        )
