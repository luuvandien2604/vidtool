"""paper_collage_hero family - generative editorial torn-paper collage compositions.

Arrangement responds to: archival hero backdrop, chapter/contextual narrative,
secondary inset assets (maps, documents, portraits) with tape strips, and high-impact
keyword-grounded quotes.
"""
from __future__ import annotations

from videotool.domain.composition import (CompositionLayer, LayerType,
                                          MotionStyle, VisualComposition)
from videotool.domain.semantic_beat import SemanticFunction

from .base import CANVAS, CompositionContext, CompositionFamily, seed_rng


class PaperCollageHeroFamily(CompositionFamily):
    family_id = "paper_collage_hero"
    description = "Editorial torn-paper collage with hero backdrop and pinned insets"

    def compose(self, ctx: CompositionContext) -> VisualComposition:
        rng = seed_rng(ctx.episode_id, ctx.beat.beat_id, "collage", str(ctx.variant))
        cid = f"comp_{ctx.beat.beat_id}"
        photos = ctx.assets_of_kind("photo", "portrait")
        maps = ctx.assets_of_kind("map")
        docs = ctx.assets_of_kind("document")

        variant = self._pick_variant(ctx, photos, maps, docs, rng)
        comp = VisualComposition(
            composition_id=cid,
            beat_id=ctx.beat.beat_id,
            visual_family=self.family_id,
            strategy=ctx.strategy.strategy_id,
            canvas=dict(CANVAS),
            focus_target=f"{cid}_hero",
            duration_sec=ctx.beat.duration_sec,
        )
        getattr(self, f"_v_{variant}")(ctx, comp, photos, maps, docs, rng)
        comp.composition_reason = (
            f"variant={variant}; photos={len(photos)} maps={len(maps)} docs={len(docs)} "
            f"function={ctx.beat.semantic_function.value}"
        )
        return self._finish(ctx, comp)

    def _pick_variant(self, ctx: CompositionContext, photos, maps, docs, rng) -> str:
        candidates = ["hero_chapter_opener"]
        if maps:
            candidates.append("hero_plus_taped_map")
        if docs:
            candidates.append("hero_plus_taped_document")
        if len(photos) >= 2:
            candidates.append("hero_plus_taped_photo")
        return rng.choice(candidates)

    # ---- variants ----------------------------------------------------
    def _v_hero_chapter_opener(self, ctx, comp, photos, maps, docs, rng):
        # 1. Archival Hero Background (safe zone compliant)
        hero_asset = photos[0] if photos else (ctx.assets[0] if ctx.assets else None)
        comp.layers.append(CompositionLayer(
            id=f"{comp.composition_id}_hero",
            type=LayerType.IMAGE,
            x=0.05, y=0.05, width=0.90, height=0.74,
            z_index=10, role="hero",
            asset_id=hero_asset.asset_id if hero_asset else None,
            entrance=MotionStyle.MASK_REVEAL,
            exit=MotionStyle.DISSOLVE,
            enter_at=0.0,
            reason="Full-bleed archival hero backdrop with slow push"
        ))
        # 2. Torn-paper Sidebar Container
        comp.layers.append(CompositionLayer(
            id=f"{comp.composition_id}_torn_sidebar",
            type=LayerType.SHAPE,
            x=0.0, y=0.0, width=0.38, height=0.80,
            z_index=20, role="support",
            entrance=MotionStyle.PAPER_SLIDE,
            exit=MotionStyle.DISSOLVE,
            enter_at=0.0,
            reason="Torn-paper sidebar panel anchoring chapter badge and context"
        ))
        # 3. Chapter & Headline Label
        title_text = ctx.beat.entities[0] if ctx.beat.entities else ctx.beat.visual_intent or "BỐI CẢNH"
        comp.layers.append(CompositionLayer(
            id=f"{comp.composition_id}_headline",
            type=LayerType.LABEL,
            x=0.04, y=0.12, width=0.30, height=0.15,
            z_index=30, role="caption",
            text=str(title_text),
            entrance=MotionStyle.UNDERLINE_REVEAL,
            exit=MotionStyle.DISSOLVE,
            enter_at=0.2,
            reason="Headline and chapter pill on torn paper"
        ))
        # 4. Gold Milestone Date Card
        if ctx.beat.dates:
            comp.layers.append(CompositionLayer(
                id=f"{comp.composition_id}_fact_card",
                type=LayerType.TEXT,
                x=0.04, y=0.68, width=0.30, height=0.10,
                z_index=35, role="caption",
                text=f"{ctx.beat.dates[0]} · {title_text}",
                entrance=MotionStyle.SNAP_IN,
                exit=MotionStyle.DISSOLVE,
                enter_at=0.4,
                reason="Gold framed milestone date card"
            ))

    def _v_hero_plus_taped_map(self, ctx, comp, photos, maps, docs, rng):
        self._v_hero_chapter_opener(ctx, comp, photos, maps, docs, rng)
        # Add taped map inset top-right
        comp.layers.append(CompositionLayer(
            id=f"{comp.composition_id}_inset_map",
            type=LayerType.MAP,
            x=0.60, y=0.08, width=0.34, height=0.36,
            z_index=25, role="support",
            asset_id=maps[0].asset_id if maps else None,
            entrance=MotionStyle.SNAP_IN,
            exit=MotionStyle.DISSOLVE,
            enter_at=0.3,
            reason="Taped regional map inset in upper right"
        ))

    def _v_hero_plus_taped_document(self, ctx, comp, photos, maps, docs, rng):
        self._v_hero_chapter_opener(ctx, comp, photos, maps, docs, rng)
        comp.layers.append(CompositionLayer(
            id=f"{comp.composition_id}_inset_doc",
            type=LayerType.DOCUMENT,
            x=0.60, y=0.08, width=0.34, height=0.36,
            z_index=25, role="support",
            asset_id=docs[0].asset_id if docs else None,
            entrance=MotionStyle.SNAP_IN,
            exit=MotionStyle.DISSOLVE,
            enter_at=0.3,
            reason="Taped archival document inset in upper right"
        ))

    def _v_hero_plus_taped_photo(self, ctx, comp, photos, maps, docs, rng):
        self._v_hero_chapter_opener(ctx, comp, photos, maps, docs, rng)
        secondary_photo = photos[1]
        comp.layers.append(CompositionLayer(
            id=f"{comp.composition_id}_inset_photo",
            type=LayerType.IMAGE,
            x=0.60, y=0.08, width=0.34, height=0.36,
            z_index=25, role="support",
            asset_id=secondary_photo.asset_id,
            entrance=MotionStyle.PLACE_PHOTO,
            exit=MotionStyle.DISSOLVE,
            enter_at=0.3,
            reason="Taped secondary archival photo inset"
        ))


FAMILY = PaperCollageHeroFamily()
