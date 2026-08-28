"""Vox Paper Collage procedural SVG and composite rendering engine (Phase A).

Generates deterministic paper-collage visual assets:
1. Procedural torn-paper edge masks (seeded per beat).
2. Vintage paper texture & drop shadow filters.
3. Chapter pill badges (e.g. 'CHƯƠNG 1').
4. Condensed headlines with procedural yellow brush-stroke underlines.
5. Framed gold fact boxes (date + event milestones).
6. Semi-transparent tape strip corner decorations for insets.
7. Bottom quote banners with gold-highlighted emphasis keywords.
"""
from __future__ import annotations

import html
import random
import re
from dataclasses import dataclass, field
from typing import Any

from videotool.render.vox_theme import DEFAULT_VOX_THEME, VoxTheme


def generate_torn_paper_path(width: float, height: float, seed: str | int,
                             segments: int = 40, roughness: float = 10.0) -> str:
    """Generate a deterministic SVG path for a torn-paper panel anchored on the left.

    The left, top, and bottom edges are straight; the right edge is organically
    torn/jagged using deterministic pseudo-random offsets seeded by the given seed.
    """
    rng = random.Random(f"torn_paper_{seed}")
    d_parts = [f"M 0 0", f"L {width:.2f} 0"]

    # Generate jagged right edge from top (y=0) to bottom (y=height)
    step_y = height / max(1, segments)
    for i in range(1, segments):
        curr_y = i * step_y
        jitter = rng.uniform(-roughness, roughness)
        curr_x = max(20.0, width + jitter)
        d_parts.append(f"L {curr_x:.2f} {curr_y:.2f}")

    d_parts.append(f"L {width:.2f} {height:.2f}")
    d_parts.append(f"L 0 {height:.2f}")
    d_parts.append("Z")

    return " ".join(d_parts)


def generate_brush_stroke_svg(x: float, y: float, width: float, height: float = 12.0,
                              color: str = "#E1B400", seed: str | int = 0) -> str:
    """Generate an organic procedural yellow brush stroke underline path."""
    rng = random.Random(f"brush_{seed}")
    w = max(40.0, width)
    h = max(6.0, height)

    # Build an organic tapered polygon representing a paint brush swipe
    p1 = (x, y + h * 0.4)
    p2 = (x + w * 0.15, y + rng.uniform(-1.5, 1.5))
    p3 = (x + w * 0.5, y + rng.uniform(-2.0, 1.0))
    p4 = (x + w * 0.85, y + rng.uniform(-1.0, 2.0))
    p5 = (x + w, y + h * 0.5)
    p6 = (x + w * 0.9, y + h + rng.uniform(-1.5, 1.5))
    p7 = (x + w * 0.5, y + h + rng.uniform(-2.0, 1.5))
    p8 = (x + w * 0.1, y + h + rng.uniform(-1.0, 2.0))

    pts = f"M {p1[0]:.1f} {p1[1]:.1f} Q {p2[0]:.1f} {p2[1]:.1f} {p3[0]:.1f} {p3[1]:.1f} " \
          f"T {p5[0]:.1f} {p5[1]:.1f} Q {p6[0]:.1f} {p6[1]:.1f} {p7[0]:.1f} {p7[1]:.1f} " \
          f"T {p1[0]:.1f} {p1[1]:.1f} Z"

    return f'<path d="{pts}" fill="{color}" opacity="0.92"/>'


def generate_tape_strip_svg(cx: float, cy: float, width: float = 84.0, height: float = 24.0,
                            angle_deg: float = -10.0, seed: str | int = 0) -> str:
    """Generate a semi-transparent vintage tape strip with soft shadow."""
    x = cx - width / 2.0
    y = cy - height / 2.0
    return (
        f'<g transform="rotate({angle_deg:.1f} {cx:.1f} {cy:.1f})">'
        f'  <rect x="{x+1:.1f}" y="{y+2:.1f}" width="{width:.1f}" height="{height:.1f}" rx="2" '
        f'fill="#000000" opacity="0.25"/>'
        f'  <rect x="{x:.1f}" y="{y:.1f}" width="{width:.1f}" height="{height:.1f}" rx="2" '
        f'fill="#F8F6E6" fill-opacity="0.65" stroke="#DCD5BC" stroke-opacity="0.5" stroke-width="1"/>'
        f'</g>'
    )


