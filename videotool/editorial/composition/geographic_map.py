"""geographic_map family - generative map compositions.

Variants: region focus, route trace, annotated callouts, map+archival split.
Route lines appear only when the beat narrates movement; callouts when data
is voiced; archival overlay when a photo of the place exists.
"""
from __future__ import annotations

from videotool.domain.composition import (CompositionLayer, LayerType,
                                          MotionStyle, Relationship,
                                          VisualComposition)
from videotool.domain.semantic_beat import SemanticFunction

from .base import CANVAS, CompositionContext, CompositionFamily, seed_rng


class GeographicMapFamily(CompositionFamily):
    family_id = "geographic_map"
    description = "Geography-led composition"

    def compose(self, ctx: CompositionContext) -> VisualComposition:
        rng = seed_rng(ctx.episode_id, ctx.beat.beat_id, "map", str(ctx.variant))
        cid = f"comp_{ctx.beat.beat_id}"
        maps = ctx.assets_of_kind("map")
        photos = ctx.assets_of_kind("photo", "portrait")
        variant = self._pick(ctx, maps, photos, rng)
        comp = VisualComposition(
            composition_id=cid, beat_id=ctx.beat.beat_id,
            visual_family=self.family_id, strategy=ctx.strategy.strategy_id,
            canvas=dict(CANVAS), duration_sec=ctx.beat.duration_sec)
        getattr(self, f"_v_{variant}")(ctx, comp, maps, photos, rng)
        comp.composition_reason = (f"variant={variant}; maps={len(maps)} "
                                   f"photos={len(photos)} "
                                   f"movement={'movement' in ctx.beat.relationships or ctx.beat.semantic_function == SemanticFunction.GEOGRAPHIC_MOVEMENT}")
        return self._finish(ctx, comp)

    def _pick(self, ctx, maps, photos, rng) -> str:
        fn = ctx.beat.semantic_function
        if fn == SemanticFunction.GEOGRAPHIC_MOVEMENT or ctx.beat.locations:
            if fn == SemanticFunction.GEOGRAPHIC_MOVEMENT:
                return rng.choice(["route_trace", "flow_field"])
            if photos and rng.random() < 0.5:
                return "map_plus_archival"
            if ctx.beat.dates or "%" in ctx.beat.narration_text or "thousand" in ctx.beat.narration_text.lower():
                return "annotated_map"
        return rng.choice(["region_focus", "route_trace", "annotated_map"])

    def _map_layer(self, ctx, comp, maps, x, y, w, h) -> CompositionLayer:
        return CompositionLayer(
            id=f"{comp.composition_id}_map", type=LayerType.MAP, x=x, y=y,
            width=w, height=h, z_index=10, role="hero" if w > 0.5 else "support",
            asset_id=maps[0].asset_id if maps else None,
            entrance=MotionStyle.MASK_REVEAL, exit=MotionStyle.SLIDE_OUT,
            enter_at=0.0,
            reason=f"Map establishes {ctx.beat.locations[0] if ctx.beat.locations else 'the region'} as narration situates events")

    def _place_label(self, ctx, comp, x, y, text, at=0.3, z=30) -> CompositionLayer:
        return CompositionLayer(
            id=f"{comp.composition_id}_lbl_{len(comp.layers)}", type=LayerType.LABEL,
            x=x, y=y, width=0.22, height=0.055, z_index=z, role="caption",
            text=text, entrance=MotionStyle.UNDERLINE_REVEAL,
            exit=MotionStyle.SLIDE_OUT, enter_at=at,
            reason="Place name labeled as narration mentions it")

    # ---- variants --------------------------------------------------------
    def _v_region_focus(self, ctx, comp, maps, photos, rng):
        comp.layers.append(self._map_layer(ctx, comp, maps, 0.12, 0.07, 0.76, 0.70))
        loc = ctx.beat.locations[0] if ctx.beat.locations else (ctx.beat.entities[0] if ctx.beat.entities else "region")
        region = CompositionLayer(
            id=f"{comp.composition_id}_region", type=LayerType.SHAPE,
            x=0.38 + rng.uniform(-0.06, 0.06), y=0.25, width=0.24, height=0.30,
            z_index=20, role="support", entrance=MotionStyle.MASK_REVEAL,
            exit=MotionStyle.DISSOLVE, enter_at=0.4,
            reason=f"Region {loc} highlighted while narration dwells on it")
        comp.layers.append(region)
        comp.layers.append(self._place_label(ctx, comp, 0.40, 0.58, str(loc), at=0.5))
        comp.focus_target = region.id

    def _v_route_trace(self, ctx, comp, maps, photos, rng):
        comp.layers.append(self._map_layer(ctx, comp, maps, 0.07, 0.08, 0.86, 0.68))
        route = CompositionLayer(
            id=f"{comp.composition_id}_route", type=LayerType.LINE,
            x=0.30, y=0.45, width=0.40, height=0.10, z_index=25,
            role="connector", entrance=MotionStyle.ROUTE_DRAW,
            exit=MotionStyle.DISSOLVE, enter_at=0.35, rotation=-8.0,
            reason="Route draws as narration describes the path of movement")
        comp.layers.append(route)
        for i, (mx, my, tag) in enumerate([(0.24, 0.40, "origin"), (0.68, 0.32, "destination")]):
            comp.layers.append(CompositionLayer(
                id=f"{comp.composition_id}_pin_{i}", type=LayerType.ICON,
                x=mx, y=my, width=0.05, height=0.07, z_index=30, role="connector",
                entrance=MotionStyle.PIN_CONNECT, exit=MotionStyle.DISSOLVE,
                enter_at=0.30 + 0.25 * i,
                reason=f"{tag.capitalize()} pinned when narration reaches it"))
        loc0 = ctx.beat.locations[0] if ctx.beat.locations else "origin"
        loc1 = ctx.beat.locations[1] if len(ctx.beat.locations) > 1 else "destination"
        comp.layers.append(self._place_label(ctx, comp, 0.20, 0.50, str(loc0), at=0.45))
        comp.layers.append(self._place_label(ctx, comp, 0.66, 0.42, str(loc1), at=0.6))
        comp.relationships.append(Relationship(
            from_layer=f"{comp.composition_id}_pin_0",
            to_layer=f"{comp.composition_id}_pin_1", kind="connects", label="route"))
        comp.focus_target = route.id

    def _v_flow_field(self, ctx, comp, maps, photos, rng):
        comp.layers.append(self._map_layer(ctx, comp, maps, 0.10, 0.08, 0.80, 0.68))
        for i in range(3):
            comp.layers.append(CompositionLayer(
                id=f"{comp.composition_id}_flow_{i}", type=LayerType.LINE,
                x=0.34 + 0.05 * i, y=0.30 + 0.09 * i, width=0.30,
                height=0.045 + 0.015 * i, z_index=25, role="connector",
                entrance=MotionStyle.ROUTE_DRAW, exit=MotionStyle.DISSOLVE,
                enter_at=0.3 + 0.12 * i, rotation=4.0 * i - 4.0,
                reason="Flow bands thicken as the narrated volume grows"))
        comp.layers.append(self._place_label(
            ctx, comp, 0.38, 0.66, "volume of movement", at=0.7))
        comp.focus_target = f"{comp.composition_id}_flow_1"

    def _v_annotated_map(self, ctx, comp, maps, photos, rng):
        comp.layers.append(self._map_layer(ctx, comp, maps, 0.10, 0.07, 0.64, 0.70))
        for i, (num, ent) in enumerate(zip(("1", "2"), ctx.beat.locations or ["A", "B"])):
            comp.layers.append(CompositionLayer(
                id=f"{comp.composition_id}_callout_{i}", type=LayerType.LABEL,
                x=0.78, y=0.20 + 0.16 * i, width=0.18, height=0.10, z_index=30,
                role="caption", text=f"{num} · {ent}",
                entrance=MotionStyle.SNAP_IN, exit=MotionStyle.SLIDE_OUT,
                enter_at=0.5 + 0.15 * i,
                reason="Numbered callout as narration counts the facts"))
        comp.focus_target = f"{comp.composition_id}_map"

    def _v_map_plus_archival(self, ctx, comp, maps, photos, rng):
        comp.layers.append(self._map_layer(ctx, comp, maps, 0.06, 0.10, 0.52, 0.64))
        if photos:
            comp.layers.append(CompositionLayer(
                id=f"{comp.composition_id}_photo", type=LayerType.IMAGE,
                x=0.60, y=0.18, width=0.34, height=0.48, z_index=15,
                role="support", asset_id=photos[0].asset_id,
                entrance=MotionStyle.PLACE_PHOTO, exit=MotionStyle.SLIDE_OUT,
                enter_at=0.45,
                reason="Archival frame of the place enters as narration zooms into it"))
            comp.relationships.append(Relationship(
                from_layer=f"{comp.composition_id}_map",
                to_layer=f"{comp.composition_id}_photo", kind="annotates",
                label="ground truth"))
            comp.focus_target = f"{comp.composition_id}_photo"
        else:
            comp.focus_target = f"{comp.composition_id}_map"


FAMILY = GeographicMapFamily()
