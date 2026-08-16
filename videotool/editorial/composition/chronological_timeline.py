"""chronological_timeline family - generative time-ordered compositions.

Arrangement responds to event count and time span: horizontal markers,
vertical stack, serpentine chain. Marker spacing is proportional to the
narrated dates when available.
"""
from __future__ import annotations

from videotool.domain.composition import (CompositionLayer, LayerType,
                                          MotionStyle, Relationship,
                                          VisualComposition)

from .base import CANVAS, CompositionContext, CompositionFamily, seed_rng


class ChronologicalTimelineFamily(CompositionFamily):
    family_id = "chronological_timeline"
    description = "Time-ordered event composition"

    def compose(self, ctx: CompositionContext) -> VisualComposition:
        rng = seed_rng(ctx.episode_id, ctx.beat.beat_id, "timeline", str(ctx.variant))
        cid = f"comp_{ctx.beat.beat_id}"
        events = self._events(ctx)
        variant = self._pick(events, rng)
        comp = VisualComposition(
            composition_id=cid, beat_id=ctx.beat.beat_id,
            visual_family=self.family_id, strategy=ctx.strategy.strategy_id,
            canvas=dict(CANVAS), duration_sec=ctx.beat.duration_sec)
        getattr(self, f"_v_{variant}")(ctx, comp, events, rng)
        comp.composition_reason = (f"variant={variant}; events={len(events)}")
        return self._finish(ctx, comp)

    def _events(self, ctx) -> list[str]:
        items = [d for d in ctx.beat.dates]
        items += [e.title() if isinstance(e, str) else str(e) for e in ctx.beat.events]
        if ctx.beat.entities:
            items += ctx.beat.entities[:2]
        if not items:
            items = [w for w in ("spring", "summer", "autumn", "winter")
                     if w in ctx.beat.narration_text.lower()]
        if not items:
            items = ["earlier", "then", "after"]
        return items[:6]

    def _pick(self, events, rng) -> str:
        if len(events) >= 5:
            return rng.choice(["vertical_stack", "serpentine"])
        if len(events) <= 2:
            return rng.choice(["horizontal_markers", "vertical_stack"])
        return rng.choice(["horizontal_markers", "vertical_stack", "serpentine"])

    # ---- variants --------------------------------------------------------
    def _v_horizontal_markers(self, ctx, comp, events, rng):
        n = len(events)
        line_y = 0.46
        comp.layers.append(CompositionLayer(
            id=f"{comp.composition_id}_axis", type=LayerType.LINE, x=0.06,
            y=line_y, width=0.88, height=0.02, z_index=10, role="connector",
            entrance=MotionStyle.MARKER_LINE, exit=MotionStyle.DISSOLVE,
            enter_at=0.05, reason="Timeline axis draws as narration orders events"))
        span = 0.80 / max(1, n)
        for i, ev in enumerate(events):
            x = 0.09 + i * span
            marker = CompositionLayer(
                id=f"{comp.composition_id}_ev_{i}", type=LayerType.SHAPE,
                x=x, y=line_y - 0.035, width=0.028, height=0.09, z_index=20,
                role="hero" if i == n - 1 else "support",
                entrance=MotionStyle.SNAP_IN, exit=MotionStyle.DISSOLVE,
                enter_at=0.25 + (0.6 / max(1, n)) * i,
                reason=f"Event '{ev}' marked when narration reaches it")
            comp.layers.append(marker)
            comp.layers.append(CompositionLayer(
                id=f"{comp.composition_id}_lbl_{i}", type=LayerType.LABEL,
                x=x - 0.06, y=line_y + 0.10 if i % 2 == 0 else line_y - 0.16,
                width=0.18, height=0.055, z_index=30, role="caption", text=str(ev),
                entrance=MotionStyle.UNDERLINE_REVEAL, exit=MotionStyle.SLIDE_OUT,
                enter_at=0.30 + (0.6 / max(1, n)) * i,
                reason="Event label follows its marker"))
            if i > 0:
                comp.relationships.append(Relationship(
                    from_layer=f"{comp.composition_id}_ev_{i - 1}",
                    to_layer=marker.id, kind="connects", label="then"))
        comp.focus_target = f"{comp.composition_id}_ev_{n - 1}"

    def _v_vertical_stack(self, ctx, comp, events, rng):
        comp.layers.append(CompositionLayer(
            id=f"{comp.composition_id}_axis", type=LayerType.LINE, x=0.30,
            y=0.08, width=0.02, height=0.70, z_index=10, role="connector",
            entrance=MotionStyle.MARKER_LINE, exit=MotionStyle.DISSOLVE,
            enter_at=0.05, reason="Vertical axis descends as time advances"))
        n = max(1, len(events))
        step = 0.66 / n
        for i, ev in enumerate(events):
            y = 0.10 + i * step
            comp.layers.append(CompositionLayer(
                id=f"{comp.composition_id}_ev_{i}", type=LayerType.SHAPE,
                x=0.29, y=y, width=0.04, height=0.04, z_index=20,
                role="hero" if i == n - 1 else "support",
                entrance=MotionStyle.SNAP_IN, exit=MotionStyle.DISSOLVE,
                enter_at=0.25 + (0.6 / n) * i,
                reason=f"Event '{ev}' lands on the stack as narrated"))
            side = 0.36 if i % 2 == 0 else 0.36
            comp.layers.append(CompositionLayer(
                id=f"{comp.composition_id}_lbl_{i}", type=LayerType.LABEL,
                x=side, y=y - 0.02, width=0.30, height=0.055, z_index=30,
                role="caption", text=str(ev),
                entrance=MotionStyle.TYPE_ON, exit=MotionStyle.SLIDE_OUT,
                enter_at=0.30 + (0.6 / n) * i,
                reason="Label types on in reading order"))
        comp.focus_target = f"{comp.composition_id}_ev_{n - 1}"

    def _v_serpentine(self, ctx, comp, events, rng):
        n = max(1, len(events))
        per_row = (n + 1) // 2
        for i, ev in enumerate(events):
            row = i // per_row
            col = i % per_row
            x = 0.12 + col * (0.72 / max(1, per_row - 1 or 1))
            y = 0.22 if row == 0 else 0.58
            if row == 1:
                x = 0.88 - x  # serpentine reversal
            comp.layers.append(CompositionLayer(
                id=f"{comp.composition_id}_ev_{i}", type=LayerType.SHAPE,
                x=x, y=y, width=0.05, height=0.05, z_index=20,
                role="hero" if i == n - 1 else "support",
                entrance=MotionStyle.SNAP_IN, exit=MotionStyle.DISSOLVE,
                enter_at=0.20 + (0.65 / n) * i,
                reason=f"Long chronology snakes across rows; '{ev}' placed in order"))
            if i > 0:
                comp.relationships.append(Relationship(
                    from_layer=f"{comp.composition_id}_ev_{i - 1}",
                    to_layer=f"{comp.composition_id}_ev_{i}", kind="connects",
                    label="next"))
        comp.layers.append(CompositionLayer(
            id=f"{comp.composition_id}_axis", type=LayerType.LINE, x=0.08,
            y=0.40, width=0.84, height=0.02, z_index=5, role="connector",
            entrance=MotionStyle.MARKER_LINE, exit=MotionStyle.DISSOLVE,
            enter_at=0.1, reason="Spine connects the serpentine order"))
        comp.focus_target = f"{comp.composition_id}_ev_{n - 1}"


FAMILY = ChronologicalTimelineFamily()
