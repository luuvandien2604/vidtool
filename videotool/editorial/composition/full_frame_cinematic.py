"""full_frame_cinematic family - one image allowed to breathe.

Variants: pure hold, letterboxed hold with a single editorial line,
hold+quote. Restrained by design; the camera stays stable, motion comes
from the single caption element.
"""
from __future__ import annotations

from videotool.domain.composition import (CompositionLayer, LayerType,
                                          MotionStyle, VisualComposition)

from .base import CANVAS, CompositionContext, CompositionFamily, seed_rng


class FullFrameCinematicFamily(CompositionFamily):
    family_id = "full_frame_cinematic"
    description = "Single full-bleed cinematic frame"

    def compose(self, ctx: CompositionContext) -> VisualComposition:
        rng = seed_rng(ctx.episode_id, ctx.beat.beat_id, "cinematic", str(ctx.variant))
        cid = f"comp_{ctx.beat.beat_id}"
        visuals = ctx.assets_of_kind("photo", "portrait", "map", "document")
        has_quote = '"' in ctx.beat.narration_text
        variant = self._pick(has_quote, rng)
        comp = VisualComposition(
            composition_id=cid, beat_id=ctx.beat.beat_id,
            visual_family=self.family_id, strategy=ctx.strategy.strategy_id,
            canvas=dict(CANVAS), duration_sec=ctx.beat.duration_sec)
        getattr(self, f"_v_{variant}")(ctx, comp, visuals, rng)
        comp.composition_reason = f"variant={variant}; assets={len(visuals)}"
        return self._finish(ctx, comp)

    def _pick(self, has_quote, rng) -> str:
        if has_quote:
            return rng.choice(["hold_quote", "letterbox_quote"])
        return rng.choice(["pure_hold", "letterbox_line"])

    # ---- variants --------------------------------------------------------
    def _hero(self, ctx, comp, visuals, entrance=MotionStyle.MASK_REVEAL):
        return CompositionLayer(
            id=f"{comp.composition_id}_hero", type=LayerType.IMAGE, x=0.0,
            y=0.0, width=1.0, height=0.82, z_index=10, role="hero",
            asset_id=visuals[0].asset_id if visuals else None,
            entrance=entrance, exit=MotionStyle.DISSOLVE, enter_at=0.0,
            reason="Full-bleed frame holds while narration carries the moment")

    def _v_pure_hold(self, ctx, comp, visuals, rng):
        comp.layers.append(self._hero(ctx, comp, visuals))
        comp.focus_target = f"{comp.composition_id}_hero"

    def _v_letterbox_line(self, ctx, comp, visuals, rng):
        comp.layers.append(self._hero(ctx, comp, visuals))
        line = CompositionLayer(
            id=f"{comp.composition_id}_line", type=LayerType.TEXT,
            x=0.08 if rng.random() < 0.5 else 0.42, y=0.70, width=0.50,
            height=0.07, z_index=30, role="caption",
            text=self._line_text(ctx), entrance=MotionStyle.UNDERLINE_REVEAL,
            exit=MotionStyle.DISSOLVE, enter_at=0.55,
            reason="One editorial line lands as the beat resolves")
        comp.layers.append(line)
        comp.focus_target = line.id

    def _v_hold_quote(self, ctx, comp, visuals, rng):
        comp.layers.append(self._hero(ctx, comp, visuals))
        quote = CompositionLayer(
            id=f"{comp.composition_id}_quote", type=LayerType.TEXT, x=0.10,
            y=0.30, width=0.55, height=0.36, z_index=30, role="caption",
            text=self._quote_text(ctx), entrance=MotionStyle.TYPE_ON,
            exit=MotionStyle.DISSOLVE, enter_at=0.35,
            reason="Quotation types over the frame as it is spoken")
        comp.layers.append(quote)
        comp.focus_target = quote.id

    def _v_letterbox_quote(self, ctx, comp, visuals, rng):
        comp.layers.append(self._hero(ctx, comp, visuals,
                                      entrance=MotionStyle.CUT_IN))
        comp.layers.append(CompositionLayer(
            id=f"{comp.composition_id}_band", type=LayerType.SHAPE, x=0.0,
            y=0.62, width=1.0, height=0.20, z_index=20, role="support",
            entrance=MotionStyle.MASK_REVEAL, exit=MotionStyle.DISSOLVE,
            enter_at=0.3,
            reason="Letterbox band isolates the quotation"))
        comp.layers.append(CompositionLayer(
            id=f"{comp.composition_id}_quote", type=LayerType.TEXT, x=0.10,
            y=0.68, width=0.80, height=0.10, z_index=30, role="caption",
            text=self._quote_text(ctx), entrance=MotionStyle.TYPE_ON,
            exit=MotionStyle.DISSOLVE, enter_at=0.45,
            reason="The line types on inside the band"))
        comp.focus_target = f"{comp.composition_id}_quote"

    # ---- helpers ---------------------------------------------------------
    def _line_text(self, ctx) -> str:
        words = ctx.beat.narration_text.split()
        return " ".join(words[:9])

    def _quote_text(self, ctx) -> str:
        text = ctx.beat.narration_text
        if '"' in text:
            inside = text.split('"')[1::2]
            if inside:
                return f"\u201c{inside[0]}\u201d"
        return f"\u201c{' '.join(text.split()[:12])}\u201d"


FAMILY = FullFrameCinematicFamily()
