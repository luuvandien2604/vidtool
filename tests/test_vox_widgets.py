"""Tests for Vox design tokens, specialized widgets, and art-direction immunity.

Validates that:
1. TimelineWidget renders horizontal and vertical spine lines with Vox Yellow.
2. StatBadgeWidget maps LOCATION to blue and all other badges/dates to Vox Yellow.
3. Infographic cards and widgets are 100% immune to per-episode art_direction overrides.
4. DATE disambiguation routes correctly between TimelineWidget and StatBadgeWidget.
5. Codebase adheres to generalization guidelines (0 forbidden domain words).
"""
import xml.etree.ElementTree as ET
from pathlib import Path

from videotool.render.frame_plan import (ConnectorRenderElement,
                                        PixelRect,
                                        TextRenderElement)
from videotool.render.svg_overlay import generate_svg_overlay
from videotool.render.vox_theme import DEFAULT_VOX_THEME, VoxColors, VoxTheme
from videotool.render.widgets.stat_badge import StatBadgeItem, StatBadgeWidget
from videotool.render.widgets.timeline import TimelineNodeItem, TimelineWidget


def test_vox_theme_tokens():
    """Verify that Vox palette tokens adhere to editorial color specifications."""
    assert VoxColors.ACCENT_YELLOW == "#FFD100"
    assert VoxColors.ACCENT_BLUE == "#3B82F6"
    assert VoxColors.BG_DARK_CARD == "#1C202B"
    assert VoxColors.BG_DARK_SLATE == "#14171F"
    assert VoxColors.TEXT_PRIMARY_LIGHT == "#F9FAFB"

    theme = VoxTheme()
    assert theme.colors.ACCENT_YELLOW == "#FFD100"
    assert theme.spacing.RADIUS_MD == 10.0
    assert "DejaVu Sans" in theme.typography.FONT_FAMILY_PRIMARY


def test_timeline_widget_horizontal_rendering():
    """Verify TimelineWidget generates valid SVG with horizontal spine and yellow accents."""
    widget = TimelineWidget()
    nodes = [
        TimelineNodeItem(node_id="n1", center_x=300.0, center_y=540.0, date_text="1989", label_text="Phase A"),
        TimelineNodeItem(node_id="n2", center_x=700.0, center_y=540.0, date_text="1990", label_text="Phase B"),
    ]
    fragments = widget.render_fragment(nodes, include_text=True)
    svg_doc = f'<svg xmlns="http://www.w3.org/2000/svg">\n<defs><filter id="card-drop-shadow"/></defs>\n' + "\n".join(fragments) + "\n</svg>"
    
    root = ET.fromstring(svg_doc)
    assert root.tag.endswith("svg")
    
    # Assert spine line with Vox Yellow accent
    lines = root.findall(".//{http://www.w3.org/2000/svg}line")
    assert len(lines) >= 2
    yellow_lines = [line for line in lines if line.attrib.get("stroke") == "#FFD100"]
    assert len(yellow_lines) >= 1
    assert float(yellow_lines[0].attrib["x1"]) == 300.0
    assert float(yellow_lines[0].attrib["x2"]) == 700.0


def test_timeline_widget_vertical_rendering_regression():
    """Regression test: verify vertical timeline spine layout when nodes share same X coordinate."""
    widget = TimelineWidget()
    # Reproduces Beat 5's vertical layout where X coordinates are identical
    nodes = [
        TimelineNodeItem(node_id="n_top", center_x=960.0, center_y=216.0, label_text="Stage 1"),
        TimelineNodeItem(node_id="n_bottom", center_x=960.0, center_y=540.0, label_text="Stage 2"),
    ]
    fragments = widget.render_fragment(nodes, include_text=True)
    svg_doc = f'<svg xmlns="http://www.w3.org/2000/svg">\n<defs><filter id="card-drop-shadow"/></defs>\n' + "\n".join(fragments) + "\n</svg>"
    
    root = ET.fromstring(svg_doc)
    lines = root.findall(".//{http://www.w3.org/2000/svg}line")
    assert len(lines) >= 2
    
    # Assert vertical spine connecting (960, 216) to (960, 540)
    yellow_vertical_lines = [
        line for line in lines 
        if line.attrib.get("stroke") == "#FFD100" 
        and float(line.attrib["x1"]) == float(line.attrib["x2"]) == 960.0
    ]
    assert len(yellow_vertical_lines) == 1
    assert float(yellow_vertical_lines[0].attrib["y1"]) == 216.0
    assert float(yellow_vertical_lines[0].attrib["y2"]) == 540.0


