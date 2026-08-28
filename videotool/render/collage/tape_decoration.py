"""Tape Decoration Component (Phase 2).

Renders realistic semi-transparent matte masking tape strips with frayed/jagged
torn edges and subtle drop shadows.
"""
from __future__ import annotations

import math
import random


def generate_tape_polygon_points(
    cx: float,
    cy: float,
    width: float = 120.0,
    height: float = 34.0,
    angle_deg: float = 0.0,
    seed: int = 42,
) -> list[tuple[float, float]]:
    """Generate rotated polygon points with jagged ragged ends."""
    rng = random.Random(seed)
    half_w = width / 2.0
    half_h = height / 2.0
    rad = math.radians(angle_deg)
    cos_a = math.cos(rad)
    sin_a = math.sin(rad)

    def rot(lx: float, ly: float) -> tuple[float, float]:
        rx = lx * cos_a - ly * sin_a + cx
        ry = lx * sin_a + ly * cos_a + cy
        return (round(rx, 2), round(ry, 2))

    local_points = []
    # Top edge: left to right
    local_points.append((-half_w, -half_h))
    local_points.append((half_w, -half_h))

    # Right torn edge: jagged zig-zag downwards
    num_teeth = 6
    tooth_h = height / num_teeth
    for i in range(1, num_teeth):
        jitter = (rng.random() - 0.5) * 6.0
        local_points.append((half_w + jitter, -half_h + i * tooth_h))
    local_points.append((half_w, half_h))

    # Bottom edge: right to left
    local_points.append((-half_w, half_h))

    # Left torn edge: jagged zig-zag upwards
    for i in range(num_teeth - 1, 0, -1):
        jitter = (rng.random() - 0.5) * 6.0
        local_points.append((-half_w + jitter, -half_h + i * tooth_h))

    return [rot(lx, ly) for lx, ly in local_points]


def render_tape_strip_svg(
    cx: float,
    cy: float,
    width: float = 120.0,
    height: float = 34.0,
    angle_deg: float = 0.0,
    color: str = "rgba(242, 238, 224, 0.78)",
    seed: int = 42,
) -> str:
    """Render a single masking tape strip SVG element."""
    points = generate_tape_polygon_points(cx, cy, width, height, angle_deg, seed)
    pts_str = " ".join(f"{x},{y}" for x, y in points)
    return (
        f'<polygon points="{pts_str}" fill="{color}" stroke="rgba(215, 205, 185, 0.5)" '
        f'stroke-width="1.0" filter="drop-shadow(0px 2px 3px rgba(0,0,0,0.22))" />'
    )
