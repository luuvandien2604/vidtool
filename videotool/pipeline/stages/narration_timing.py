"""Narration timing pipeline stage."""
from __future__ import annotations

from typing import Any

from videotool.domain.timing import NarrationTiming
from videotool.editorial.timing import validate_narration_timing
from videotool.pipeline.context import PipelineContext
from videotool.pipeline.fingerprints import STAGE_VERSIONS, stable_hash
from videotool.pipeline.stage import BasePipelineStage
from videotool.providers.timing import NARRATION_TIMING_VERSION


class NarrationTimingStage(BasePipelineStage):
    id = "narration_timing"

    def fingerprint(self, ctx: PipelineContext) -> str:
        narration_payload = ctx.narration.to_dict()
        return stable_hash(
            self.version,
            ctx.episode_id,
            narration_payload,
            ctx.timing_provider.provider_id,
            ctx.timing_provider.provider_version,
            NARRATION_TIMING_VERSION,
        )

    def execute(self, ctx: PipelineContext) -> dict:
        return ctx.timing_provider.align(ctx.narration).to_dict()

    def validate(self, payload: Any, ctx: PipelineContext) -> bool:
        try:
            timing = NarrationTiming.from_dict(payload)
        except Exception:
            return False
        return not validate_narration_timing(timing)
