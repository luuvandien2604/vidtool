"""Semantic anchors extraction pipeline stage."""
from __future__ import annotations

from typing import Any

from videotool.domain.semantic_beat import SemanticBeat
from videotool.domain.timing import NarrationTiming, SemanticAnchor
from videotool.editorial.timing import (
    ANCHOR_EXTRACTION_VERSION,
    extract_semantic_anchors,
    validate_anchors,
)
from videotool.pipeline.context import PipelineContext
from videotool.pipeline.fingerprints import stable_hash
from videotool.pipeline.stage import BasePipelineStage


class SemanticAnchorsStage(BasePipelineStage):
    id = "semantic_anchors"

    def fingerprint(self, ctx: PipelineContext) -> str:
        return stable_hash(
            self.version,
            ctx.episode_id,
            ctx.state["beats_semantic_hash"],
            ctx.state["timing_hash"],
            ANCHOR_EXTRACTION_VERSION,
        )

    def execute(self, ctx: PipelineContext) -> list[dict]:
        narration_timing: NarrationTiming = ctx.state["narration_timing"]
        beats: list[SemanticBeat] = ctx.state["beats"]
        return [
            anchor.to_dict()
            for anchor in extract_semantic_anchors(narration_timing, beats)
        ]

    def validate(self, payload: Any, ctx: PipelineContext) -> bool:
        try:
            anchors = [SemanticAnchor.from_dict(a) for a in payload]
        except Exception:
            return False
        return not validate_anchors(
            anchors, ctx.state["beats"], ctx.state["narration_timing"]
        )
