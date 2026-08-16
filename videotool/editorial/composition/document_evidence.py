"""document_evidence family - generative primary-source compositions.

Variants respond to the number of documents, the presence of a quote, and
beat density: single focus, stacked cascade, split compare, clip+annotation,
quote-led typographic.
"""
from __future__ import annotations

from videotool.domain.composition import (CompositionLayer, LayerType,
                                          MotionStyle, Relationship,
                                          VisualComposition)

from .base import CANVAS, CompositionContext, CompositionFamily, seed_rng


class DocumentEvidenceFamily(CompositionFamily):
    family_id = "document_evidence"
    description = "Primary-source led composition"

    def compose(self, ctx: CompositionContext) -> VisualComposition:
        rng = seed_rng(ctx.episode_id, ctx.beat.beat_id, "document", str(ctx.variant))
        cid = f"comp_{ctx.beat.beat_id}"
        docs = ctx.assets_of_kind("document")
        photos = ctx.assets_of_kind("photo", "portrait")
        has_quote = '"' in ctx.beat.narration_text or "said" in ctx.beat.narration_text.lower()
        variant = self._pick(ctx, docs, has_quote, rng)
        comp = VisualComposition(
            composition_id=cid, beat_id=ctx.beat.beat_id,
            visual_family=self.family_id, strategy=ctx.strategy.strategy_id,
            canvas=dict(CANVAS), duration_sec=ctx.beat.duration_sec)
        getattr(self, f"_v_{variant}")(ctx, comp, docs, photos, rng)
        comp.composition_reason = (f"variant={variant}; docs={len(docs)} "
                                   f"quote={has_quote}")
        return self._finish(ctx, comp)

    def _pick(self, ctx, docs, has_quote, rng) -> str:
        if not docs:
            return "quote_typographic" if has_quote else "clip_annotation"
        if has_quote and rng.random() < 0.6:
            return "doc_plus_quote"
        if len(docs) >= 3 and ctx.beat.semantic_function.value in ("ESCALATION",
                                                                   "ESTABLISHING_CONTEXT"):
            return "stacked_cascade"
        if len(docs) >= 2:
            return rng.choice(["split_compare", "stacked_cascade"])
        return rng.choice(["single_focus", "clip_annotation"])

    # ---- variants ------------------------------------------------------
    def _v_single_focus(self, ctx, comp, docs, photos, rng):
        comp.layers.append(CompositionLayer(
            id=f"{comp.composition_id}_doc", type=LayerType.DOCUMENT,
            x=0.14, y=0.07, width=0.72, height=0.70, z_index=10,
            role="document", asset_id=docs[0].asset_id,
            entrance=MotionStyle.DOCUMENT_UNFOLD, exit=MotionStyle.SLIDE_OUT,
            enter_at=0.0,
            reason="The source itself enters as narration cites evidence"))
        comp.layers.append(self._highlight(ctx, comp, 0.2, 0.52))
        comp.focus_target = f"{comp.composition_id}_doc"

    def _v_stacked_cascade(self, ctx, comp, docs, photos, rng):
        n = min(3, len(docs))
        for i in range(n):
            comp.layers.append(CompositionLayer(
                id=f"{comp.composition_id}_doc_{i}", type=LayerType.DOCUMENT,
                x=0.10 + i * 0.08, y=0.10 + i * 0.17, width=0.62,
                height=0.50, z_index=10 + i, role="hero" if i == n - 1 else "support",
                asset_id=docs[i].asset_id, rotation=(i - 1) * 3.0,
                entrance=MotionStyle.PAPER_SLIDE, exit=MotionStyle.COLLAPSE,
                enter_at=0.12 * i,
                reason="Corroborating sources accumulate as narration builds the record"))
        comp.relationships.extend(
            Relationship(from_layer=f"{comp.composition_id}_doc_{i}",
                         to_layer=f"{comp.composition_id}_doc_{i + 1}",
                         kind="groups", label="paper trail")
            for i in range(n - 1))
        comp.focus_target = f"{comp.composition_id}_doc_{n - 1}"

    def _v_split_compare(self, ctx, comp, docs, photos, rng):
        positions = [(0.05, 0.10, 0.42), (0.53, 0.16, 0.42)]
        for i in range(2):
            x, y, w = positions[i]
            comp.layers.append(CompositionLayer(
                id=f"{comp.composition_id}_doc_{i}", type=LayerType.DOCUMENT,
                x=x, y=y, width=w, height=0.64, z_index=10, role="hero" if i == 0 else "support",
                asset_id=docs[i].asset_id, rotation=1.5 * (1 - i),
                entrance=MotionStyle.SNAP_IN, exit=MotionStyle.SLIDE_OUT,
                enter_at=0.0 if i == 0 else 0.4,
                reason="Two sources set side by side for comparison"))
        comp.relationships.append(Relationship(
            from_layer=f"{comp.composition_id}_doc_0",
            to_layer=f"{comp.composition_id}_doc_1", kind="contrasts", label="compare"))
        comp.focus_target = f"{comp.composition_id}_doc_0"

    def _v_clip_annotation(self, ctx, comp, docs, photos, rng):
        base_x, base_y = 0.08, 0.10
        asset = docs[0].asset_id if docs else None
        comp.layers.append(CompositionLayer(
            id=f"{comp.composition_id}_doc", type=LayerType.DOCUMENT,
            x=base_x, y=base_y, width=0.52, height=0.66, z_index=10,
            role="document", asset_id=asset, entrance=MotionStyle.MASK_REVEAL,
            exit=MotionStyle.SLIDE_OUT, enter_at=0.0,
            reason="Source shown whole before the detail is isolated"))
        comp.layers.append(CompositionLayer(
            id=f"{comp.composition_id}_clip", type=LayerType.DOCUMENT,
            x=0.52, y=0.22, width=0.40, height=0.40, z_index=20, role="hero",
            asset_id=asset, entrance=MotionStyle.SCALE_EMPHASIS,
            exit=MotionStyle.COLLAPSE, enter_at=0.45,
            reason="Key passage enlarged as narration reads it"))
        comp.layers.append(self._highlight(ctx, comp, 0.55, 0.58))
        comp.focus_target = f"{comp.composition_id}_clip"

    def _v_doc_plus_quote(self, ctx, comp, docs, photos, rng):
        quote = self._quote_text(ctx)
        comp.layers.append(CompositionLayer(
            id=f"{comp.composition_id}_doc", type=LayerType.DOCUMENT,
            x=0.06, y=0.10, width=0.48, height=0.66, z_index=10,
            role="hero" if not docs else "document",
            asset_id=docs[0].asset_id if docs else None,
            entrance=MotionStyle.DOCUMENT_UNFOLD, exit=MotionStyle.SLIDE_OUT,
            enter_at=0.0, reason="Source material anchors the quotation"))
        comp.layers.append(CompositionLayer(
            id=f"{comp.composition_id}_quote", type=LayerType.TEXT, x=0.58,
            y=0.20, width=0.36, height=0.44, z_index=30, role="caption",
            text=quote, entrance=MotionStyle.TYPE_ON, exit=MotionStyle.DISSOLVE,
            enter_at=0.35,
            reason="The spoken/written line types on as it is voiced"))
        comp.focus_target = f"{comp.composition_id}_quote"

    def _v_quote_typographic(self, ctx, comp, docs, photos, rng):
        quote = self._quote_text(ctx)
        comp.layers.append(CompositionLayer(
            id=f"{comp.composition_id}_quote", type=LayerType.TEXT, x=0.10,
            y=0.18, width=0.80, height=0.50, z_index=10, role="hero",
            text=quote, entrance=MotionStyle.TYPE_ON, exit=MotionStyle.DISSOLVE,
            enter_at=0.0, reason="No source scan; the words carry the frame"))
        comp.layers.append(self._highlight(ctx, comp, 0.24, 0.64))
        comp.focus_target = f"{comp.composition_id}_quote"

    # ---- helpers ---------------------------------------------------------
    def _highlight(self, ctx, comp, x, y) -> CompositionLayer:
        return CompositionLayer(
            id=f"{comp.composition_id}_mark", type=LayerType.LINE, x=x, y=y,
            width=0.30, height=0.035, z_index=40, role="connector",
            entrance=MotionStyle.MARKER_LINE, exit=MotionStyle.DISSOLVE,
            enter_at=0.7,
            reason=f"Marker underlines the decisive detail "
                   f"(accent: {ctx.art_direction.accent.get('warning', 'red')})")

    def _quote_text(self, ctx) -> str:
        text = ctx.beat.narration_text
        if '"' in text:
            inside = text.split('"')[1::2]
            if inside:
                return f"\u201c{inside[0]}\u201d"
        return f"\u201c{text[:120]}\u201d"


FAMILY = DocumentEvidenceFamily()