def generate_chapter_pill_svg(x: float, y: float, text: str = "CHƯƠNG 1",
                              accent_color: str = "#E1B400") -> str:
    """Generate a rounded chapter pill badge (e.g. 'CHƯƠNG 1')."""
    clean_txt = html.escape(text.upper())
    w = max(110.0, len(text) * 11.5 + 32.0)
    h = 32.0
    return (
        f'<g transform="translate({x:.1f}, {y:.1f})">'
        f'  <rect x="0" y="0" width="{w:.1f}" height="{h:.1f}" rx="{h/2.0:.1f}" '
        f'fill="#111111" stroke="{accent_color}" stroke-width="1.8"/>'
        f'  <text x="{w/2.0:.1f}" y="21.5" fill="#E7E0D2" '
        f'font-family="DejaVu Sans, Liberation Sans, sans-serif" font-size="13" font-weight="bold" '
        f'letter-spacing="1.5" text-anchor="middle">{clean_txt}</text>'
        f'</g>'
    )


def generate_gold_fact_box_svg(x: float, y: float, width: float, height: float,
                               date_text: str, title_text: str, subtitle_text: str = "",
                               accent_color: str = "#E1B400") -> str:
    """Generate a structured milestone fact box with gold frame and typography."""
    esc_date = html.escape(date_text.strip())
    esc_title = html.escape(title_text.strip().upper())
    esc_sub = html.escape(subtitle_text.strip().upper())

    w = max(240.0, width)
    h = max(70.0, height)

    lines = [
        f'<g transform="translate({x:.1f}, {y:.1f})">',
        f'  <!-- Card Background & Drop Shadow -->',
        f'  <rect x="0" y="0" width="{w:.1f}" height="{h:.1f}" rx="4" fill="#121212" '
        f'stroke="{accent_color}" stroke-width="2" filter="url(#card-drop-shadow)"/>',
    ]

    if esc_date and (esc_title or esc_sub):
        lines.append(
            f'  <text x="18" y="28" fill="{accent_color}" '
            f'font-family="DejaVu Sans, Liberation Sans, sans-serif" font-size="18" font-weight="bold" '
            f'letter-spacing="0.8">{esc_date}</text>'
        )
        if esc_title:
            lines.append(
                f'  <text x="18" y="50" fill="#E7E0D2" '
                f'font-family="DejaVu Sans, Liberation Sans, sans-serif" font-size="14" font-weight="bold" '
                f'letter-spacing="0.5">{esc_title}</text>'
            )
        if esc_sub:
            lines.append(
                f'  <text x="18" y="68" fill="#A0AEC0" '
                f'font-family="DejaVu Sans, Liberation Sans, sans-serif" font-size="12" '
                f'letter-spacing="0.4">{esc_sub}</text>'
            )
    elif esc_date:
        lines.append(
            f'  <text x="{w/2.0:.1f}" y="{h/2.0 + 7:.1f}" fill="{accent_color}" '
            f'font-family="DejaVu Sans, Liberation Sans, sans-serif" font-size="20" font-weight="bold" '
            f'text-anchor="middle">{esc_date}</text>'
        )
    else:
        lines.append(
            f'  <text x="{w/2.0:.1f}" y="{h/2.0 + 7:.1f}" fill="#E7E0D2" '
            f'font-family="DejaVu Sans, Liberation Sans, sans-serif" font-size="16" font-weight="bold" '
            f'text-anchor="middle">{esc_title}</text>'
        )

    lines.append('</g>')
    return "\n".join(lines)


def highlight_keywords_in_quote(quote_text: str,
                                emphasis_keywords: list[str] | None = None,
                                accent_color: str = "#E1B400") -> str:
    """Format quote text into SVG tspans with emphasized keywords rendered in gold."""
    if not quote_text:
        return ""

    if not emphasis_keywords:
        return f'<tspan fill="#E7E0D2">{html.escape(quote_text)}</tspan>'

    # Build regex for word/phrase boundary matching (case-insensitive)
    escaped_keys = [re.escape(k.strip()) for k in emphasis_keywords if k and k.strip()]
    if not escaped_keys:
        return f'<tspan fill="#E7E0D2">{html.escape(quote_text)}</tspan>'

    pattern = re.compile(rf"({'|'.join(escaped_keys)})", re.IGNORECASE)
    parts = pattern.split(quote_text)

    tspans: list[str] = []
    for part in parts:
        if not part:
            continue
        # Check if this part matches any emphasis keyword
        is_emphasis = any(part.lower() == k.lower() for k in emphasis_keywords if k)
        clean = html.escape(part)
        if is_emphasis:
            tspans.append(f'<tspan fill="{accent_color}" font-weight="bold">{clean}</tspan>')
        else:
            tspans.append(f'<tspan fill="#E7E0D2">{clean}</tspan>')

    return "".join(tspans)


