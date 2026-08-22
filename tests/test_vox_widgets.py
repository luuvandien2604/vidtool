"""Tests for Vox design tokens, TimelineWidget, and StatBadgeWidget."""
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from videotool.render.frame_plan import PixelRect, TextRenderElement, ConnectorRenderElement
from videotool.render.svg_overlay import generate_svg_overlay
from videotool.render.vox_theme import (DEFAULT_VOX_THEME, VoxColors,
                                        VoxSpacing, VoxTheme, VoxTypography)
from videotool.render.widgets.stat_badge import StatBadgeItem, StatBadgeWidget
from videotool.render.widgets.timeline import TimelineNodeItem, TimelineWidget


def test_vox_theme_tokens():
    """Verify Vox color tokens, typography defaults, and spacing constants."""
    theme = DEFAULT_VOX_THEME
    assert theme.colors.ACCENT_YELLOW == "#FFD100"
    assert theme.colors.BG_DARK_SLATE == "#14171F"
    assert theme.colors.BG_DARK_CARD == "#1C202B"
    assert "DejaVu Sans" in theme.typography.FONT_FAMILY_PRIMARY
    assert theme.spacing.TIMELINE_NODE_RADIUS == 10.0
    assert theme.spacing.ACCENT_BAR_WIDTH == 6.0

    # Color resolution
    assert theme.resolve_color("#123456") == "#123456"
    assert theme.resolve_color("accent_yellow") == "#FFD100"
    assert theme.resolve_color("ACCENT-CORAL") == "#E11D48"
    assert theme.resolve_color(None) == "#FFD100"


def test_timeline_widget_rendering():
    """Verify TimelineWidget produces valid SVG with spine line, halos, dates, and labels."""
    widget = TimelineWidget()
    nodes = [
        TimelineNodeItem(
            node_id="node_1",
            center_x=400.0,
            center_y=540.0,
            date_text="1989",
            label_text="Border Opens",
            is_active=False,
        ),
        TimelineNodeItem(
            node_id="node_2",
            center_x=960.0,
            center_y=540.0,
            date_text="November 1989",
            label_text="Press Conference",
            is_active=True,
        ),
        TimelineNodeItem(
            node_id="node_3",
            center_x=1520.0,
            center_y=540.0,
            date_text="Midnight",
            label_text="Gates Open",
            is_active=False,
        ),
    ]

    fragments = widget.render_fragment(nodes)
    assert len(fragments) > 0
    full_svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="1920" height="1080">\n' + "\n".join(fragments) + "\n</svg>"

    # Validate well-formed XML
    root = ET.fromstring(full_svg)
    assert root.tag == "{http://www.w3.org/2000/svg}svg"

    # Check for spine lines (shadow + accent)
    lines = root.findall(".//{http://www.w3.org/2000/svg}line")
    assert len(lines) >= 2  # Spine lines

    # Check for text elements
    texts = [t.text for t in root.findall(".//{http://www.w3.org/2000/svg}text")]
    assert "1989" in texts
    assert "November 1989" in texts
    assert "Press Conference" in texts
    assert "Gates Open" in texts


def test_stat_badge_widget_rendering():
    """Verify StatBadgeWidget renders pure SVG vector icons, labels, and values."""
    widget = StatBadgeWidget()
    items = [
        StatBadgeItem(label="YEAR", value="1989", kind="date", center_x=400.0, center_y=300.0),
        StatBadgeItem(label="LOCATION", value="Central Checkpoint", kind="location", center_x=960.0, center_y=300.0),
        StatBadgeItem(label="FIGURE", value="Government Spokesman", kind="person", center_x=1520.0, center_y=300.0),
        StatBadgeItem(label="ESTIMATE", value="50,000 People", kind="metric", center_x=960.0, center_y=700.0),
    ]

    fragments = widget.render_fragment(items)
    full_svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="1920" height="1080">\n'
        '  <defs><filter id="card-drop-shadow"><feDropShadow dx="0" dy="4" stdDeviation="6"/></filter></defs>\n'
        + "\n".join(fragments)
        + "\n</svg>"
    )

    # Validate XML parsing
    root = ET.fromstring(full_svg)
    assert root.tag == "{http://www.w3.org/2000/svg}svg"

    # Check that paths and circles exist for icons
    assert len(root.findall(".//{http://www.w3.org/2000/svg}circle")) >= 4
    texts = [t.text for t in root.findall(".//{http://www.w3.org/2000/svg}text")]
    assert "1989" in texts
    assert "LOCATION" in texts
    assert "Central Checkpoint" in texts
    assert "50,000 People" in texts


