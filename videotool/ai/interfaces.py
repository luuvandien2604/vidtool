"""Interfaces behind which AI models live (spec section 28).

Phase 1 ships deterministic heuristic implementations so the whole pipeline
is testable offline. An LLM-backed provider can be swapped in later without
touching the planning stages: every AI output still passes through the same
deterministic validation/repair layer.
"""
from __future__ import annotations

from typing import Protocol

from videotool.domain.narration import Narration
from videotool.domain.semantic_beat import SemanticBeat
from videotool.domain.art_direction import EpisodeArtDirection


class BeatAnalyzer(Protocol):
    """Narration + timing -> semantic beats."""

    def analyze(self, narration: Narration, episode_id: str) -> list[SemanticBeat]: ...


class ArtDirectionGenerator(Protocol):
    """Topic + narration + beats -> per-episode visual identity."""

    def generate(self, episode_id: str, subject: str,
                 narration: Narration, beats: list[SemanticBeat]) -> EpisodeArtDirection: ...


class MediaAcquirer(Protocol):
    """Semantic asset requirements -> scored, resolved media assets."""
