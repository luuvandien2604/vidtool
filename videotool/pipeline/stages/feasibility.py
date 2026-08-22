"""Strategy feasibility pipeline stage (plan of record)."""
from __future__ import annotations

from typing import Any

from videotool.domain.strategy import SelectionRecord
from videotool.editorial import validation
from videotool.editorial.feasibility import run_feasibility_pass
from videotool.pipeline.context import PipelineContext
from videotool.pipeline.fingerprints import stable_hash
from videotool.pipeline.stage import BasePipelineStage
from videotool.pipeline.stages.strategy import _repair_strategy_records


class StrategyFeasibilityStage(BasePipelineStage):
    id = "strategy_feasibility"

    def fingerprint(self, ctx: PipelineContext) -> str:
        return stable_hash(
            self.version,
            ctx.episode_id,
            ctx.state["strategy_hash"],
            ctx.state["media_hash"],
            ctx.mode,
            ctx.planner_config.max_family_streak,
        )

    def execute(self, ctx: PipelineContext) -> dict:
        complete = _repair_strategy_records(
            ctx.state["preliminary_strategy_plan"], ctx.state["beats"], ctx
        )
        result = run_feasibility_pass(
            complete,
            ctx.state["beats"],
            ctx.state["requirements"],
            ctx.state["assets"],
            ctx.planner_config.max_family_streak,
        )
        return {
            "adjustments": result.adjustments,
            "records": [r.to_dict() for r in result.records],
        }

    def validate(self, payload: Any, ctx: PipelineContext) -> bool:
        try:
            records = [
                SelectionRecord.from_dict(r) for r in payload.get("records", [])
            ]
        except Exception:
            return False
        return validation.validate_strategy_plan(records, ctx.state["beats"]).ok
