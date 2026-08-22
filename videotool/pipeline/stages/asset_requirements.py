"""Asset requirements pipeline stage."""
from __future__ import annotations

from typing import Any

from videotool.domain.assets import AssetRequirement
from videotool.editorial.composition import semantic_asset_requirements
from videotool.pipeline.context import PipelineContext
from videotool.pipeline.fingerprints import stable_hash
from videotool.pipeline.stage import BasePipelineStage


class AssetRequirementsStage(BasePipelineStage):
    id = "asset_requirements"

    def fingerprint(self, ctx: PipelineContext) -> str:
        return stable_hash(
            self.version,
            ctx.episode_id,
            ctx.state["beats_semantic_hash"],
        )

    def execute(self, ctx: PipelineContext) -> list[dict]:
        import videotool.pipeline.runner as runner_module
        req_fn = getattr(runner_module, "semantic_asset_requirements", semantic_asset_requirements)
        reqs = req_fn(ctx.state["beats"])
        kept = [r for r in reqs if r.beat_id and r.description]
        if len(kept) != len(reqs):
            ctx.record_repair(
                "asset_requirements", "invalid requirements", "dropped"
            )
        return [r.to_dict() for r in kept]

    def validate(self, payload: Any, ctx: PipelineContext) -> bool:
        beat_ids = {b.beat_id for b in ctx.state["beats"]}
        try:
            reqs = [AssetRequirement.from_dict(r) for r in payload]
        except Exception:
            return False
        return bool(reqs) and all(
            r.beat_id in beat_ids and r.description for r in reqs
        )