def test_date_role_disambiguation():
    """Explicitly verify DATE disambiguation rule: timeline sequence vs standalone fact."""
    # Case A: Multi-node sequence in chronological_timeline family -> routes to TimelineWidget
    timeline_texts = [
        TextRenderElement(
            element_id="t1",
            text="1989: Event A",
            role="TIMELINE_NODE",
            text_role="DATE",
            z_index=1,
            bounds_norm={"x": 0.2, "y": 0.5, "width": 0.2, "height": 0.1},
            bounds_px=PixelRect(x=384, y=540, width=200, height=60),
            entrance_sec=0.0,
            exit_sec=5.0,
            style_name="NodeTimeline",
        ),
        TextRenderElement(
            element_id="t2",
            text="1990: Event B",
            role="TIMELINE_NODE",
            text_role="DATE",
            z_index=1,
            bounds_norm={"x": 0.6, "y": 0.5, "width": 0.2, "height": 0.1},
            bounds_px=PixelRect(x=1152, y=540, width=200, height=60),
            entrance_sec=0.0,
            exit_sec=5.0,
            style_name="NodeTimeline",
        ),
    ]

    svg_timeline = generate_svg_overlay(
        text_elements=timeline_texts,
        visual_family="chronological_timeline",
    )
    assert svg_timeline is not None
    assert "Timeline Spine" in svg_timeline
    assert "Timeline Node: t1" in svg_timeline
    assert "Stat Badge:" not in svg_timeline

    # Case B: Standalone single DATE in non-timeline beat -> routes to StatBadgeWidget
    standalone_date = [
        TextRenderElement(
            element_id="d1",
            text="1989",
            role="DATE",
            text_role="DATE",
            z_index=1,
            bounds_norm={"x": 0.4, "y": 0.4, "width": 0.2, "height": 0.1},
            bounds_px=PixelRect(x=768, y=432, width=180, height=60),
            entrance_sec=0.0,
            exit_sec=5.0,
            style_name="NodeLabel",
        )
    ]

    svg_badge = generate_svg_overlay(
        text_elements=standalone_date,
        visual_family="full_frame_cinematic",
    )
    assert svg_badge is not None
    assert "Stat Badge: DATE" in svg_badge
    assert "Timeline Spine" not in svg_badge


def test_svg_overlay_with_connectors_and_quotes():
    """Verify connectors and quote cards use Vox design tokens."""
    conns = [
        ConnectorRenderElement(
            connector_id="c1",
            source_node_id="src",
            target_node_id="tgt",
            relationship_type="CAUSES",
            connector_style_hint="solid",
            directed=True,
            start_px=(200.0, 500.0),
            end_px=(800.0, 500.0),
            color="#FFD100",
        )
    ]
    texts = [
        TextRenderElement(
            element_id="q1",
            text='"As far as I know, it takes effect immediately."',
            role="QUOTE",
            text_role="QUOTE",
            z_index=2,
            bounds_norm={"x": 0.2, "y": 0.7, "width": 0.6, "height": 0.15},
            bounds_px=PixelRect(x=384, y=756, width=600, height=100),
            entrance_sec=0.0,
            exit_sec=5.0,
            style_name="NodeQuote",
        )
    ]

    svg = generate_svg_overlay(
        connectors=conns,
        text_elements=texts,
        accent_color="#FFD100",
    )
    assert svg is not None
    assert '<polygon points=' in svg  # Directed arrowhead
    assert '#FFD100' in svg          # Accent gold bar
    assert 'card-drop-shadow' in svg

    # Validate well-formed XML
    ET.fromstring(svg)


def test_generalization_vox_codebase():
    """Verify no forbidden domain words are hardcoded in render/vox_theme.py or render/widgets/."""
    forbidden = ["berlin", "schabowski", "bornholmer"]
    render_dir = Path(__file__).resolve().parent.parent / "videotool" / "render"
    files_to_check = [
        render_dir / "vox_theme.py",
        render_dir / "widgets" / "timeline.py",
        render_dir / "widgets" / "stat_badge.py",
        render_dir / "widgets" / "__init__.py",
        render_dir / "svg_overlay.py",
    ]

    for fpath in files_to_check:
        if not fpath.exists():
            continue
        content = fpath.read_text(encoding="utf-8").lower()
        for word in forbidden:
            assert word not in content, f"Forbidden word '{word}' found in {fpath.name}"
