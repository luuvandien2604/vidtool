"""Vox Collage Scene Compositor (Phase 2).

Orchestrates all collage layers into high-resolution SVG overlay vector graphics
matching the reference-faithful editorial standard.
"""
from __future__ import annotations

import html
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from videotool.render.collage.fact_card import render_fact_card_svg
from videotool.render.collage.map_card import render_map_card_svg
from videotool.render.collage.media_card import render_taped_media_card_svg
from videotool.render.collage.paper_panel import render_paper_panel_svg
from videotool.render.collage.quote_banner import render_quote_banner_svg
from videotool.render.collage.tape_decoration import render_tape_strip_svg


def generate_brush_stroke_svg(
    x: float,
    y: float,
    width: float,
    height: float = 16.0,
    color: str = "#E1B400",
    seed: int = 42,
) -> str:
    """Generate organic painterly yellow brush stroke under headlines."""
    rng = random.Random(seed)
    num_pts = 14
    dx = width / num_pts
    top_pts = []
    bot_pts = []
    for i in range(num_pts + 1):
        px = x + i * dx
        jt = (rng.random() - 0.5) * (height * 0.28)
        top_pts.append((px, y + jt))
        jb = (rng.random() - 0.5) * (height * 0.28)
        bot_pts.append((px, y + height + jb))

    cmd = [f"M {top_pts[0][0]:.1f},{top_pts[0][1]:.1f}"]
    for px, py in top_pts[1:]:
        cmd.append(f"L {px:.1f},{py:.1f}")
    for px, py in reversed(bot_pts):
        cmd.append(f"L {px:.1f},{py:.1f}")
    cmd.append("Z")
    d_str = " ".join(cmd)
    return (
        f'<path d="{d_str}" fill="{color}" opacity="0.94" '
        f'filter="drop-shadow(0px 2px 4px rgba(0,0,0,0.18))" />'
    )


def wrap_vietnamese_text(text: str, max_chars_per_line: int = 40) -> list[str]:
    """Wrap text cleanly into lines respecting word boundaries."""
    paragraphs = text.split("\n\n")
    all_lines = []
    for p_idx, p in enumerate(paragraphs):
        words = p.split()
        cur_line = []
        cur_len = 0
        for w in words:
            if cur_len + len(w) + (1 if cur_line else 0) <= max_chars_per_line:
                cur_line.append(w)
                cur_len += len(w) + (1 if len(cur_line) > 1 else 0)
            else:
                if cur_line:
                    all_lines.append(" ".join(cur_line))
                cur_line = [w]
                cur_len = len(w)
        if cur_line:
            all_lines.append(" ".join(cur_line))
        if p_idx < len(paragraphs) - 1:
            all_lines.append("")  # Paragraph separator
    return all_lines


@dataclass
class VoxEditorialSceneConfig:
    chapter_text: str = "CHƯƠNG 1"
    headline_lines: list[str] = field(default_factory=lambda: ["TIÊU ĐỀ CHÍNH", "BỐI CẢNH LỊCH SỬ"])
    body_paragraphs: str = ""
    date_milestone: str = "1961"
    date_title: str = "SỰ KIỆN LỊCH SỬ"
    date_subtitle: str = "MỐC QUAN TRỌNG"
    quote_text: str = ""
    quote_emphasis: list[str] = field(default_factory=list)
    show_map_card: bool = True
    map_label_west: str = "TÂY ĐỨC"
    map_label_east: str = "ĐÔNG ĐỨC"
    map_pin_label: str = "THỦ ĐÔ"
    secondary_cards: list[dict[str, Any]] = field(default_factory=list)
    canvas_w: int = 1920
    canvas_h: int = 1080
    paper_width: float = 720.0
    accent_yellow: str = "#E1B400"
    west_blue: str = "#33495A"
    east_red: str = "#8C3932"
    seed: int = 42