def generate_quote_banner_svg(x: float, y: float, width: float, height: float,
                              text: str, emphasis_keywords: list[str] | None = None,
                              accent_color: str = "#E1B400", seed: str | int = 0) -> str:
    """Generate a dark bottom-center quote banner with highlighted keywords."""
    if not text:
        return ""

    w = max(400.0, width)
    h = max(50.0, height)
    tspan_content = highlight_keywords_in_quote(text, emphasis_keywords, accent_color)

    return (
        f'<g transform="translate({x:.1f}, {y:.1f})">'
        f'  <!-- Dark Brush / Paper Banner Background -->'
        f'  <rect x="0" y="0" width="{w:.1f}" height="{h:.1f}" rx="6" fill="#111111" fill-opacity="0.92" '
        f'stroke="#2A2A28" stroke-width="1.5" filter="url(#card-drop-shadow)"/>'
        f'  <!-- Quote text with gold keyword spans -->'
        f'  <text x="{w/2.0:.1f}" y="{h/2.0 + 6.0:.1f}" text-anchor="middle" '
        f'font-family="DejaVu Sans, Liberation Sans, sans-serif" font-size="18" '
        f'letter-spacing="0.3" xml:space="preserve">{tspan_content}</text>'
        f'</g>'
    )


@dataclass
class VoxCollageData:
    """Data payload describing a rich Vox Paper Collage layout for one beat."""
    beat_id: str
    chapter_text: str = "CHƯƠNG 1"
    headline_lines: list[str] = field(default_factory=list)
    body_paragraph: str = ""
    date_milestone: str = ""
    date_title: str = ""
    date_subtitle: str = ""
    quote_text: str = ""
    quote_emphasis: list[str] = field(default_factory=list)
    insets: list[dict[str, Any]] = field(default_factory=list)  # [{'x': float, 'y': float, 'w': float, 'h': float, 'taped': bool}]
    accent_color: str = "#E1B400"
    paper_width: float = 720.0  # ~38% of 1920


