"""Stage registry for the video production pipeline (spec section 20).

Maintains the canonical ordered sequence of discrete pipeline stages.
"""
from __future__ import annotations

from videotool.pipeline.stage import PipelineStage
from videotool.pipeline.stages import (
    AssetRequirementsStage,
    EpisodeArtDirectionStage,
    MediaAcquisitionResultStage,
    MediaAcquisitionTraceStage,
    MediaAssetsStage,
    MediaAttributionStage,
    MediaCandidatesStage,
    MediaSearchPlanStage,
    MotionPlanStage,
    NarrationTimingStage,
    SemanticAnchorsStage,
    SemanticBeatsStage,
    SemanticGeometryStage,
    StrategyFeasibilityStage,
    TimelineStage,
    TimingBindingsStage,
    VisualCompositionsStage,
    VisualHistoryStage,
    VisualStrategyPlanStage,
)

__all__ = ["StageRegistry"]


class StageRegistry:
    """Registry maintaining the canonical ordered sequence of pipeline stages."""

    def __init__(self):
        self._stages: list[PipelineStage] = [
            NarrationTimingStage(),
            SemanticBeatsStage(),
            SemanticAnchorsStage(),
            EpisodeArtDirectionStage(),
            VisualStrategyPlanStage(),
            AssetRequirementsStage(),
            MediaSearchPlanStage(),
            MediaCandidatesStage(),
            MediaAcquisitionResultStage(),
            MediaAssetsStage(),
            MediaAcquisitionTraceStage(),
            MediaAttributionStage(),
            StrategyFeasibilityStage(),
            VisualCompositionsStage(),
            VisualHistoryStage(),
            TimingBindingsStage(),
            SemanticGeometryStage(),
            MotionPlanStage(),
            TimelineStage(),
        ]

    def all_stages(self) -> list[PipelineStage]:
        return list(self._stages)

    def get_stage(self, stage_id: str) -> PipelineStage | None:
        for s in self._stages:
            if s.id == stage_id:
                return s
        return None
