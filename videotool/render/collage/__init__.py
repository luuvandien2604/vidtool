"""Modular Vox Collage Rendering Engine (Phase 2)."""
from __future__ import annotations

from videotool.render.collage.fact_card import render_fact_card_svg
from videotool.render.collage.map_card import render_map_card_svg
from videotool.render.collage.media_card import render_taped_media_card_svg
from videotool.render.collage.paper_panel import (generate_torn_paper_path,
                                                 render_paper_panel_svg)
from videotool.render.collage.quote_banner import (highlight_keywords_in_quote,
                                                  render_quote_banner_svg)
from videotool.render.collage.scene import (VoxEditorialSceneConfig,
                                           generate_brush_stroke_svg,
                                           render_vox_editorial_scene_svg)
from videotool.render.collage.tape_decoration import (
    generate_tape_polygon_points, render_tape_strip_svg)

__all__ = [
    "render_paper_panel_svg",
    "generate_torn_paper_path",
    "render_tape_strip_svg",
    "generate_tape_polygon_points",
    "render_fact_card_svg",
    "render_quote_banner_svg",
    "highlight_keywords_in_quote",
    "render_map_card_svg",
    "render_taped_media_card_svg",
    "generate_brush_stroke_svg",
    "VoxEditorialSceneConfig",
    "render_vox_editorial_scene_svg",
]
