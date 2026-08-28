"""Fact Card Component (Phase 2).

Renders dark translucent archival milestone card with authentic double-gold
corner brackets, gold date badge, and structured text hierarchy.
"""
from __future__ import annotations


def render_fact_card_svg(
    x: float = 60.0,
    y: float = 780.0,
    width: float = 480.0,
    height: float = 130.0,
    date_text: str = "1961",
    title_text: str = "SỰ KIỆN LỊCH SỬ",
    subtitle_text: str = "MỐC THỜI GIAN QUAN TRỌNG",
    accent_color: str = "#E1B400",
) -> str:
    """Render gold framed fact/milestone box SVG."""
    c_len = 16.0
    # Gold corner brackets path
    # Top-left, top-right, bottom-left, bottom-right corners
    corners_d = (
        f"M {x},{y + c_len} L {x},{y} L {x + c_len},{y} "
        f"M {x + width - c_len},{y} L {x + width},{y} L {x + width},{y + c_len} "
        f"M {x},{y + height - c_len} L {x},{y + height} L {x + c_len},{y + height} "
        f"M {x + width - c_len},{y + height} L {x + width},{y + height} L {x + width},{y + height - c_len}"
    )

    return f"""
    <!-- Gold Milestone Fact Card -->
    <g id="fact_card">
      <rect x="{x}" y="{y}" width="{width}" height="{height}" rx="3"
            fill="#161616" fill-opacity="0.88" />
      <path d="{corners_d}" fill="none" stroke="{accent_color}" stroke-width="2.5" />
      <text x="{x + 20}" y="{y + 36}"
            font-family="'Oswald', 'Montserrat', 'DejaVu Sans', sans-serif"
            font-size="24" font-weight="900" fill="{accent_color}" letter-spacing="1.5">
        {date_text}
      </text>
      <text x="{x + 20}" y="{y + 72}"
            font-family="'Oswald', 'Montserrat', 'DejaVu Sans', sans-serif"
            font-size="22" font-weight="700" fill="#FFFFFF" letter-spacing="0.8">
        {title_text}
      </text>
      <text x="{x + 20}" y="{y + 104}"
            font-family="'Inter', 'Roboto', 'DejaVu Sans', sans-serif"
            font-size="15" font-weight="600" fill="#B3B9C1" letter-spacing="0.5">
        {subtitle_text}
      </text>
    </g>
    """.strip()
