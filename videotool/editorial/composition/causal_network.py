"""causal_network family - generative relationship-graph compositions.

The arrangement IS the graph (spec section 7): 3 equal entities -> triangle;
1 center + k events -> radial/asymmetric; 2 opposing actors -> split; a
chain of dated events -> directional causal chain.
"""
from __future__ import annotations

from videotool.domain.composition import (CompositionLayer, LayerType,
                                          MotionStyle, Relationship,
                                          VisualComposition)

from .base import CANVAS, CompositionContext, CompositionFamily, seed_rng

_NODE_W, _NODE_H = 0.20, 0.16


class CausalNetworkFamily(CompositionFamily):
    family_id = "causal_network"
    description = "Relationship-graph composition"

    def compose(self, ctx: CompositionContext) -> VisualComposition:
        rng = seed_rng(ctx.episode_id, ctx.beat.beat_id, "causal", str(ctx.variant))
        cid = f"comp_{ctx.beat.beat_id}"
        nodes = self._nodes(ctx)
        shape = self._graph_shape(nodes, ctx)
        comp = VisualComposition(
            composition_id=cid, beat_id=ctx.beat.beat_id,
            visual_family=self.family_id, strategy=ctx.strategy.strategy_id,
            canvas=dict(CANVAS), duration_sec=ctx.beat.duration_sec)
        getattr(self, f"_v_{shape}")(ctx, comp, nodes, rng)
        comp.composition_reason = f"graph_shape={shape}; nodes={len(nodes)}"
        return self._finish(ctx, comp)

    def _nodes(self, ctx) -> list[str]:
        nodes: list[str] = []
        for src in (ctx.beat.entities, ctx.beat.locations, ctx.beat.objects):
            for item in src:
                if item not in nodes:
                    nodes.append(str(item))
        if len(nodes) < 2:
            words = ctx.beat.narration_text.split()
            nodes += [w.strip(".,;:!?") for w in words if w[0].isupper()][:3 - len(nodes)]
        while len(nodes) < 2:
            nodes.append("factor" if len(nodes) == 0 else "outcome")
        return nodes[:5]

    def _graph_shape(self, nodes, ctx) -> str:
        n = len(nodes)
        has_center = bool(ctx.beat.entities and
                          (ctx.beat.relationships or ctx.beat.events))
        if n == 2:
            return "split_opposing"
        if n == 3:
            return "triangle"
        if has_center:
            return "radial"
        return "chain"

    # ---- shapes --------------------------------------------------------
    def _node(self, ctx, comp, idx, text, x, y, role="support", at=0.3):
        return CompositionLayer(
            id=f"{comp.composition_id}_n{idx}", type=LayerType.LABEL,
            x=x, y=y, width=_NODE_W, height=_NODE_H, z_index=20, role=role,
            text=str(text), entrance=MotionStyle.SNAP_IN,
            exit=MotionStyle.COLLAPSE, enter_at=at,
            reason=f"'{text}' enters as narration names it")

    def _edge(self, comp, idx, x1, y1, x2, y2, at=0.5, label="leads to"):
        import math
        cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
        length = math.hypot(x2 - x1, y2 - y1)
        angle = math.degrees(math.atan2(y2 - y1, x2 - x1))
        return CompositionLayer(
            id=f"{comp.composition_id}_e{idx}", type=LayerType.ARROW,
            x=cx - length / 2, y=cy - 0.015, width=length, height=0.03,
            z_index=15, role="connector", rotation=angle,
            entrance=MotionStyle.MARKER_LINE, exit=MotionStyle.DISSOLVE,
            enter_at=at,
            reason=f"Causal connector draws: {label}")

    def _v_chain(self, ctx, comp, nodes, rng):
        n = len(nodes)
        stagger = rng.choice([(0.30, 0.48), (0.48, 0.30), (0.38, 0.52)])
        for i, node in enumerate(nodes):
            x = 0.07 + i * ((0.86 - _NODE_W) / max(1, n - 1)) if n > 1 else 0.40
            y = stagger[0] if i % 2 == 0 else stagger[1]
            comp.layers.append(self._node(ctx, comp, i, node, round(x, 3), y,
                                          role="hero" if i == n - 1 else "support",
                                          at=0.25 + 0.15 * i))
            if i > 0:
                prev_x = 0.07 + (i - 1) * ((0.86 - _NODE_W) / max(1, n - 1))
                prev_y = stagger[0] if (i - 1) % 2 == 0 else stagger[1]
                comp.layers.append(self._edge(
                    comp, i, prev_x + _NODE_W, prev_y + _NODE_H / 2,
                    x, y + _NODE_H / 2, at=0.35 + 0.15 * i))
                comp.relationships.append(Relationship(
                    from_layer=f"{comp.composition_id}_n{i - 1}",
                    to_layer=f"{comp.composition_id}_n{i}", kind="points_to"))
        comp.focus_target = f"{comp.composition_id}_n{n - 1}"

    def _v_triangle(self, ctx, comp, nodes, rng):
        base = [(0.40, 0.10), (0.12, 0.56), (0.68, 0.56)]
        rot = ctx.variant % 3
        spots = base[rot:] + base[:rot]
        for i, node in enumerate(nodes[:3]):
            x, y = spots[i]
            comp.layers.append(self._node(ctx, comp, i, node, x, y,
                                          at=0.25 + 0.15 * i))
        edges = ((0, 1), (1, 2), (2, 0))
        for j, (a, b) in enumerate(edges):
            ax, ay = spots[a]; bx, by = spots[b]
            comp.layers.append(self._edge(
                comp, 100 + j, ax + _NODE_W / 2, ay + _NODE_H,
                bx + _NODE_W / 2, by, at=0.5 + 0.1 * j))
            comp.relationships.append(Relationship(
                from_layer=f"{comp.composition_id}_n{a}",
                to_layer=f"{comp.composition_id}_n{b}", kind="connects"))
        comp.focus_target = f"{comp.composition_id}_n0"

    def _v_radial(self, ctx, comp, nodes, rng):
        import math
        center = nodes[0]
        spokes = nodes[1:] or ["event"]
        cx, cy = 0.40, 0.34
        theta0 = (ctx.variant % 4) * (math.pi / 6) - math.pi / 6
        comp.layers.append(self._node(ctx, comp, 0, center, cx, cy, role="hero",
                                      at=0.2))
        n = len(spokes)
        for i, node in enumerate(spokes):
            theta = theta0 - math.pi / 2 + (2 * math.pi * i) / max(1, n)
            sx = cx + 0.32 * math.cos(theta)
            sy = cy + 0.26 * math.sin(theta)
            comp.layers.append(self._node(
                ctx, comp, i + 1, node,
                round(min(max(sx, 0.05), 0.95 - _NODE_W), 3),
                round(min(max(sy, 0.08), 0.72 - _NODE_H), 3),
                at=0.4 + 0.12 * i))
            comp.layers.append(self._edge(
                comp, 200 + i, cx + _NODE_W / 2, cy + _NODE_H / 2,
                sx + _NODE_W / 2, sy + _NODE_H / 2, at=0.45 + 0.12 * i,
                label="influences"))
            comp.relationships.append(Relationship(
                from_layer=f"{comp.composition_id}_n0",
                to_layer=f"{comp.composition_id}_n{i + 1}", kind="points_to"))
        comp.focus_target = f"{comp.composition_id}_n0"

    def _v_split_opposing(self, ctx, comp, nodes, rng):
        left, right = nodes[0], nodes[1] if len(nodes) > 1 else "outcome"
        comp.layers.append(self._node(ctx, comp, 0, left, 0.08, 0.30,
                                      role="hero", at=0.25))
        comp.layers.append(self._node(ctx, comp, 1, right, 0.72, 0.30,
                                      role="hero", at=0.5))
        comp.layers.append(CompositionLayer(
            id=f"{comp.composition_id}_divide", type=LayerType.LINE, x=0.49,
            y=0.12, width=0.02, height=0.62, z_index=12, role="connector",
            entrance=MotionStyle.MARKER_LINE, exit=MotionStyle.DISSOLVE,
            enter_at=0.35,
            reason=f"Division line echoes episode geometry: {ctx.art_direction.geometry[0] if ctx.art_direction.geometry else 'split'}"))
        comp.layers.append(self._edge(comp, 0, 0.30, 0.38, 0.70, 0.38,
                                      at=0.7, label="opposes"))
        comp.relationships.append(Relationship(
            from_layer=f"{comp.composition_id}_n0",
            to_layer=f"{comp.composition_id}_n1", kind="contrasts"))
        comp.focus_target = f"{comp.composition_id}_divide"


FAMILY = CausalNetworkFamily()
