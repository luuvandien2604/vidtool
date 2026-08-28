"""Media Card Component (Phase 2).

Renders pinned archival photo cards and historical sign insets with subtle
polaroid/newsprint borders, corner masking tape, and drop shadows.
"""
from __future__ import annotations

import base64
from pathlib import Path
from videotool.render.collage.tape_decoration import render_tape_strip_svg


def to_data_uri(path_or_url: str) -> str:
    """Convert file path to base64 data URI if it is a local file."""
    if path_or_url.startswith("data:") or path_or_url.startswith("http"):
        return path_or_url
    p = Path(path_or_url)
    if p.exists() and p.is_file():
        ext = p.suffix.lower().lstrip(".")
        mime = f"image/{ext}" if ext in ("png", "jpeg", "webp") else "image/png"
        if ext == "jpg":
            mime = "image/jpeg"
        encoded = base64.b64encode(p.read_bytes()).decode("utf-8")
        return f"data:{mime};base64,{encoded}"
    return path_or_url


def render_taped_media_card_svg(
    image_href: str,
    x: float,
    y: float,
    width: float,
    height: float,
    rotation_deg: float = 0.0,
    tape_corners: tuple[str, ...] = ("top-left", "bottom-right"),
    border_width: float = 6.0,
    seed: int = 42,
) -> str:
    """Render a photo/document card with tape strips holding its corners."""
    center_x = x + width / 2.0
    center_y = y + height / 2.0
    transform = f'transform="rotate({rotation_deg} {center_x} {center_y})"' if rotation_deg != 0.0 else ""
    data_uri = to_data_uri(image_href)

    tape_elements = []
    if "top-left" in tape_corners:
        tape_elements.append(
            render_tape_strip_svg(x + 12.0, y + 8.0, width=90.0, height=28.0, angle_deg=-20.0, seed=seed)
        )
    if "top-right" in tape_corners:
        tape_elements.append(
            render_tape_strip_svg(x + width - 12.0, y + 8.0, width=90.0, height=28.0, angle_deg=20.0, seed=seed + 1)
        )
    if "bottom-left" in tape_corners:
        tape_elements.append(
            render_tape_strip_svg(x + 12.0, y + height - 8.0, width=90.0, height=28.0, angle_deg=20.0, seed=seed + 2)
        )
    if "bottom-right" in tape_corners:
        tape_elements.append(
            render_tape_strip_svg(
                x + width - 12.0, y + height - 8.0, width=90.0, height=28.0, angle_deg=-15.0, seed=seed + 3
            )
        )

    tapes_xml = "\n      ".join(tape_elements)
    img_x = x + border_width
    img_y = y + border_width
    img_w = width - 2 * border_width
    img_h = height - 2 * border_width

    return f"""
    <!-- Archival Media Card -->
    <g {transform} filter="drop-shadow(0px 8px 16px rgba(0,0,0,0.60))">
      <!-- Card Frame -->
      <rect x="{x}" y="{y}" width="{width}" height="{height}" rx="3"
            fill="#EFECE6" stroke="#D2CBC0" stroke-width="1.2" />

      <!-- Archival Image Embed -->
      <image href="{data_uri}" x="{img_x}" y="{img_y}" width="{img_w}" height="{img_h}"
             preserveAspectRatio="xMidYMid slice" />

      <!-- Masking Tape Overlays -->
      {tapes_xml}
    </g>
    """.strip()
