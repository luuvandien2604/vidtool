"""Visual history pipeline stage."""
from __future__ import annotations

from typing import Any

from videotool.domain.visual_history import VisualHistory
from videotool.editorial.composition import history_from_compositions
from videotool.pipeline.context import PipelineContext
from videotool.pipeline.fingerprints import stable_hash
from videotool.pipeline.stage import BasePipelineStage


class VisualHistoryStage(BasePipelineStage):
    id = "visual_history"

    def fingerprint(self, ctx: PipelineContext) -> str:
        return stable_hash(
            self.version, ctx.episode_id, ctx.state["comps_hash"]
        )

    def execute(self, ctx: PipelineContext) -> dict:
        return history_from_compositions(ctx.state["compositions"]).to_dict()

    def validate(self, payload: Any, ctx: PipelineContext) -> bool:
        try:
            hist = VisualHistory.from_dict(payload)
        except Exception:
            return False
        return len(hist.entries) == len(ctx.state["compositions"])