def render_vox_editorial_scene_svg(config: VoxEditorialSceneConfig) -> str:
    """Render complete high-resolution 1920x1080 SVG overlay for paper collage scene."""
    defs_xml, paper_xml = render_paper_panel_svg(
        width=config.paper_width,
        height=config.canvas_h,
        fill_color="#E7E0D2",
        seed=config.seed,
    )

    # 1. Chapter Badge
    chap_x = 60.0
    chap_y = 70.0
    chap_w = 140.0
    chap_h = 36.0
    chapter_svg = f"""
    <!-- Chapter Badge -->
    <g id="chapter_badge">
      <rect x="{chap_x}" y="{chap_y}" width="{chap_w}" height="{chap_h}" rx="18"
            fill="#161616" filter="drop-shadow(0px 2px 4px rgba(0,0,0,0.25))" />
      <text x="{chap_x + chap_w / 2.0}" y="{chap_y + 24.0}" text-anchor="middle"
            font-family="'Oswald', 'Montserrat', 'DejaVu Sans', sans-serif"
            font-size="15" font-weight="900" fill="#FFFFFF" letter-spacing="1.5">
        {html.escape(config.chapter_text)}
      </text>
    </g>
    """

    # 2. Headline & Yellow Brush Stroke
    head_x = 60.0
    head_y = 175.0
    line1 = config.headline_lines[0] if config.headline_lines else "TIÊU ĐỀ CHÍNH"
    line2 = config.headline_lines[1] if len(config.headline_lines) > 1 else "SỰ KIỆN LỊCH SỬ"

    # Brush stroke under line 1
    brush_svg = generate_brush_stroke_svg(
        x=head_x - 4.0,
        y=head_y + 12.0,
        width=480.0,
        height=18.0,
        color=config.accent_yellow,
        seed=config.seed,
    )

    headline_svg = f"""
    <!-- Headline Section -->
    <g id="headline_section">
      <text x="{head_x}" y="{head_y}"
            font-family="'Oswald', 'Bebas Neue', 'Impact', 'DejaVu Sans', sans-serif"
            font-size="64" font-weight="900" fill="#141618" letter-spacing="1.0">
        {html.escape(line1)}
      </text>
      {brush_svg}
      <text x="{head_x}" y="{head_y + 75.0}"
            font-family="'Oswald', 'Bebas Neue', 'Impact', 'DejaVu Sans', sans-serif"
            font-size="64" font-weight="900" fill="#141618" letter-spacing="1.0">
        {html.escape(line2)}
      </text>
    </g>
    """

    # 3. Body Text Paragraphs
    body_x = 60.0
    body_y = 310.0
    body_lines = wrap_vietnamese_text(config.body_paragraphs, max_chars_per_line=38)
    line_tspans = []
    cur_y = 0.0
    for line in body_lines:
        if line == "":
            cur_y += 18.0  # Paragraph gap
        else:
            line_tspans.append(f'<tspan x="{body_x}" y="{body_y + cur_y}">{html.escape(line)}</tspan>')
            cur_y += 30.0

    body_svg = f"""
    <!-- Body Paragraphs -->
    <text font-family="'Inter', 'Roboto', 'DejaVu Sans', sans-serif"
          font-size="18.5" font-weight="500" fill="#24282E" letter-spacing="0.2">
      {"".join(line_tspans)}
    </text>
    """

    # 4. Gold Milestone Fact Card
    fact_card_svg = render_fact_card_svg(
        x=60.0,
        y=745.0,
        width=510.0,
        height=135.0,
        date_text=config.date_milestone,
        title_text=config.date_title,
        subtitle_text=config.date_subtitle,
        accent_color=config.accent_yellow,
    )

    # 5. Top-Right Map Card
    map_svg = ""
    if config.show_map_card:
        map_svg = render_map_card_svg(
            x=1440.0,
            y=45.0,
            width=410.0,
            height=320.0,
            west_color=config.west_blue,
            east_color=config.east_red,
            tape_seed=config.seed + 10,
        )

    # 6. Secondary Taped Archival Cards (e.g. Warning sign and soldier photos bottom right)
    secondary_svgs = []
    for sc in config.secondary_cards:
        card_markup = render_taped_media_card_svg(
            image_href=sc["href"],
            x=sc.get("x", 1460.0),
            y=sc.get("y", 680.0),
            width=sc.get("width", 380.0),
            height=sc.get("height", 270.0),
            rotation_deg=sc.get("rotation", 4.0),
            tape_corners=sc.get("tape_corners", ("top-left", "top-right")),
            seed=config.seed + 20,
        )
        secondary_svgs.append(card_markup)

    # 7. Quote Banner
    quote_svg = ""
    if config.quote_text:
        quote_svg = render_quote_banner_svg(
            x=300.0,
            y=930.0,
            width=1320.0,
            height=86.0,
            text=config.quote_text,
            emphasis_keywords=config.quote_emphasis,
            accent_color=config.accent_yellow,
            seed=config.seed + 6,
        )

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg"
     xmlns:xlink="http://www.w3.org/1999/xlink"
     viewBox="0 0 {config.canvas_w} {config.canvas_h}"
     width="{config.canvas_w}" height="{config.canvas_h}">
  <defs>
    {defs_xml}
  </defs>

  {paper_xml}
  {chapter_svg}
  {headline_svg}
  {body_svg}
  {fact_card_svg}
  {map_svg}
  {"".join(secondary_svgs)}
  {quote_svg}
</svg>
""".strip()
