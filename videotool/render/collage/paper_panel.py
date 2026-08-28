"""Paper Panel Component (Phase 2).

Generates organic torn-paper boundary paths with procedural fiber displacements,
vintage parchment textures, and realistic drop shadows.
"""
from __future__ import annotations

import math
import random


def generate_torn_paper_path(
    width: float,
    height: float,
    seed: int = 42,
    segments: int = 28,
    roughness: float = 16.0,
) -> str:
    """Generate SVG path `d` attribute for a panel with a torn right edge."""
    rng = random.Random(seed)
    # Start at top-left, go across to top-right
    points = [(0.0, 0.0), (width, 0.0)]

    # Generate organic ragged right edge
    step_y = height / segments
    for i in range(1, segments):
        y = i * step_y
        offset_x = (rng.random() - 0.5) * 2.0 * roughness
        micro_jitter = (rng.random() - 0.5) * (roughness * 0.35)
        x = width + offset_x + micro_jitter
        points.append((x, y))

    points.append((width, height))
    points.append((0.0, height))

    # Construct SVG path commands with subtle smoothing curves
    cmd = [f"M {points[0][0]:.1f},{points[0][1]:.1f}"]
    cmd.append(f"L {points[1][0]:.1f},{points[1][1]:.1f}")
    for i in range(2, len(points) - 2):
        px, py = points[i]
        cmd.append(f"L {px:.1f},{py:.1f}")
    cmd.append(f"L {points[-2][0]:.1f},{points[-2][1]:.1f}")
    cmd.append(f"L {points[-1][0]:.1f},{points[-1][1]:.1f}")
    cmd.append("Z")
    return " ".join(cmd)


def render_paper_panel_svg(
    width: float = 720.0,
    height: float = 1080.0,
    fill_color: str = "#E7E0D2",
    seed: int = 42,
    show_shadow: bool = True,
) -> tuple[str, str]:
    """Render paper panel SVG defs and path element.

    Returns:
        (defs_xml, element_xml)
    """
    path_d = generate_torn_paper_path(width, height, seed=seed)
    defs_xml = """
    <filter id="paperShadow" x="-10%" y="-10%" width="130%" height="130%">
      <feGaussianBlur in="SourceAlpha" stdDeviation="12" />
      <feOffset dx="8" dy="4" result="offsetblur" />
      <feComponentTransfer>
        <feFuncA type="linear" slope="0.45" />
      </feComponentTransfer>
      <feMerge>
        <feMergeNode />
        <feMergeNode in="SourceGraphic" />
      </feMerge>
    </filter>
    <pattern id="paperGrain" width="100" height="100" patternUnits="userSpaceOnUse">
      <rect width="100" height="100" fill="#E7E0D2" />
      <circle cx="20" cy="30" r="1.5" fill="#D4CBBA" opacity="0.35" />
      <circle cx="70" cy="65" r="2.0" fill="#D4CBBA" opacity="0.30" />
      <circle cx="45" cy="85" r="1.0" fill="#C5BCA8" opacity="0.25" />
      <circle cx="85" cy="20" r="1.2" fill="#C5BCA8" opacity="0.30" />
    </pattern>
    """
    filter_attr = 'filter="url(#paperShadow)"' if show_shadow else ""
    element_xml = f"""
    <!-- Left Torn-Paper Panel -->
    <path d="{path_d}" fill="url(#paperGrain)" {filter_attr} />
    <path d="{path_d}" fill="{fill_color}" opacity="0.88" />
    """
    return defs_xml.strip(), element_xml.strip()
