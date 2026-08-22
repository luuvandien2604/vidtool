"""Semantic geometry pipeline stage."""
from __future__ import annotations

from typing import Any

from videotool.domain.geometry import GeometryHistory, GeometryPlan
from videotool.editorial.composition import assets_for_beat
from videotool.editorial.geometry import (
    GEOMETRY_CANDIDATE_VERSION,
    GEOMETRY_POLICY_VERSION,
    GEOMETRY_SCORE_VERSION,
    GEOMETRY_SIGNATURE_VERSION,
    GEOMETRY_SOLVER_VERSION,
    SEMANTIC_GEOMETRY_VERSION,
    geometry_input_projection,
    validate_geometry_plan,
    validate_geometry_plans,
)
from videotool.pipeline.context import PipelineContext
from videotool.pipeline.fingerprints import stable_hash
from videotool.pipeline.stage import BasePipelineStage


class SemanticGeometryStage(BasePipelineStage):
    id = "semantic_geometry"

    def fingerprint(self, ctx: PipelineContext) -> str:
        geometry_projection = geometry_input_projection(
            ctx.state["compositions"],
            ctx.state["assets"],
            ctx.state["strategy_plan"],
            ctx.state["art_direction"],
            ctx.state["semantic_anchors"],
            ctx.state["timing_bindings"],
            ctx.state["requirements"],
        )
        return stable_hash(
            self.version,
            ctx.episode_id,
            ctx.state["beats_semantic_hash"],
            geometry_projection,
            SEMANTIC_GEOMETRY_VERSION,
            GEOMETRY_POLICY_VERSION,
            GEOMETRY_SIGNATURE_VERSION,
            GEOMETRY_SOLVER_VERSION,
            GEOMETRY_CANDIDATE_VERSION,
            GEOMETRY_SCORE_VERSION,
        )

    def execute(self, ctx: PipelineContext) -> list[dict]:
        selection_by_beat = {item.beat_id: item for item in ctx.state["strategy_plan"]}
        composition_by_beat = {item.beat_id: item for item in ctx.state["compositions"]}
        history = GeometryHistory()
        plans: list[GeometryPlan] = []
        for beat in ctx.state["beats"]:
            selection = selection_by_beat[beat.beat_id]
            composition = composition_by_beat.get(beat.beat_id)
            beat_requirements = [
                item for item in ctx.state["requirements"] if item.beat_id == beat.beat_id
            ]
            beat_assets = assets_for_beat(
                ctx.state["assets"], ctx.state["requirements"], beat.beat_id
            )
            beat_anchors = [
                item for item in ctx.state["semantic_anchors"] if item.beat_id == beat.beat_id
            ]
            composition_bindings = [
                item
                for item in ctx.state["timing_bindings"]
                if composition is not None
                and item.composition_id == composition.composition_id
            ]
            try:
                plan = ctx.geometry_builder.build_plan(
                    beat,
                    selection.visual_family,
                    selection.selected_strategy,
                    beat_assets,
                    beat_requirements,
                    ctx.state["art_direction"],
                    beat_anchors,
                    composition,
                    composition_bindings,
                    history.recent(),
                )
                report = validate_geometry_plan(
                    plan, {asset.asset_id for asset in ctx.state["assets"]}
                )
                if not report.ok:
                    raise ValueError("; ".join(report.errors))
            except Exception as exc:
                reason = (
                    f"{composition.beat_id}: semantic geometry raised {type(exc).__name__}"
                )
                ctx.record_repair(
                    "semantic_geometry",
                    reason,
                    "deterministic semantic geometry fallback",
                )
                plan = ctx.geometry_builder.fallback_plan(
                    beat, selection.visual_family, reason, history.recent()
                )
            plans.append(plan)
            history.record(plan.structural_geometry_signature)
        return [plan.to_dict() for plan in plans]

    def validate(self, payload: Any, ctx: PipelineContext) -> bool:
        try:
            plans = [GeometryPlan.from_dict(item) for item in payload]
        except Exception:
            return False
        return validate_geometry_plans(
            plans,
            {beat.beat_id for beat in ctx.state["beats"]},
            {asset.asset_id for asset in ctx.state["assets"]},
        ).ok
