"""Motion plan pipeline stage."""
from __future__ import annotations

from typing import Any

from videotool.domain.motion import MotionPlan
from videotool.editorial import validation
from videotool.editorial.motion import build_motion_plan
from videotool.editorial.timing import MOTION_TIMING_VERSION
from videotool.pipeline.context import PipelineContext
from videotool.pipeline.fingerprints import stable_hash
from videotool.pipeline.stage import BasePipelineStage


class MotionPlanStage(BasePipelineStage):
    id = "motion_plan"

    def fingerprint(self, ctx: PipelineContext) -> str:
        return stable_hash(
            self.version,
            ctx.episode_id,
            ctx.state["beats_semantic_hash"],
            ctx.state["timing_hash"],
            ctx.state["comps_hash"],
            ctx.state["anchors_hash"],
            ctx.state["fp_bindings"],
            ctx.state["bindings_hash"],
            MOTION_TIMING_VERSION,
            ctx.timing_policy.to_dict(),
        )

    def execute(self, ctx: PipelineContext) -> dict:
        return build_motion_plan(
            ctx.episode_id,
            ctx.state["beats"],
            ctx.state["compositions"],
            ctx.state["semantic_anchors"],
            ctx.state["timing_bindings"],
            ctx.timing_policy,
        ).to_dict()

    def validate(self, payload: Any, ctx: PipelineContext) -> bool:
        try:
            motion = MotionPlan.from_dict(payload)
        except Exception:
            return False
        return validation.validate_motion(
            motion,
            ctx.state["beats"],
            ctx.state["compositions"],
            ctx.state["semantic_anchors"],
            ctx.state["timing_bindings"],
        ).ok