def test_stat_badge_widget_color_rules():
    """Verify that LOCATION uses blue and other facts use Vox Yellow."""
    widget = StatBadgeWidget()
    items = [
        StatBadgeItem(label="Capital City", value="Paris", kind="location", center_x=400.0, center_y=500.0),
        StatBadgeItem(label="Milestone Year", value="1989", kind="date", center_x=800.0, center_y=500.0),
        StatBadgeItem(label="Key Figure", value="Scientist", kind="person", center_x=1200.0, center_y=500.0),
    ]
    fragments = widget.render_fragment(items, include_text=True)
    svg_doc = f'<svg xmlns="http://www.w3.org/2000/svg">\n<defs><filter id="card-drop-shadow"/></defs>\n' + "\n".join(fragments) + "\n</svg>"
    
    root = ET.fromstring(svg_doc)
    rects = root.findall(".//{http://www.w3.org/2000/svg}rect")
    
    # Accent bars
    accent_fills = [r.attrib.get("fill") for r in rects if r.attrib.get("width") == "6.0" or r.attrib.get("width") == "6"]
    assert "#3B82F6" in accent_fills  # Blue for location
    assert "#FFD100" in accent_fills  # Yellow for date and person


def test_date_role_disambiguation():
    """Verify that DATE roles route to TimelineWidget in timeline family and StatBadgeWidget otherwise."""
    # Case A: Timeline family -> TimelineWidget
    elem_tl = TextRenderElement(
        element_id="elem_date_tl",
        text="November 1989",
        role="TIMELINE_NODE",
        text_role="DATE",
        z_index=1,
        bounds_norm={"x": 0.45, "y": 0.45, "w": 0.1, "h": 0.05},
        bounds_px=PixelRect(x=860, y=515, width=200, height=50),
        entrance_sec=0.0,
        exit_sec=5.0,
        style_name="NodeTimeline",
    )
    svg_tl = generate_svg_overlay(text_elements=[elem_tl], visual_family="chronological_timeline", include_text=True)
    assert svg_tl is not None
    assert "Timeline Node: elem_date_tl" in svg_tl

    # Case B: Standalone fact -> StatBadgeWidget
    elem_fact = TextRenderElement(
        element_id="elem_date_standalone",
        text="1989",
        role="DATE",
        text_role="DATE",
        z_index=1,
        bounds_norm={"x": 0.47, "y": 0.47, "w": 0.06, "h": 0.04},
        bounds_px=PixelRect(x=900, y=520, width=120, height=40),
        entrance_sec=0.0,
        exit_sec=5.0,
        style_name="NodeLabel",
    )
    svg_badge = generate_svg_overlay(text_elements=[elem_fact], visual_family="full_frame_cinematic", include_text=True)
    assert svg_badge is not None
    assert "Stat Badge: DATE" in svg_badge


def test_art_direction_override_immunity_regression():
    """Regression test: verify infographic cards & widgets are immune to art_direction accent overrides."""
    elem_label = TextRenderElement(
        element_id="elem_label",
        text="Crucial Observation",
        role="LABEL",
        text_role="LABEL",
        z_index=1,
        bounds_norm={"x": 0.42, "y": 0.47, "w": 0.16, "h": 0.06},
        bounds_px=PixelRect(x=810, y=510, width=300, height=60),
        entrance_sec=0.0,
        exit_sec=5.0,
        style_name="NodeLabel",
    )
    elem_quote = TextRenderElement(
        element_id="elem_quote",
        text="The decisive moment arrives",
        role="QUOTE",
        text_role="QUOTE",
        z_index=1,
        bounds_norm={"x": 0.41, "y": 0.46, "w": 0.18, "h": 0.08},
        bounds_px=PixelRect(x=790, y=500, width=340, height=80),
        entrance_sec=0.0,
        exit_sec=5.0,
        style_name="NodeQuote",
    )
    
    # Deliberately supply a contrasting art direction accent (bright green)
    fake_art_direction_accent = "#00FF00"
    
    svg = generate_svg_overlay(
        text_elements=[elem_label, elem_quote],
        accent_color=fake_art_direction_accent,
        include_text=True,
    )
    assert svg is not None
    
    # Assert that fake_art_direction_accent did NOT infect the SVG overlay
    assert fake_art_direction_accent not in svg
    # Assert signature Vox Yellow is strictly used for the card accents
    assert "#FFD100" in svg


def test_generalization_vox_codebase():
    """Verify no hardcoded domain strings exist in the render codebase outside fixtures/cli."""
    render_dir = Path(__file__).resolve().parent.parent / "videotool" / "render"
    forbidden_tokens = ["berlin", "schabowski", "bornholmer"]

    for py_file in render_dir.rglob("*.py"):
        content = py_file.read_text(encoding="utf-8").lower()
        for token in forbidden_tokens:
            assert token not in content, f"Forbidden domain token '{token}' detected in {py_file}"
