"""Context projection layer for the AI Editorial Director (Phase 3A).

Projects rich domain and episode states into clean, compact, sanitized
request DTOs without leaking internal engine weights or private runner state.
"""
from __future__ import annotations

from typing import Any

from videotool.domain.art_direction import EpisodeArtDirection
from videotool.domain.semantic_beat import SemanticBeat
from videotool.domain.strategy import StrategyDefinition
from videotool.domain.visual_history import EpisodeVisualMemory
from videotool.editorial.composition import FAMILIES
from videotool.editorial.director.models import (
    EditorialDirectorRequest,
    StrategyDescriptor,
)
from videotool.editorial.strategies import FUNCTION_CANDIDATES, STRATEGY_CATALOG


class EditorialContextProjector:
    """Projects internal pipeline state into a clean EditorialDirectorRequest."""

    @staticmethod
    def project_beat(
        beat: SemanticBeat,
        art_direction: EpisodeArtDirection | None = None,
        visual_memory: EpisodeVisualMemory | None = None,
        catalog: dict[str, StrategyDefinition] | None = None,
        families: dict[str, Any] | None = None,
    ) -> EditorialDirectorRequest:
        catalog_map = catalog if catalog is not None else STRATEGY_CATALOG
        family_map = families if families is not None else FAMILIES
        memory = visual_memory if visual_memory is not None else EpisodeVisualMemory()

        # 1. Identify relevant candidate strategy descriptors for this beat
        # Primary candidate IDs from semantic function
        candidate_ids = list(FUNCTION_CANDIDATES.get(beat.semantic_function, ["cinematic_hold"]))
        if beat.locations and "region_map" not in candidate_ids:
            candidate_ids.append("region_map")
        if beat.dates and "linear_timeline" not in candidate_ids:
            candidate_ids.append("linear_timeline")

        descriptors: list[StrategyDescriptor] = []
        for sid in candidate_ids:
            s_def = catalog_map.get(sid)
            if s_def is not None:
                descriptors.append(StrategyDescriptor(
                    strategy_id=s_def.strategy_id,
                    visual_family=s_def.visual_family,
                    compatible_functions=list(s_def.functions),
                    storytelling_note=s_def.storytelling_note,
                ))

        # 2. Extract visual memory projection
        recent_entries = memory.recent(6)
        recent_families = [e.visual_family for e in recent_entries]
        recent_strategies = [e.strategy for e in recent_entries]
        streak_family, streak_len = memory.family_streak()

        # 3. Extract art direction summary
        motifs = list(art_direction.visual_motifs) if art_direction else []
        accent = str(art_direction.accent.get("primary", "#E6C280")) if art_direction else "#E6C280"

        return EditorialDirectorRequest(
            beat_id=beat.beat_id,
            semantic_function=beat.semantic_function.value,
            narration_text=beat.narration_text,
            entities=list(beat.entities),
            locations=list(beat.locations),
            dates=list(beat.dates),
            information_density=float(beat.information_density),
            art_direction_motifs=motifs,
            accent_color=accent,
            recent_families=recent_families,
            recent_strategies=recent_strategies,
            family_streak=(streak_family, streak_len),
            candidate_descriptors=descriptors,
            available_families=sorted(family_map.keys()),
        )