def generate_vox_collage_overlay_svg(collage: VoxCollageData,
                                    canvas_w: int = 1920,
                                    canvas_h: int = 1080,
                                    theme: VoxTheme | None = None) -> str:
    """Generate a complete 1080p SVG vector overlay representing a Vox Paper Collage."""
    active_theme = theme or DEFAULT_VOX_THEME
    accent = collage.accent_color or active_theme.colors.ACCENT_GOLD
    seed = collage.beat_id

    elements: list[str] = []

    # 1. Defs: Shadows, paper gradient, and textures
    elements.append('<defs>')
    elements.append('  <filter id="paper-drop-shadow" x="-10%" y="-10%" width="130%" height="130%">')
    elements.append('    <feDropShadow dx="8" dy="4" stdDeviation="10" flood-color="#000000" flood-opacity="0.6"/>')
    elements.append('  </filter>')
    elements.append('  <filter id="card-drop-shadow" x="-15%" y="-15%" width="135%" height="140%">')
    elements.append('    <feDropShadow dx="0" dy="4" stdDeviation="6" flood-color="#000000" flood-opacity="0.65"/>')
    elements.append('  </filter>')
    elements.append('  <linearGradient id="agedPaperGrad" x1="0%" y1="0%" x2="100%" y2="100%">')
    elements.append('    <stop offset="0%" stop-color="#FAF8F5"/>')
    elements.append('    <stop offset="70%" stop-color="#E7E0D2"/>')
    elements.append('    <stop offset="100%" stop-color="#DFD7C7"/>')
    elements.append('  </linearGradient>')
    elements.append('</defs>')

    # 2. Torn Paper Sidebar Panel (Left side ~38% width)
    torn_path = generate_torn_paper_path(
        width=collage.paper_width,
        height=float(canvas_h),
        seed=seed,
        segments=42,
        roughness=12.0,
    )
    elements.append(
        f'<!-- Torn-Paper Sidebar Panel -->\n'
        f'<path d="{torn_path}" fill="url(#agedPaperGrad)" filter="url(#paper-drop-shadow)"/>'
    )

    # 3. Chapter Pill Badge
    pill_y = 60.0
    elements.append(generate_chapter_pill_svg(x=60.0, y=pill_y, text=collage.chapter_text, accent_color=accent))

    # 4. Headline & Yellow Brush Stroke Underline
    headline_y = pill_y + 68.0
    max_line_w = 0.0
    for idx, line in enumerate(collage.headline_lines or ["BỐI CẢNH LỊCH SỬ", "SỰ KIỆN NỔI BẬT"]):
        clean_line = html.escape(line.upper())
        line_w = len(line) * 22.0
        max_line_w = max(max_line_w, line_w)
        elements.append(
            f'<text x="60" y="{headline_y + idx * 46:.1f}" fill="#111111" '
            f'font-family="DejaVu Sans, Liberation Sans, sans-serif" font-size="38" font-weight="bold" '
            f'letter-spacing="0.5">{clean_line}</text>'
        )

    brush_y = headline_y + len(collage.headline_lines or ["", ""]) * 46.0 - 10.0
    brush_w = min(collage.paper_width - 120.0, max(180.0, max_line_w * 0.85))
    elements.append(generate_brush_stroke_svg(x=60.0, y=brush_y, width=brush_w, height=10.0, color=accent, seed=seed))

    # 5. Body Context Paragraph
    body_y = brush_y + 36.0
    if collage.body_paragraph:
        # Wrap paragraph into multiple lines (approx 38 chars per line)
        words = collage.body_paragraph.split()
        lines: list[str] = []
        cur_line: list[str] = []
        cur_len = 0
        for w in words:
            if cur_len + len(w) + 1 > 42:
                lines.append(" ".join(cur_line))
                cur_line = [w]
                cur_len = len(w)
            else:
                cur_line.append(w)
                cur_len += len(w) + 1
        if cur_line:
            lines.append(" ".join(cur_line))

        # Render maximum 6 lines of body context
        for l_idx, bl in enumerate(lines[:6]):
            elements.append(
                f'<text x="60" y="{body_y + l_idx * 26:.1f}" fill="#2A2A28" '
                f'font-family="DejaVu Sans, Liberation Sans, sans-serif" font-size="16" '
                f'letter-spacing="0.2">{html.escape(bl)}</text>'
            )

    # 6. Framed Gold Fact Box
    fact_y = canvas_h - 220.0
    if collage.date_milestone or collage.date_title:
        fact_w = collage.paper_width - 140.0
        elements.append(
            generate_gold_fact_box_svg(
                x=60.0,
                y=fact_y,
                width=fact_w,
                height=90.0,
                date_text=collage.date_milestone or "",
                title_text=collage.date_title or "SỰ KIỆN LỊCH SỬ",
                subtitle_text=collage.date_subtitle or "MỐC THỜI GIAN QUAN TRỌNG",
                accent_color=accent,
            )
        )

    # 7. Tape Strips on Inset Elements (Top-right / Bottom-right)
    for ins in collage.insets:
        ix, iy, iw, ih = ins.get("x", 0.0), ins.get("y", 0.0), ins.get("w", 0.0), ins.get("h", 0.0)
        if ins.get("taped", True) and iw > 0 and ih > 0:
            # Top-left tape
            elements.append(generate_tape_strip_svg(cx=ix + 20.0, cy=iy + 5.0, angle_deg=-15.0, seed=f"{seed}_tl"))
            # Top-right tape
            elements.append(generate_tape_strip_svg(cx=ix + iw - 20.0, cy=iy + 5.0, angle_deg=12.0, seed=f"{seed}_tr"))
            # Bottom-right tape (optional)
            if ih > 160.0:
                elements.append(generate_tape_strip_svg(cx=ix + iw - 15.0, cy=iy + ih - 5.0, angle_deg=-8.0, seed=f"{seed}_br"))

    # 8. Bottom Highlight Quote Banner
    if collage.quote_text:
        qw = min(1100.0, canvas_w * 0.58)
        qh = 72.0
        qx = (canvas_w - qw) / 2.0 + 120.0  # Centered in the right visual area
        qy = canvas_h - 115.0
        elements.append(
            generate_quote_banner_svg(
                x=qx,
                y=qy,
                width=qw,
                height=qh,
                text=collage.quote_text,
                emphasis_keywords=collage.quote_emphasis,
                accent_color=accent,
                seed=seed,
            )
        )

    body = "\n".join(elements)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{canvas_w}" height="{canvas_h}" '
        f'viewBox="0 0 {canvas_w} {canvas_h}">\n{body}\n</svg>'
    )
