"""Generative composition family infrastructure (spec sections 7-9, 17-18).

A family is NOT a template: compose() responds to the beat's entities,
available assets, art direction and recent visual history. All placement is
normalized (0..1) and avoids the subtitle safe zone.
"""
from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass, field

from videotool.domain.art_direction import EpisodeArtDirection
from videotool.domain.assets import MediaAsset
from videotool.domain.composition import (CompositionLayer, EntranceStep,
                                          LayerType, MotionStyle,
                                          VisualComposition)
from videotool.domain.semantic_beat import SemanticBeat
from videotool.domain.strategy import StrategyDefinition
from videotool.domain.visual_history import VisualHistory, derive_signature

CANVAS = {"width": 1920, "height": 1080, "aspect": "16:9"}

# normalized rectangle (x, y, w, h) reserved for subtitles
SUBTITLE_SAFE_ZONE = (0.05, 0.84, 0.90, 0.15)

CRITICAL_ROLES = {"hero", "support", "connector", "chart", "map", "document"}


def seed_rng(*parts: str) -> random.Random:
    digest = hashlib.sha256("|".join(parts).encode()).hexdigest()
    return random.Random(int(digest[:16], 16))


def intersects_safe_zone(layer: CompositionLayer) -> bool:
    zx, zy, zw, zh = SUBTITLE_SAFE_ZONE
    ix = max(0.0, min(layer.x + layer.width, zx + zw) - max(layer.x, zx))
    iy = max(0.0, min(layer.y + layer.height, zy + zh) - max(layer.y, zy))
    area = ix * iy
    layer_area = max(layer.width * layer.height, 1e-6)
    return layer.role in CRITICAL_ROLES and area / layer_area > 0.10


@dataclass
class CompositionContext:
    beat: SemanticBeat
    strategy: StrategyDefinition
    art_direction: EpisodeArtDirection
    assets: list[MediaAsset] = field(default_factory=list)
    history: VisualHistory = field(default_factory=VisualHistory)
    episode_id: str = ""
    variant: int = 0

    def assets_of_kind(self, *kinds: str) -> list[MediaAsset]:
        return [a for a in self.assets if a.kind in kinds]

    def hero_asset(self) -> MediaAsset | None:
        for kind in ("photo", "portrait", "document", "map"):
            found = self.assets_of_kind(kind)
            if found:
                return found[0]
        return self.assets[0] if self.assets else None


class CompositionFamily:
    family_id: str = ""
    description: str = ""

    def compose(self, ctx: CompositionContext) -> VisualComposition:
        raise NotImplementedError

    # ---- shared helpers ----------------------------------------------
    def _finish(self, ctx: CompositionContext, comp: VisualComposition,
                mirror: bool = False) -> VisualComposition:
        if mirror:
            _mirror_composition(comp)
        comp.novelty_signature = derive_signature(comp)
        comp.duration_sec = ctx.beat.duration_sec
        _stagger_entrances(comp)
        _add_texture_if_fits(ctx, comp)
        return comp


def _mirror_composition(comp: VisualComposition) -> None:
    for layer in comp.layers:
        layer.x = round(1.0 - layer.x - layer.width, 4)
    comp.reading_order = list(reversed(comp.reading_order)) or comp.reading_order


def _stagger_entrances(comp: VisualComposition) -> None:
    """Progressive assembly (spec section 9): layers enter across the beat."""
    ordered = [l for l in comp.layers if l.type != LayerType.TEXTURE]
    ordered.sort(key=lambda l: (l.enter_at, l.z_index))
    n = max(1, len(ordered))
    comp.entrance_sequence = [
        EntranceStep(layer_id=l.id,
                     offset_sec=round(l.enter_at * comp.duration_sec, 3),
                     style=l.entrance.value,
                     reason=l.reason)
        for l in ordered
    ]
    comp.reading_order = comp.reading_order or [l.id for l in ordered]


def _add_texture_if_fits(ctx: CompositionContext, comp: VisualComposition) -> None:
    if any(l.type == LayerType.TEXTURE for l in comp.layers):
        return
    grain = CompositionLayer(
        id=f"{comp.composition_id}_paper_texture", type=LayerType.TEXTURE,
        x=0.0, y=0.0, width=1.0, height=1.0, z_index=1,
        role="texture", entrance=MotionStyle.DISSOLVE, exit=MotionStyle.DISSOLVE,
        enter_at=0.0,
        reason=f"Episode archival language: {ctx.art_direction.archival_language[0] if ctx.art_direction.archival_language else 'paper'}")
    comp.layers.append(grain)


def compose_with_distinct_signature(family: CompositionFamily,
                                    ctx: CompositionContext,
                                    used_signatures: set[str],
                                    max_tries: int = 6) -> VisualComposition:
    """Ask the family for compositions until signature is genuinely new.

    Mirroring doubles the variant space; identical signature reuse is a hard
    constraint (spec section 10).
    """
    last: VisualComposition | None = None
    for variant in range(max_tries):
        ctx.variant = variant
        comp = family.compose(ctx)
        if variant % 2 == 1:
            # odd variants mirror the arrangement: doubles structural space
            _mirror_composition(comp)
            comp.novelty_signature = derive_signature(comp)
            _stagger_entrances(comp)
        last = comp
        if comp.novelty_signature not in used_signatures:
            return comp
    assert last is not None
    return last
