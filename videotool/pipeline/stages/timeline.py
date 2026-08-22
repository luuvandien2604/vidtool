"""Timeline generation pipeline stage."""
from __future__ import annotations

from typing import Any

from videotool.editorial import validation
from videotool.editorial.timeline import build_timeline
from videotool.pipeline.context import PipelineContext
from videotool.pipeline.fingerprints import stable_hash
from videotool.pipeline.stage import BasePipelineStage


class TimelineStage(BasePipelineStage):
    id = "timeline"

    def fingerprint(self, ctx: PipelineContext) -> str:
        return stable_hash(
            self.version,
            ctx.episode_id,
            ctx.state["timing_hash"],
            ctx.state["beats_semantic_hash"],
            ctx.state["comps_hash"],
            ctx.state["fp_motion"],
            ctx.state["motion_hash"],
        )

    def execute(self, ctx: PipelineContext) -> dict:
        return build_timeline(
            ctx.episode_id,
            ctx.state["timed_narration"],
            ctx.state["beats"],
            ctx.state["compositions"],
            ctx.state["motion"],
            ctx.state["narration_timing"],
        )

    def validate(self, payload: Any, ctx: PipelineContext) -> bool:
        if not isinstance(payload, dict) or not payload.get("segments"):
            return False
        return validation.validate_timeline(
            payload, ctx.state["beats"], ctx.state["compositions"], ctx.mode
        ).ok
