"""Timeline widget generator for chronological milestones and historical sequences.

Renders horizontal/connected timeline spines, milestone nodes, date pills,
and event summary cards using Vox editorial design tokens.
"""
from __future__ import annotations

import html
from dataclasses import dataclass

from videotool.render.vox_theme import DEFAULT_VOX_THEME, VoxTheme


@dataclass
class TimelineNodeItem:
    """Represents a single milestone event on a timeline."""
    node_id: str
    center_x: float
    center_y: float
    date_text: str = ""
    label_text: str = ""
    is_active: bool = False
    is_milestone: bool = True
    accent_color: str | None = None


class TimelineWidget:
    """Renders Vox-style horizontal chronological timelines."""

    def __init__(self, theme: VoxTheme | None = None):
        self.theme = theme or DEFAULT_VOX_THEME

    def render_fragment(self, nodes: list[TimelineNodeItem], include_text: bool = True) -> list[str]:
        """Generate SVG fragment elements for a list of timeline nodes."""
        if not nodes:
            return []

        elements: list[str] = []
        colors = self.theme.colors
        spacing = self.theme.spacing
        typo = self.theme.typography

        # Sort nodes by X coordinate to establish left-to-right temporal progression
        sorted_nodes = sorted(nodes, key=lambda n: n.center_x)

        # 1. Render Connecting Spine Line
        if len(sorted_nodes) >= 2:
            x_start = sorted_nodes[0].center_x
            x_end = sorted_nodes[-1].center_x
            y_spine = sum(n.center_y for n in sorted_nodes) / len(sorted_nodes)

            # Dark outline for high-contrast visibility against video backgrounds
            elements.append('  <!-- Timeline Spine -->')
            elements.append(
                f'  <line x1="{x_start:.1f}" y1="{y_spine:.1f}" x2="{x_end:.1f}" y2="{y_spine:.1f}" '
                f'stroke="{colors.SHADOW_COLOR}" stroke-opacity="0.7" stroke-width="{spacing.STROKE_OUTLINE:.1f}" '
                f'stroke-linecap="round"/>'
            )
            elements.append(
                f'  <line x1="{x_start:.1f}" y1="{y_spine:.1f}" x2="{x_end:.1f}" y2="{y_spine:.1f}" '
                f'stroke="{colors.ACCENT_YELLOW}" stroke-width="{spacing.STROKE_STANDARD:.1f}" '
                f'stroke-linecap="round"/>'
            )

        # 2. Render Milestone Nodes, Date Badges, and Event Cards
        for node in sorted_nodes:
            nx = node.center_x
            ny = node.center_y
            node_accent = node.accent_color or (colors.ACCENT_YELLOW if node.is_active else colors.ACCENT_BLUE)

            elements.append(f'  <!-- Timeline Node: {html.escape(node.node_id)} -->')

            # Outer Halo
            elements.append(
                f'  <circle cx="{nx:.1f}" cy="{ny:.1f}" r="{spacing.TIMELINE_HALO_RADIUS:.1f}" '
                f'fill="{node_accent}" fill-opacity="0.25" stroke="{node_accent}" stroke-width="1.5"/>'
            )

            # Inner Core Circle
            core_fill = colors.ACCENT_YELLOW if node.is_active else colors.TEXT_PRIMARY_LIGHT
            elements.append(
                f'  <circle cx="{nx:.1f}" cy="{ny:.1f}" r="{spacing.TIMELINE_NODE_RADIUS:.1f}" '
                f'fill="{core_fill}" stroke="{colors.SHADOW_COLOR}" stroke-opacity="0.6" stroke-width="2"/>'
            )

            # Center Dot
            elements.append(
                f'  <circle cx="{nx:.1f}" cy="{ny:.1f}" r="4" fill="{node_accent}"/>'
            )

            # Date Badge (Rendered above node if date_text exists)
            if node.date_text:
                clean_date = html.escape(node.date_text.strip())
                pill_w = max(90.0, len(clean_date) * 11.0 + 24.0)
                pill_h = 30.0
                pill_x = nx - (pill_w / 2.0)
                pill_y = ny - 50.0

                elements.append('  <g filter="url(#card-drop-shadow)">')
                elements.append(
                    f'    <rect x="{pill_x:.1f}" y="{pill_y:.1f}" width="{pill_w:.1f}" height="{pill_h:.1f}" '
                    f'rx="{pill_h/2.0:.1f}" ry="{pill_h/2.0:.1f}" '
                    f'fill="{colors.BG_DARK_CARD}" fill-opacity="0.95" stroke="{node_accent}" stroke-width="1.8"/>'
                )
                if include_text:
                    elements.append(
                        f'    <text x="{nx:.1f}" y="{pill_y + 20.0:.1f}" '
                        f'font-family="{typo.FONT_FAMILY_PRIMARY}" font-size="{typo.SIZE_BADGE}" '
                        f'font-weight="{typo.WEIGHT_BOLD}" fill="{node_accent}" text-anchor="middle">{clean_date}</text>'
                    )
                elements.append('  </g>')

            # Event Label Card (Rendered below node if label_text exists)
            if node.label_text:
                clean_label = html.escape(node.label_text.strip())
                card_w = max(180.0, len(clean_label) * 9.5 + 32.0)
                card_h = 52.0
                card_x = nx - (card_w / 2.0)
                card_y = ny + 24.0

                elements.append('  <g filter="url(#card-drop-shadow)">')
                elements.append(
                    f'    <rect x="{card_x:.1f}" y="{card_y:.1f}" width="{card_w:.1f}" height="{card_h:.1f}" '
                    f'rx="{spacing.RADIUS_MD:.1f}" ry="{spacing.RADIUS_MD:.1f}" '
                    f'fill="{colors.BG_DARK_SLATE}" fill-opacity="0.92" stroke="{colors.BORDER_DARK}" stroke-width="1.5"/>'
                )
                # Left accent indicator
                elements.append(
                    f'    <rect x="{card_x:.1f}" y="{card_y + 4.0:.1f}" width="5" height="{card_h - 8.0:.1f}" '
                    f'rx="2.5" fill="{node_accent}"/>'
                )
                if include_text:
                    elements.append(
                        f'    <text x="{card_x + 16.0:.1f}" y="{card_y + 32.0:.1f}" '
                        f'font-family="{typo.FONT_FAMILY_PRIMARY}" font-size="{typo.SIZE_LABEL_UPPER}" '
                        f'font-weight="{typo.WEIGHT_SEMIBOLD}" fill="{colors.TEXT_PRIMARY_LIGHT}">{clean_label}</text>'
                    )
                elements.append('  </g>')

        return elements
