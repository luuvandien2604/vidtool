"""Deterministic SVG vector overlay generator for VisualEdge connectors and entity cards.

Produces 1920x1080 SVG overlays containing directed/undirected relationship
lines, route paths, endpoint markers, location badges, timeline milestones,
and Vox-style editorial cards. Native FFmpeg librsvg decoder parses these
as crisp vector graphics.
"""
from __future__ import annotations

import html
import math
import re
from typing import TYPE_CHECKING

from videotool.render.vox_theme import DEFAULT_VOX_THEME, VoxTheme
from videotool.render.widgets.stat_badge import StatBadgeItem, StatBadgeWidget
from videotool.render.widgets.timeline import TimelineNodeItem, TimelineWidget

if TYPE_CHECKING:
    from videotool.render.frame_plan import (ConnectorRenderElement,
                                            TextRenderElement)


def _extract_date_and_label(text: str) -> tuple[str, str]:
    """Split timeline text into date milestone and descriptive label if possible."""
    m = re.match(r"^((?:19\d\d|20\d\d|[A-Z][a-z]+ \d{4}|\d{1,2}/\d{1,2}/\d{2,4}))(?:\s*[:\-–—]\s*|\s+)(.*)$", text)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    if re.match(r"^(19\d\d|20\d\d|[A-Z][a-z]+ \d{4})$", text.strip()):
        return text.strip(), ""
    return "", text.strip()


