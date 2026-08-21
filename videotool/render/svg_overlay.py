"""Deterministic SVG vector overlay generator for VisualEdge connectors.

Produces 1920x1080 SVG overlays containing directed/undirected relationship
lines, route paths, and endpoint markers. Native FFmpeg librsvg decoder parses
these as crisp vector graphics.
"""
from __future__ import annotations

import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from videotool.render.frame_plan import ConnectorRenderElement


def generate_svg_overlay(connectors: list[ConnectorRenderElement],
                         canvas_w: int = 1920,
                         canvas_h: int = 1080,
                         accent_color: str = "#E6C280") -> str | None:
    """Generate an SVG vector overlay for a beat's connectors."""
    if not connectors:
        return None

    elements = []
    # Header
    svg_header = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{canvas_w}" height="{canvas_h}" viewBox="0 0 {canvas_w} {canvas_h}">'
    ]

    for i, conn in enumerate(connectors):
        x1, y1 = conn.start_px
        x2, y2 = conn.end_px

        dx = x2 - x1
        dy = y2 - y1
        dist = math.hypot(dx, dy)
        if dist < 1e-4:
            continue

        angle = math.atan2(dy, dx)
        stroke_color = conn.color or accent_color
        stroke_width = max(4.0, conn.stroke_width)

        # Dash styling for routes vs solid causal/temporal links
        dash_attr = ' stroke-dasharray="12,8"' if conn.is_dashed else ""

        # Draw start endpoint circle
        elements.append(
            f'  <circle cx="{x1:.1f}" cy="{y1:.1f}" r="7" fill="{stroke_color}"/>'
        )

        if conn.directed:
            arrow_len = 18.0
            arrow_half_w = 8.0
            # Pull line back slightly so arrowhead sits cleanly
            line_end_x = x2 - (arrow_len * 0.7) * math.cos(angle)
            line_end_y = y2 - (arrow_len * 0.7) * math.sin(angle)

            elements.append(
                f'  <line x1="{x1:.1f}" y1="{y1:.1f}" x2="{line_end_x:.1f}" y2="{line_end_y:.1f}" '
                f'stroke="{stroke_color}" stroke-width="{stroke_width}" stroke-linecap="round"{dash_attr}/>'
            )

            # Arrowhead polygon
            tip_x, tip_y = x2, y2
            p1_x = x2 - arrow_len * math.cos(angle) + arrow_half_w * math.sin(angle)
            p1_y = y2 - arrow_len * math.sin(angle) - arrow_half_w * math.cos(angle)
            p2_x = x2 - arrow_len * math.cos(angle) - arrow_half_w * math.sin(angle)
            p2_y = y2 - arrow_len * math.sin(angle) + arrow_half_w * math.cos(angle)

            elements.append(
                f'  <polygon points="{tip_x:.1f},{tip_y:.1f} {p1_x:.1f},{p1_y:.1f} {p2_x:.1f},{p2_y:.1f}" '
                f'fill="{stroke_color}"/>'
            )
        else:
            elements.append(
                f'  <line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
                f'stroke="{stroke_color}" stroke-width="{stroke_width}" stroke-linecap="round"{dash_attr}/>'
            )
            # End dot for undirected connection
            elements.append(
                f'  <circle cx="{x2:.1f}" cy="{y2:.1f}" r="7" fill="{stroke_color}"/>'
            )

    svg_footer = ['</svg>']
    return "\n".join(svg_header + elements + svg_footer) + "\n"
