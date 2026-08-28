"""Discrete pipeline stage implementations (spec section 20)."""
from __future__ import annotations

from .art_direction import EpisodeArtDirectionStage
from .asset_requirements import AssetRequirementsStage
from .chapter_outline import ChapterOutlineStage
from .chapter_scriptwriting import ChapterScriptwritingStage
from .composition import VisualCompositionsStage
from .fact_registry import FactRegistryStage
from .feasibility import StrategyFeasibilityStage
from .geometry import SemanticGeometryStage
from .master_assembly import MasterAssemblyStage
from .media import (
    MediaAcquisitionResultStage,
    MediaAcquisitionTraceStage,
    MediaAssetsStage,
    MediaAttributionStage,
    MediaCandidatesStage,
    MediaSearchPlanStage,
)
from .motion import MotionPlanStage
from .narration_timing import NarrationTimingStage
from .scene_compilation import SceneCompilationStage
from .semantic_anchors import SemanticAnchorsStage
from .semantic_beats import SemanticBeatsStage
from .strategy import VisualStrategyPlanStage
from .timeline import TimelineStage
from .timing_bindings import TimingBindingsStage
from .visual_history import VisualHistoryStage

__all__ = [
    "FactRegistryStage",
    "ChapterOutlineStage",
    "ChapterScriptwritingStage",
    "NarrationTimingStage",
    "SemanticBeatsStage",
    "SemanticAnchorsStage",
    "EpisodeArtDirectionStage",
    "VisualStrategyPlanStage",
    "AssetRequirementsStage",
    "MediaSearchPlanStage",
    "MediaCandidatesStage",
    "MediaAcquisitionResultStage",
    "MediaAssetsStage",
    "MediaAcquisitionTraceStage",
    "MediaAttributionStage",
    "StrategyFeasibilityStage",
    "VisualCompositionsStage",
    "VisualHistoryStage",
    "TimingBindingsStage",
    "SemanticGeometryStage",
    "MotionPlanStage",
    "TimelineStage",
    "SceneCompilationStage",
    "MasterAssemblyStage",
]
