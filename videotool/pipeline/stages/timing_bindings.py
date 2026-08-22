"""Timing bindings pipeline stage."""
from __future__ import annotations

from typing import Any

from videotool.domain.timing import TimingBinding
from videotool.editorial.timing import (
    TIMING_BINDING_VERSION,
    build_timing_bindings,
    validate_timing_bindings,
)
from videotool.pipeline.context import PipelineContext
from videotool.pipeline.fingerprints import stable_hash
from videotool.pipeline.stage import BasePipelineStage


class TimingBindingsStage(BasePipelineStage):
    id = "timing_bindings"

    def fingerprint(self, ctx: PipelineContext) -> str:
        return stable_hash(
            self.version,
            ctx.episode_id,
            ctx.state["fp_anchors"],
            ctx.state["anchors_hash"],
            ctx.state["comps_hash"],
            TIMING_BINDING_VERSION,
            ctx.timing_policy.to_dict(),
        )

    def execute(self, ctx: PipelineContext) -> list[dict]:
        return [
            binding.to_dict()
            for binding in build_timing_bindings(
                ctx.state["beats"],
                ctx.state["compositions"],
                ctx.state["semantic_anchors"],
                ctx.timing_policy,
            )
        ]

    def validate(self, payload: Any, ctx: PipelineContext) -> bool:
        try:
            bindings = [TimingBinding.from_dict(b) for b in payload]
        except Exception:
            return False
        return not validate_timing_bindings(
            bindings,
            ctx.state["beats"],
            ctx.state["compositions"],
            ctx.state["semantic_anchors"],
        )
