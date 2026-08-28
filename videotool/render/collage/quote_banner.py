"""Quote Banner Component (Phase 2).

Renders dark charcoal brush stroke banner with XML-safe gold keyword highlighting.
"""
from __future__ import annotations

import re


def highlight_keywords_in_quote(
    quote_text: str,
    emphasis_keywords: list[str],
    accent_color: str = "#E1B400",
) -> str:
    """Safely highlight emphasis keywords in SVG quote text using `<tspan>`."""
    if not emphasis_keywords:
        return quote_text

    result = quote_text
    sorted_keywords = sorted(emphasis_keywords, key=len, reverse=True)
    for kw in sorted_keywords:
        if not kw.strip():
            continue
        pattern = re.compile(re.escape(kw), re.IGNORECASE)
        result = pattern.sub(
            f'<tspan fill="{accent_color}" font-weight="900">{kw}</tspan>',
            result,
        )
    return result


def render_quote_banner_svg(
    x: float = 480.0,
    y: float = 930.0,
    width: float = 960.0,
    height: float = 84.0,
    text: str = "Một bức tường không chỉ bằng bê tông và dây thép gai, mà còn bằng nỗi sợ hãi và sự chia rẽ.",
    emphasis_keywords: list[str] | None = None,
    accent_color: str = "#E1B400",
    seed: int = 42,
) -> str:
    """Render charcoal brush quote banner at the bottom of the frame."""
    highlighted = highlight_keywords_in_quote(
        text, emphasis_keywords or ["nỗi sợ hãi", "sự chia rẽ"], accent_color=accent_color
    )
    center_x = x + width / 2.0
    text_y = y + height / 2.0 + 7.0

    return f"""
    <!-- Charcoal Quote Banner -->
    <g id="quote_banner" filter="drop-shadow(0px 4px 10px rgba(0,0,0,0.65))">
      <rect x="{x}" y="{y}" width="{width}" height="{height}" rx="6"
            fill="#121314" fill-opacity="0.92" stroke="#2A2C30" stroke-width="1.2" />
      <text x="{center_x}" y="{y + height / 2.0 + 8.0}"
            text-anchor="middle" xml:space="preserve"
            font-family="'Inter', 'Roboto', 'DejaVu Sans', sans-serif"
            font-size="22" font-weight="500" fill="#E8EDF2" letter-spacing="0.3">
        {highlighted}
      </text>
    </g>
    """.strip()
