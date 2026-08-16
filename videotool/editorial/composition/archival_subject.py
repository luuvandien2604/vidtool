"""archival_subject family - generative portrait/subject compositions.

Arrangement responds to: how many subject assets exist, whether a document or
location co-occurs, beat density and recent history. Variants: full-frame,
third left/right, offset-with-document, duo-panel, typographic (no photo).
"""
from __future__ import annotations

from videotool.domain.composition import (CompositionLayer, LayerType,
                                          MotionStyle, Relationship,
                                          VisualComposition)
from videotool.domain.semantic_beat import SemanticFunction

from .base import CANVAS, CompositionContext, CompositionFamily, seed_rng


def _name_layer(ctx: CompositionContext, cid: str) -> CompositionLayer:
    who = ctx.beat.entities[0] if ctx.beat.entities else ctx.beat.locations[0] if ctx.beat.locations else "the subject"
    when = ctx.beat.dates[0] if ctx.beat.dates else ""
    return who, CompositionLayer(
        id=f"{cid}_name", type=LayerType.TEXT, x=0.06, y=0.66, width=0.34,
        height=0.07, z_index=30, role="caption", text=f"{who}{f' · {when}' if when else ''}",
        entrance=MotionStyle.TYPE_ON, exit=MotionStyle.SLIDE_OUT,
        enter_at=0.35, reason="Identity appears as narration names the subject")


