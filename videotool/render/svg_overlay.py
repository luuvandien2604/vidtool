"""Deterministic SVG vector overlay generator for VisualEdge connectors and entity cards.

Produces 1920x1080 SVG overlays containing directed/undirected relationship
lines, route paths, endpoint markers, location badges, and frosted glass node cards.
Native FFmpeg librsvg decoder parses these as crisp vector graphics.
"""
from __future__ import annotations

import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from videotool.render.frame_plan import (ConnectorRenderElement,
                                            TextRenderElement)


def generate_svg_overlay(connectors: list[ConnectorRenderElement] | None = None,
                         text_elements: list[TextRenderElement] | None = None,
                         canvas_w: int = 1920,
                         canvas_h: int = 1080,
                         accent_color: str = "#E6C280") -> str | None:
    """Generate an SVG vector overlay for a beat's connectors and node card containers."""
    conns = connectors or []
    texts = text_elements or []

    if not conns and not texts:
        return None

    elements: list[str] = []

    # SVG Header with shadow filter and gradients
    svg_header = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{canvas_w}" height="{canvas_h}" viewBox="0 0 {canvas_w} {canvas_h}">',
        '  <defs>',
        '    <filter id="card-drop-shadow" x="-10%" y="-10%" width="125%" height="130%">',
        '      <feDropShadow dx="0" dy="4" stdDeviation="6" flood-color="#000000" flood-opacity="0.6"/>',
        '    </filter>',
        '  </defs>',
    ]

    # 1. Render Connectors (underneath text cards)
    for conn in conns:
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

        # Draw dark outline for high contrast against any background
        elements.append(
            f'  <line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
            f'stroke="#000000" stroke-opacity="0.6" stroke-width="{stroke_width + 4.0}" stroke-linecap="round"{dash_attr}/>'
        )

        # Start endpoint anchor ring
        elements.append(
            f'  <circle cx="{x1:.1f}" cy="{y1:.1f}" r="8" fill="{stroke_color}" stroke="#ffffff" stroke-width="2"/>'
        )

        if conn.directed:
            arrow_len = 20.0
            arrow_half_w = 9.0
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
                f'fill="{stroke_color}" stroke="#000000" stroke-opacity="0.5" stroke-width="1.5"/>'
            )
        else:
            elements.append(
                f'  <line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
                f'stroke="{stroke_color}" stroke-width="{stroke_width}" stroke-linecap="round"{dash_attr}/>'
            )
            # End dot for undirected connection
            elements.append(
                f'  <circle cx="{x2:.1f}" cy="{y2:.1f}" r="8" fill="{stroke_color}" stroke="#ffffff" stroke-width="2"/>'
            )

    # 2. Render Node Cards & Location Badges for text elements
    for elem in texts:
        cx = elem.bounds_px.center_x
        cy = elem.bounds_px.center_y
        w = elem.bounds_px.width
        h = elem.bounds_px.height

        if elem.style_name == "NodeQuote":
            # Elegant quote card with left gold border
            bw = max(320.0, float(w) + 48.0)
            bh = max(80.0, float(h) + 24.0)
            bx = cx - bw / 2.0
            by = cy - bh / 2.0

            elements.append(
                f'  <rect x="{bx:.1f}" y="{by:.1f}" width="{bw:.1f}" height="{bh:.1f}" rx="8" ry="8" '
                f'fill="#18181b" fill-opacity="0.90" stroke="#eab308" stroke-width="2" filter="url(#card-drop-shadow)"/>'
            )
            elements.append(
                f'  <rect x="{bx:.1f}" y="{by:.1f}" width="8" height="{bh:.1f}" rx="4" fill="#eab308"/>'
            )

        elif elem.style_name == "NodeTimeline":
            # Indigo timeline step card
            bw = max(240.0, float(w) + 36.0)
            bh = max(68.0, float(h) + 16.0)
            bx = cx - bw / 2.0
            by = cy - bh / 2.0

            elements.append(
                f'  <rect x="{bx:.1f}" y="{by:.1f}" width="{bw:.1f}" height="{bh:.1f}" rx="10" ry="10" '
                f'fill="#1e1b4b" fill-opacity="0.88" stroke="#818cf8" stroke-width="2" filter="url(#card-drop-shadow)"/>'
            )
            elements.append(
                f'  <circle cx="{bx + 20.0:.1f}" cy="{cy:.1f}" r="6" fill="#818cf8" stroke="#ffffff" stroke-width="1.5"/>'
            )

        elif w < 220 and len(elem.text) <= 15:
            # Compact location / entity badge for short labels
            bw = max(160.0, float(w) + 50.0)
            bh = max(52.0, float(h) + 14.0)
            bx = cx - bw / 2.0
            by = cy - bh / 2.0

            elements.append(
                f'  <rect x="{bx:.1f}" y="{by:.1f}" width="{bw:.1f}" height="{bh:.1f}" rx="{bh/2.0:.1f}" ry="{bh/2.0:.1f}" '
                f'fill="#0f172a" fill-opacity="0.88" stroke="#38bdf8" stroke-width="2" filter="url(#card-drop-shadow)"/>'
            )
            # Location pin icon dot on left
            elements.append(
                f'  <circle cx="{bx + 18.0:.1f}" cy="{cy:.1f}" r="5" fill="#38bdf8"/>'
            )

        else:
            # Diagram / Concept / Entity Card for larger labels
            bw = max(260.0, float(w) + 36.0)
            bh = max(68.0, float(h) + 16.0)
            bx = cx - bw / 2.0
            by = cy - bh / 2.0

            elements.append(
                f'  <rect x="{bx:.1f}" y="{by:.1f}" width="{bw:.1f}" height="{bh:.1f}" rx="10" ry="10" '
                f'fill="#0f172a" fill-opacity="0.88" stroke="#475569" stroke-width="2" filter="url(#card-drop-shadow)"/>'
            )
            # Accent highlight bar on left
            elements.append(
                f'  <rect x="{bx:.1f}" y="{by + 6.0:.1f}" width="6" height="{bh - 12.0:.1f}" rx="3" fill="{accent_color}"/>'
            )

    svg_footer = ['</svg>']
    return "\n".join(svg_header + elements + svg_footer) + "\n"
