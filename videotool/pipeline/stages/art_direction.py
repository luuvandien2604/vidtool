"""Episode art direction pipeline stage."""
from __future__ import annotations

from typing import Any

from videotool.domain.art_direction import EpisodeArtDirection
from videotool.editorial import validation
from videotool.pipeline.context import PipelineContext
from videotool.pipeline.fingerprints import stable_hash
from videotool.pipeline.stage import BasePipelineStage


class EpisodeArtDirectionStage(BasePipelineStage):
    id = "episode_art_direction"

    def fingerprint(self, ctx: PipelineContext) -> str:
        return stable_hash(
            self.version,
            ctx.episode_id,
            ctx.episode.subject,
            ctx.state["semantic_narration_payload"],
            ctx.state["beats_semantic_hash"],
        )

    def execute(self, ctx: PipelineContext) -> dict:
        ad = ctx.art_director.generate(
            ctx.episode_id,
            ctx.episode.subject,
            ctx.state["timed_narration"],
            ctx.state["beats"],
        )
        if not ad.visual_motifs or not ad.accent.get("primary"):
            ctx.record_repair(
                "episode_art_direction",
                "generated identity incomplete",
                "deterministic fallback art direction",
            )
            ad = validation.fallback_art_direction(ctx.episode_id, ctx.episode.subject)
        return ad.to_dict()

    def validate(self, payload: Any, ctx: PipelineContext) -> bool:
        try:
            ad = EpisodeArtDirection.from_dict(payload)
        except Exception:
            return False
        return bool(ad.visual_motifs) and bool(ad.accent.get("primary"))
