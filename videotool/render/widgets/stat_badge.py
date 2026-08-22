"""Stat badge and milestone fact widget generator for documentary motion graphics.

Renders high-contrast fact badges, location markers, date callouts, and metric cards
with geometric SVG vector icons and Vox editorial styling.
"""
from __future__ import annotations

import html
from dataclasses import dataclass

from videotool.render.vox_theme import DEFAULT_VOX_THEME, VoxTheme


@dataclass
class StatBadgeItem:
    """Represents a standalone key fact, location badge, date callout, or metric."""
    label: str
    value: str
    kind: str = "metric"  # "date", "location", "person", "metric"
    center_x: float = 960.0
    center_y: float = 540.0
    width: float = 240.0
    height: float = 64.0
    accent_color: str | None = None


class StatBadgeWidget:
    """Renders Vox-style geometric stat badges and key fact cards."""

    def __init__(self, theme: VoxTheme | None = None):
        self.theme = theme or DEFAULT_VOX_THEME

    def _render_icon_svg(self, kind: str, cx: float, cy: float, color: str) -> list[str]:
        """Render pure SVG geometric vector icon centered at (cx, cy)."""
        icons: list[str] = []
        k = kind.lower().strip()

        if k in ("date", "calendar", "time", "year"):
            # Calendar vector icon
            rx, ry = cx - 10.0, cy - 9.0
            icons.append(
                f'<rect x="{rx:.1f}" y="{ry:.1f}" width="20" height="18" rx="3" '
                f'fill="none" stroke="{color}" stroke-width="2"/>'
            )
            # Top header bar & rings
            icons.append(
                f'<line x1="{rx:.1f}" y1="{ry + 5.0:.1f}" x2="{rx + 20.0:.1f}" y2="{ry + 5.0:.1f}" '
                f'stroke="{color}" stroke-width="1.8"/>'
            )
            icons.append(f'<line x1="{cx - 5.0:.1f}" y1="{ry - 3.0:.1f}" x2="{cx - 5.0:.1f}" y2="{ry + 1.0:.1f}" stroke="{color}" stroke-width="2" stroke-linecap="round"/>')
            icons.append(f'<line x1="{cx + 5.0:.1f}" y1="{ry - 3.0:.1f}" x2="{cx + 5.0:.1f}" y2="{ry + 1.0:.1f}" stroke="{color}" stroke-width="2" stroke-linecap="round"/>')
            # Calendar day dot
            icons.append(f'<circle cx="{cx:.1f}" cy="{cy + 3.0:.1f}" r="2" fill="{color}"/>')

        elif k in ("location", "place", "city", "country"):
            # Location map pin icon
            pin_y = cy - 3.0
            icons.append(
                f'<path d="M {cx:.1f} {pin_y + 11.0:.1f} '
                f'C {cx - 8.0:.1f} {pin_y + 3.0:.1f} {cx - 8.0:.1f} {pin_y - 7.0:.1f} {cx:.1f} {pin_y - 7.0:.1f} '
                f'C {cx + 8.0:.1f} {pin_y - 7.0:.1f} {cx + 8.0:.1f} {pin_y + 3.0:.1f} {cx:.1f} {pin_y + 11.0:.1f} Z" '
                f'fill="{color}" fill-opacity="0.25" stroke="{color}" stroke-width="2"/>'
            )
            icons.append(f'<circle cx="{cx:.1f}" cy="{pin_y - 1.0:.1f}" r="3" fill="{color}"/>')

        elif k in ("person", "entity", "who", "figure"):
            # User / Person avatar icon
            head_y = cy - 4.0
            icons.append(f'<circle cx="{cx:.1f}" cy="{head_y:.1f}" r="5" fill="none" stroke="{color}" stroke-width="2"/>')
            icons.append(
                f'<path d="M {cx - 9.0:.1f} {cy + 9.0:.1f} '
                f'C {cx - 9.0:.1f} {cy + 3.0:.1f} {cx + 9.0:.1f} {cy + 3.0:.1f} {cx + 9.0:.1f} {cy + 9.0:.1f}" '
                f'fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round"/>'
            )

        else:
            # Metric / Bar chart trend icon
            icons.append(f'<line x1="{cx - 7.0:.1f}" y1="{cy + 7.0:.1f}" x2="{cx - 7.0:.1f}" y2="{cy - 1.0:.1f}" stroke="{color}" stroke-width="2.5" stroke-linecap="round"/>')
            icons.append(f'<line x1="{cx:.1f}" y1="{cy + 7.0:.1f}" x2="{cx:.1f}" y2="{cy - 6.0:.1f}" stroke="{color}" stroke-width="2.5" stroke-linecap="round"/>')
            icons.append(f'<line x1="{cx + 7.0:.1f}" y1="{cy + 7.0:.1f}" x2="{cx + 7.0:.1f}" y2="{cy + 2.0:.1f}" stroke="{color}" stroke-width="2.5" stroke-linecap="round"/>')

        return icons

    def render_fragment(self, items: list[StatBadgeItem], include_text: bool = True) -> list[str]:
        """Generate SVG fragment elements for a list of stat badge items."""
        if not items:
            return []

        elements: list[str] = []
        colors = self.theme.colors
        spacing = self.theme.spacing
        typo = self.theme.typography

        for item in items:
            cx = item.center_x
            cy = item.center_y
            accent = item.accent_color or (
                colors.ACCENT_YELLOW if item.kind.lower() in ("date", "year") else
                colors.ACCENT_BLUE if item.kind.lower() in ("location", "place") else
                colors.ACCENT_CORAL if item.kind.lower() in ("person", "entity") else
                colors.ACCENT_MUSTARD
            )

            # Measure card width based on text lengths
            val_len = len(item.value)
            lbl_len = len(item.label)
            calc_w = max(item.width, max(val_len * 14.0, lbl_len * 9.0) + 70.0)
            calc_h = max(item.height, 68.0)
            card_x = cx - (calc_w / 2.0)
            card_y = cy - (calc_h / 2.0)

            elements.append(f'  <!-- Stat Badge: {html.escape(item.label or item.value)} -->')
            elements.append('  <g filter="url(#card-drop-shadow)">')

            # 1. Main Background Card
            elements.append(
                f'    <rect x="{card_x:.1f}" y="{card_y:.1f}" width="{calc_w:.1f}" height="{calc_h:.1f}" '
                f'rx="{spacing.RADIUS_MD:.1f}" ry="{spacing.RADIUS_MD:.1f}" '
                f'fill="{colors.BG_DARK_CARD}" fill-opacity="0.95" stroke="{colors.BORDER_DARK}" stroke-width="1.5"/>'
            )

            # 2. Left Accent Bar
            elements.append(
                f'    <rect x="{card_x:.1f}" y="{card_y + 4.0:.1f}" width="{spacing.ACCENT_BAR_WIDTH:.1f}" '
                f'height="{calc_h - 8.0:.1f}" rx="3" fill="{accent}"/>'
            )

            # 3. Icon Circle Container
            icon_cx = card_x + 28.0
            icon_cy = cy
            elements.append(
                f'    <circle cx="{icon_cx:.1f}" cy="{icon_cy:.1f}" r="16" '
                f'fill="{colors.BG_DARK_SLATE}" stroke="{accent}" stroke-width="1.5"/>'
            )

            # 4. Pure Vector Geometric Icon
            for icon_el in self._render_icon_svg(item.kind, icon_cx, icon_cy, accent):
                elements.append(f'    {icon_el}')

            # 5. Text Hierarchy (Included when include_text is True)
            if include_text:
                text_x = card_x + 56.0
                clean_label = html.escape(item.label.upper().strip()) if item.label else ""
                clean_val = html.escape(item.value.strip())

                if clean_label and clean_val != clean_label:
                    elements.append(
                        f'    <text x="{text_x:.1f}" y="{cy - 4.0:.1f}" '
                        f'font-family="{typo.FONT_FAMILY_PRIMARY}" font-size="{typo.SIZE_CAPTION}" '
                        f'font-weight="{typo.WEIGHT_SEMIBOLD}" fill="{colors.TEXT_MUTED_LIGHT}" '
                        f'letter-spacing="1.2">{clean_label}</text>'
                    )
                    elements.append(
                        f'    <text x="{text_x:.1f}" y="{cy + 18.0:.1f}" '
                        f'font-family="{typo.FONT_FAMILY_PRIMARY}" font-size="{typo.SIZE_VALUE_MD}" '
                        f'font-weight="{typo.WEIGHT_BOLD}" fill="{colors.TEXT_PRIMARY_LIGHT}">{clean_val}</text>'
                    )
                else:
                    elements.append(
                        f'    <text x="{text_x:.1f}" y="{cy + 8.0:.1f}" '
                        f'font-family="{typo.FONT_FAMILY_PRIMARY}" font-size="{typo.SIZE_VALUE_MD}" '
                        f'font-weight="{typo.WEIGHT_BOLD}" fill="{colors.TEXT_PRIMARY_LIGHT}">{clean_val}</text>'
                    )

            elements.append('  </g>')

        return elements
