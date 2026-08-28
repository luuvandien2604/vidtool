"""Historical Map Card Component (Phase 2).

Renders authoritative divided geography vector map card with West sector
(slate blue #33495A), East sector (dark red #8C3932), border division, and chalk callout arrow.
"""
from __future__ import annotations

from videotool.render.collage.tape_decoration import render_tape_strip_svg


def render_map_card_svg(
    x: float = 1460.0,
    y: float = 45.0,
    width: float = 380.0,
    height: float = 320.0,
    west_color: str = "#33495A",
    east_color: str = "#8C3932",
    label_west: str = "TÂY ĐỨC",
    label_east: str = "ĐÔNG ĐỨC",
    pin_label: str = "THỦ ĐÔ",
    tape_seed: int = 42,
) -> str:
    """Render historical division vector card with masking tape."""
    card_cx = x + width / 2.0
    card_cy = y + height / 2.0

    # Tape strips on top-left and bottom-right corners
    tape_tl = render_tape_strip_svg(x + 20.0, y + 10.0, width=110.0, height=32.0, angle_deg=-18.0, seed=tape_seed)
    tape_br = render_tape_strip_svg(
        x + width - 15.0, y + height - 10.0, width=110.0, height=32.0, angle_deg=14.0, seed=tape_seed + 1
    )

    # Stylized boundary shapes for West & East sectors
    # Centered in map card
    mx = x + 40.0
    my = y + 40.0
    mw = width - 80.0
    mh = height - 80.0

    # West sector polygon
    west_path = (
        f"M {mx + mw * 0.10:.1f},{my + mh * 0.20:.1f} "
        f"L {mx + mw * 0.45:.1f},{my + mh * 0.15:.1f} "
        f"L {mx + mw * 0.50:.1f},{my + mh * 0.50:.1f} "
        f"L {mx + mw * 0.48:.1f},{my + mh * 0.85:.1f} "
        f"L {mx + mw * 0.20:.1f},{my + mh * 0.88:.1f} "
        f"L {mx + mw * 0.08:.1f},{my + mh * 0.60:.1f} Z"
    )

    # East sector polygon
    east_path = (
        f"M {mx + mw * 0.50:.1f},{my + mh * 0.15:.1f} "
        f"L {mx + mw * 0.88:.1f},{my + mh * 0.22:.1f} "
        f"L {mx + mw * 0.92:.1f},{my + mh * 0.68:.1f} "
        f"L {mx + mw * 0.75:.1f},{my + mh * 0.90:.1f} "
        f"L {mx + mw * 0.50:.1f},{my + mh * 0.85:.1f} "
        f"L {mx + mw * 0.52:.1f},{my + mh * 0.50:.1f} Z"
    )

    # Border division line
    border_d = f"M {mx + mw * 0.47:.1f},{my + mh * 0.15:.1f} Q {mx + mw * 0.52:.1f},{my + mh * 0.50:.1f} {mx + mw * 0.49:.1f},{my + mh * 0.85:.1f}"

    # Chalk arrow pointing to center pin
    arrow_d = f"M {mx - 15:.1f},{my + 20:.1f} C {mx + 10:.1f},{my + 35:.1f} {mx + 30:.1f},{my + 45:.1f} {mx + mw * 0.45:.1f},{my + mh * 0.45:.1f}"

    return f"""
    <!-- Historical Division Map Card -->
    <g id="map_card" filter="drop-shadow(0px 6px 14px rgba(0,0,0,0.55))">
      <!-- Dark Card Backing -->
      <rect x="{x}" y="{y}" width="{width}" height="{height}" rx="4"
            fill="#1E2024" stroke="#32363D" stroke-width="1.5" />

      <!-- Map Sectors -->
      <path d="{west_path}" fill="{west_color}" stroke="#1E2024" stroke-width="1.5" />
      <path d="{east_path}" fill="{east_color}" stroke="#1E2024" stroke-width="1.5" />

      <!-- Dividing Border -->
      <path d="{border_d}" fill="none" stroke="#FFFFFF" stroke-width="2.5" stroke-dasharray="4,3" />

      <!-- Sector Labels -->
      <text x="{mx + mw * 0.26:.1f}" y="{my + mh * 0.55:.1f}" text-anchor="middle"
            font-family="'Oswald', 'Montserrat', 'DejaVu Sans', sans-serif"
            font-size="14" font-weight="700" fill="#E2E8F0" letter-spacing="0.5">
        {label_west}
      </text>
      <text x="{mx + mw * 0.74:.1f}" y="{my + mh * 0.55:.1f}" text-anchor="middle"
            font-family="'Oswald', 'Montserrat', 'DejaVu Sans', sans-serif"
            font-size="14" font-weight="700" fill="#E2E8F0" letter-spacing="0.5">
        {label_east}
      </text>

      <!-- Center Pinpoint -->
      <circle cx="{mx + mw * 0.49:.1f}" cy="{my + mh * 0.46:.1f}" r="4.5" fill="#161616" stroke="#FFFFFF" stroke-width="2.0" />
      <text x="{mx + mw * 0.49:.1f}" y="{my + mh * 0.38:.1f}" text-anchor="middle"
            font-family="'Oswald', 'Montserrat', 'DejaVu Sans', sans-serif"
            font-size="13" font-weight="800" fill="#FFFFFF" letter-spacing="1.0">
        {pin_label}
      </text>

      <!-- Chalk Arrow Callout -->
      <path d="{arrow_d}" fill="none" stroke="#FFFFFF" stroke-width="1.8" stroke-dasharray="3,2" opacity="0.85" />

      <!-- Corner Tape Strips -->
      {tape_tl}
      {tape_br}
    </g>
    """.strip()