def generate_svg_overlay(connectors: list[ConnectorRenderElement] | None = None,
                         text_elements: list[TextRenderElement] | None = None,
                         canvas_w: int = 1920,
                         canvas_h: int = 1080,
                         accent_color: str = "#FFD100",
                         visual_family: str | None = None,
                         theme: VoxTheme | None = None,
                         include_text: bool = False) -> str | None:
    """Generate an SVG vector overlay for a beat's connectors, timeline, and node cards.

    Strict Architectural Rule:
    Vox infographic elements (card borders, timeline spines, date pills, metric icons)
    exclusively use Vox design tokens (ACCENT_YELLOW for cards/milestones, ACCENT_BLUE
    for location badges) and are immune to per-episode art_direction overrides.
    """
    conns = connectors or []
    texts = text_elements or []

    if not conns and not texts:
        return None

    active_theme = theme or DEFAULT_VOX_THEME
    colors = active_theme.colors
    spacing = active_theme.spacing
    typo = active_theme.typography

    elements: list[str] = []

    # SVG Header with shadow filter and gradients
    svg_header = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{canvas_w}" height="{canvas_h}" viewBox="0 0 {canvas_w} {canvas_h}">',
        '  <defs>',
        '    <filter id="card-drop-shadow" x="-15%" y="-15%" width="135%" height="140%">',
        '      <feDropShadow dx="0" dy="4" stdDeviation="6" flood-color="#000000" flood-opacity="0.65"/>',
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
        # Connectors default to signature Vox Yellow
        stroke_color = colors.ACCENT_YELLOW
        stroke_width = max(spacing.STROKE_STANDARD, conn.stroke_width)

        # Dash styling for routes vs solid causal/temporal links
        dash_attr = ' stroke-dasharray="12,8"' if conn.is_dashed else ""

        # Draw dark outline for high contrast against any background
        elements.append(
            f'  <line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
            f'stroke="{colors.SHADOW_COLOR}" stroke-opacity="0.7" stroke-width="{stroke_width + 4.0}" stroke-linecap="round"{dash_attr}/>'
        )

        # Start endpoint anchor ring
        elements.append(
            f'  <circle cx="{x1:.1f}" cy="{y1:.1f}" r="8" fill="{stroke_color}" stroke="{colors.TEXT_PRIMARY_LIGHT}" stroke-width="2"/>'
        )

        if conn.directed:
            arrow_len = 20.0
            arrow_half_w = 9.0
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
                f'fill="{stroke_color}" stroke="{colors.SHADOW_COLOR}" stroke-opacity="0.5" stroke-width="1.5"/>'
            )
        else:
            elements.append(
                f'  <line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
                f'stroke="{stroke_color}" stroke-width="{stroke_width}" stroke-linecap="round"{dash_attr}/>'
            )
            # End dot for undirected connection
            elements.append(
                f'  <circle cx="{x2:.1f}" cy="{y2:.1f}" r="8" fill="{stroke_color}" stroke="{colors.TEXT_PRIMARY_LIGHT}" stroke-width="2"/>'
            )

    # 2. Categorize Text Elements for Specialized Widgets vs Standard Cards
    is_timeline_beat = (
        visual_family == "chronological_timeline"
        or any(t.style_name == "NodeTimeline" for t in texts)
        or (len(texts) >= 2 and any(t.text_role in ("TIMELINE_NODE", "DATE") for t in texts))
    )

    timeline_items: list[TimelineNodeItem] = []
    stat_items: list[StatBadgeItem] = []
    standard_cards: list[TextRenderElement] = []

    for elem in texts:
        # Rule: DATE in timeline context -> TimelineWidget; Standalone DATE -> StatBadgeWidget
        if is_timeline_beat and (elem.style_name == "NodeTimeline" or elem.text_role in ("TIMELINE_NODE", "DATE") or elem.role == "TIMELINE_NODE"):
            d_text, l_text = _extract_date_and_label(elem.text)
            timeline_items.append(TimelineNodeItem(
                node_id=elem.element_id,
                center_x=float(elem.bounds_px.center_x),
                center_y=float(elem.bounds_px.center_y),
                date_text=d_text or (elem.text if elem.text_role == "DATE" else ""),
                label_text=l_text or (elem.text if elem.text_role != "DATE" else ""),
                accent_color=colors.ACCENT_YELLOW,
            ))
        elif elem.text_role == "DATE" or (elem.role == "DATE" and not is_timeline_beat):
            # Standalone date fact -> StatBadgeWidget with ACCENT_YELLOW
            stat_items.append(StatBadgeItem(
                label="DATE",
                value=elem.text,
                kind="date",
                center_x=float(elem.bounds_px.center_x),
                center_y=float(elem.bounds_px.center_y),
                accent_color=colors.ACCENT_YELLOW,
            ))
        elif elem.text_role in ("LOCATION", "PLACE") or elem.role == "LOCATION":
            # Location badge -> StatBadgeWidget with ACCENT_BLUE
            stat_items.append(StatBadgeItem(
                label="LOCATION",
                value=elem.text,
                kind="location",
                center_x=float(elem.bounds_px.center_x),
                center_y=float(elem.bounds_px.center_y),
                accent_color=colors.ACCENT_BLUE,
            ))
        elif elem.bounds_px.width < 220 and len(elem.text) <= 15 and elem.style_name != "NodeQuote":
            # Short entity / metric fact
            stat_items.append(StatBadgeItem(
                label="ENTITY",
                value=elem.text,
                kind="entity",
                center_x=float(elem.bounds_px.center_x),
                center_y=float(elem.bounds_px.center_y),
                accent_color=colors.ACCENT_YELLOW,
            ))
        else:
            standard_cards.append(elem)

    # 3. Render Widgets
    if timeline_items:
        t_widget = TimelineWidget(active_theme)
        elements.extend(t_widget.render_fragment(timeline_items, include_text=include_text))

    if stat_items:
        s_widget = StatBadgeWidget(active_theme)
        elements.extend(s_widget.render_fragment(stat_items, include_text=include_text))

    # 4. Render Standard Cards (Quotes, Entity Cards, Diagram Nodes) with Vox styling
    for elem in standard_cards:
        cx = elem.bounds_px.center_x
        cy = elem.bounds_px.center_y
        w = elem.bounds_px.width
        h = elem.bounds_px.height

        if elem.style_name == "NodeQuote":
            # Elegant Vox quote card with signature yellow border and left bar
            bw = max(340.0, float(w) + 48.0)
            bh = max(84.0, float(h) + 28.0)
            bx = cx - bw / 2.0
            by = cy - bh / 2.0

            elements.append('  <g filter="url(#card-drop-shadow)">')
            elements.append(
                f'    <rect x="{bx:.1f}" y="{by:.1f}" width="{bw:.1f}" height="{bh:.1f}" '
                f'rx="{spacing.RADIUS_MD:.1f}" ry="{spacing.RADIUS_MD:.1f}" '
                f'fill="{colors.BG_DARK_CARD}" fill-opacity="0.94" stroke="{colors.ACCENT_YELLOW}" stroke-width="1.8"/>'
            )
            elements.append(
                f'    <rect x="{bx:.1f}" y="{by:.1f}" width="{spacing.ACCENT_BAR_WIDTH:.1f}" height="{bh:.1f}" '
                f'rx="3" fill="{colors.ACCENT_YELLOW}"/>'
            )
            elements.append('  </g>')

        else:
            # Diagram / Concept / Entity Card with signature Vox Yellow left bar
            bw = max(260.0, float(w) + 36.0)
            bh = max(68.0, float(h) + 16.0)
            bx = cx - bw / 2.0
            by = cy - bh / 2.0

            elements.append('  <g filter="url(#card-drop-shadow)">')
            elements.append(
                f'    <rect x="{bx:.1f}" y="{by:.1f}" width="{bw:.1f}" height="{bh:.1f}" '
                f'rx="{spacing.RADIUS_MD:.1f}" ry="{spacing.RADIUS_MD:.1f}" '
                f'fill="{colors.BG_DARK_CARD}" fill-opacity="0.92" stroke="{colors.BORDER_DARK}" stroke-width="1.5"/>'
            )
            # Left accent highlight bar strictly in signature Vox Yellow
            elements.append(
                f'    <rect x="{bx:.1f}" y="{by + 6.0:.1f}" width="{spacing.ACCENT_BAR_WIDTH:.1f}" '
                f'height="{bh - 12.0:.1f}" rx="3" fill="{colors.ACCENT_YELLOW}"/>'
            )
            elements.append('  </g>')

    svg_footer = ['</svg>']
    return "\n".join(svg_header + elements + svg_footer) + "\n"