class ArchivalSubjectFamily(CompositionFamily):
    family_id = "archival_subject"
    description = "Person/subject-led archival composition"

    def compose(self, ctx: CompositionContext) -> VisualComposition:
        rng = seed_rng(ctx.episode_id, ctx.beat.beat_id, "archival", str(ctx.variant))
        cid = f"comp_{ctx.beat.beat_id}"
        photos = ctx.assets_of_kind("photo", "portrait")
        docs = ctx.assets_of_kind("document")
        variant = self._pick_variant(ctx, photos, docs, rng)
        comp = VisualComposition(
            composition_id=cid, beat_id=ctx.beat.beat_id,
            visual_family=self.family_id, strategy=ctx.strategy.strategy_id,
            canvas=dict(CANVAS), focus_target="", duration_sec=ctx.beat.duration_sec,
        )
        getattr(self, f"_v_{variant}")(ctx, comp, photos, docs, rng)
        comp.composition_reason = (
            f"variant={variant}; photos={len(photos)} docs={len(docs)} "
            f"function={ctx.beat.semantic_function.value}")
        return self._finish(ctx, comp)

    def _pick_variant(self, ctx: CompositionContext, photos, docs, rng) -> str:
        if not photos:
            return "typographic"
        if ctx.beat.semantic_function == SemanticFunction.CHARACTER_INTRODUCTION and docs:
            return rng.choice(["offset_lower_doc", "duo_panel", "third_left"])
        if len(photos) >= 2 and rng.random() < 0.5:
            return "duo_panel"
        if ctx.beat.semantic_function in (SemanticFunction.HOOK, SemanticFunction.REVEAL,
                                          SemanticFunction.TURNING_POINT):
            return rng.choice(["full_frame", "third_left", "third_right"])
        return rng.choice(["third_left", "third_right", "offset_lower_doc"])

    # ---- variants ------------------------------------------------------
    def _v_full_frame(self, ctx, comp, photos, docs, rng):
        comp.layers.append(CompositionLayer(
            id=f"{comp.composition_id}_hero", type=LayerType.IMAGE, x=0.05, y=0.05,
            width=0.90, height=0.74, z_index=10, role="hero",
            asset_id=photos[0].asset_id, entrance=MotionStyle.MASK_REVEAL,
            exit=MotionStyle.DISSOLVE, enter_at=0.0,
            reason="Single arresting frame as narration opens on the subject"))
        who, nl = _name_layer(ctx, comp.composition_id)
        comp.layers.append(nl)
        comp.focus_target = nl.id

    def _v_third_left(self, ctx, comp, photos, docs, rng):
        self._third(ctx, comp, photos, 0.06, "left")

    def _v_third_right(self, ctx, comp, photos, docs, rng):
        self._third(ctx, comp, photos, 0.55, "right")

    def _third(self, ctx, comp, photos, x, side):
        comp.layers.append(CompositionLayer(
            id=f"{comp.composition_id}_hero", type=LayerType.IMAGE, x=x, y=0.10,
            width=0.39, height=0.66, z_index=10, role="hero",
            asset_id=photos[0].asset_id, entrance=MotionStyle.PLACE_PHOTO,
            exit=MotionStyle.SLIDE_OUT, enter_at=0.0,
            reason=f"Portrait placed {side} as narration introduces the person"))
        who, nl = _name_layer(ctx, comp.composition_id)
        if side == "left":
            nl.x = 0.50
        comp.layers.append(nl)
        meta = CompositionLayer(
            id=f"{comp.composition_id}_role", type=LayerType.LABEL,
            x=nl.x, y=0.75, width=0.40, height=0.06, z_index=30, role="caption",
            text=self._role_text(ctx), entrance=MotionStyle.UNDERLINE_REVEAL,
            exit=MotionStyle.SLIDE_OUT, enter_at=0.55,
            reason="Role/context line completes the introduction")
        comp.layers.append(meta)
        comp.focus_target = nl.id

    def _v_offset_lower_doc(self, ctx, comp, photos, docs, rng):
        comp.layers.append(CompositionLayer(
            id=f"{comp.composition_id}_hero", type=LayerType.IMAGE,
            x=0.08 + rng.uniform(0, 0.06), y=0.08, width=0.46, height=0.62,
            z_index=10, role="hero", asset_id=photos[0].asset_id,
            entrance=MotionStyle.PLACE_PHOTO, exit=MotionStyle.SLIDE_OUT,
            enter_at=0.0, reason="Portrait placed while narration introduces the person"))
        if docs:
            comp.layers.append(CompositionLayer(
                id=f"{comp.composition_id}_doc", type=LayerType.DOCUMENT,
                x=0.52, y=0.30, width=0.40, height=0.44, z_index=20,
                role="document", asset_id=docs[0].asset_id, rotation=-4.0,
                entrance=MotionStyle.DOCUMENT_UNFOLD, exit=MotionStyle.SLIDE_OUT,
                enter_at=0.5,
                reason="Document the person produced enters as narration cites it"))
            comp.relationships.append(Relationship(
                from_layer=f"{comp.composition_id}_hero",
                to_layer=f"{comp.composition_id}_doc", kind="annotates",
                label="authored"))
        who, nl = _name_layer(ctx, comp.composition_id)
        nl.y = 0.74
        comp.layers.append(nl)
        comp.focus_target = f"{comp.composition_id}_hero"

    def _v_duo_panel(self, ctx, comp, photos, docs, rng):
        gap = 0.06
        w = (1.0 - 3 * gap) / 2
        for i, photo in enumerate(photos[:2]):
            comp.layers.append(CompositionLayer(
                id=f"{comp.composition_id}_hero_{i}", type=LayerType.IMAGE,
                x=gap + i * (w + gap), y=0.12, width=w, height=0.62, z_index=10,
                role="hero" if i == 0 else "support", asset_id=photo.asset_id,
                entrance=MotionStyle.PLACE_PHOTO, exit=MotionStyle.SLIDE_OUT,
                enter_at=0.0 if i == 0 else 0.45,
                reason="Second archival frame placed as narration widens the subject"))
        cap = CompositionLayer(
            id=f"{comp.composition_id}_caption", type=LayerType.TEXT, x=0.06,
            y=0.76, width=0.88, height=0.06, z_index=30, role="caption",
            text=self._role_text(ctx), entrance=MotionStyle.UNDERLINE_REVEAL,
            exit=MotionStyle.SLIDE_OUT, enter_at=0.6,
            reason="Caption binds both frames to the narration")
        comp.layers.append(cap)
        comp.focus_target = f"{comp.composition_id}_hero_0"
        comp.relationships.append(Relationship(
            from_layer=f"{comp.composition_id}_hero_0",
            to_layer=f"{comp.composition_id}_hero_1", kind="contrasts",
            label="context"))

    def _v_typographic(self, ctx, comp, photos, docs, rng):
        who = ctx.beat.entities[0] if ctx.beat.entities else ctx.beat.narration_text.split()[0:2]
        who = who if isinstance(who, str) else " ".join(who)
        comp.layers.append(CompositionLayer(
            id=f"{comp.composition_id}_hero", type=LayerType.TEXT, x=0.08,
            y=0.18, width=0.60, height=0.30, z_index=10, role="hero",
            text=who, entrance=MotionStyle.TYPE_ON, exit=MotionStyle.DISSOLVE,
            enter_at=0.0, reason="No portrait asset; identity carried typographically"))
        sub = CompositionLayer(
            id=f"{comp.composition_id}_sub", type=LayerType.LABEL, x=0.08,
            y=0.50, width=0.70, height=0.10, z_index=20, role="caption",
            text=ctx.beat.narration_text[:110], entrance=MotionStyle.UNDERLINE_REVEAL,
            exit=MotionStyle.SLIDE_OUT, enter_at=0.4,
            reason="Narration excerpt holds the frame as text evidence")
        comp.layers.append(sub)
        comp.focus_target = f"{comp.composition_id}_hero"

    def _role_text(self, ctx) -> str:
        bits = []
        if ctx.beat.entities:
            bits.append(ctx.beat.entities[0])
        if ctx.beat.dates:
            bits.append(ctx.beat.dates[0])
        if ctx.beat.locations:
            bits.append(ctx.beat.locations[0])
        return " · ".join(bits) or ctx.art_direction.subject


FAMILY = ArchivalSubjectFamily()
