"""Unit tests for Vox Paper Collage Visual Engine (Phase A)."""
from __future__ import annotations

import xml.etree.ElementTree as ET

from videotool.render.vox_collage import (
    VoxCollageData,
    generate_brush_stroke_svg,
    generate_chapter_pill_svg,
    generate_gold_fact_box_svg,
    generate_quote_banner_svg,
    generate_tape_strip_svg,
    generate_torn_paper_path,
    generate_vox_collage_overlay_svg,
    highlight_keywords_in_quote,
)


def test_torn_paper_path_determinism():
    """Verify that identical seed produces identical torn-paper paths."""
    path1 = generate_torn_paper_path(width=720.0, height=1080.0, seed="beat_0001", segments=40)
    path2 = generate_torn_paper_path(width=720.0, height=1080.0, seed="beat_0001", segments=40)
    path3 = generate_torn_paper_path(width=720.0, height=1080.0, seed="beat_0002", segments=40)

    assert path1 == path2, "Torn paper path generation must be 100% deterministic for same seed"
    assert path1 != path3, "Different seeds must produce different organic jagged paths"
    assert path1.startswith("M 0 0 L 720.00 0")
    assert path1.endswith("L 0 1080.00 Z")


def test_brush_stroke_svg():
    """Verify procedural brush stroke SVG generation."""
    svg = generate_brush_stroke_svg(x=60.0, y=200.0, width=300.0, height=12.0, color="#E1B400", seed="test_brush")
    assert '<path d="M 60.0' in svg
    assert 'fill="#E1B400"' in svg
    assert 'opacity="0.92"' in svg


def test_tape_strip_svg():
    """Verify semi-transparent vintage tape strip with rotation."""
    svg = generate_tape_strip_svg(cx=1200.0, cy=150.0, width=80.0, height=24.0, angle_deg=-12.0)
    assert 'transform="rotate(-12.0 1200.0 150.0)"' in svg
    assert 'fill="#F8F6E6"' in svg
    assert 'fill-opacity="0.65"' in svg


def test_chapter_pill_svg():
    """Verify chapter pill badge rendering."""
    svg = generate_chapter_pill_svg(x=60.0, y=50.0, text="CHƯƠNG 1", accent_color="#E1B400")
    assert 'CHƯƠNG 1' in svg
    assert 'stroke="#E1B400"' in svg
    assert 'fill="#111111"' in svg
    assert 'rx="16.0"' in svg


def test_gold_fact_box_svg():
    """Verify framed gold milestone fact box."""
    svg = generate_gold_fact_box_svg(
        x=60.0,
        y=800.0,
        width=580.0,
        height=90.0,
        date_text="13/08/1961",
        title_text="BỨC TƯỜNG BERLIN",
        subtitle_text="CHÍNH THỨC ĐƯỢC XÂY DỰNG",
        accent_color="#E1B400",
    )
    assert "13/08/1961" in svg
    assert "BỨC TƯỜNG BERLIN" in svg
    assert "CHÍNH THỨC ĐƯỢC XÂY DỰNG" in svg
    assert 'stroke="#E1B400"' in svg
    assert 'fill="#121212"' in svg


def test_quote_banner_keyword_highlighting():
    """Verify keyword emphasis in quote banner (both AI and non-AI paths)."""
    quote = "Một bức tường không chỉ bằng bê tông và dây thép gai, mà còn bằng nỗi sợ hãi và sự chia rẽ."
    emphasis = ["nỗi sợ hãi", "sự chia rẽ"]

    highlighted = highlight_keywords_in_quote(quote, emphasis_keywords=emphasis, accent_color="#E1B400")
    assert '<tspan fill="#E1B400" font-weight="bold">nỗi sợ hãi</tspan>' in highlighted
    assert '<tspan fill="#E1B400" font-weight="bold">sự chia rẽ</tspan>' in highlighted
    assert '<tspan fill="#E7E0D2">Một bức tường không chỉ bằng bê tông và dây thép gai, mà còn bằng </tspan>' in highlighted

    # Non-AI / fallback path (no emphasis keywords)
    fallback = highlight_keywords_in_quote(quote, emphasis_keywords=None)
    assert '<tspan fill="#E7E0D2">' in fallback
    assert 'Một bức tường không chỉ bằng bê tông' in fallback

    # Banner SVG wrapper
    banner_svg = generate_quote_banner_svg(
        x=400.0, y=950.0, width=900.0, height=70.0,
        text=quote, emphasis_keywords=emphasis, accent_color="#E1B400"
    )
    assert '<rect' in banner_svg
    assert 'filter="url(#card-drop-shadow)"' in banner_svg
    assert 'nỗi sợ hãi' in banner_svg


def test_full_vox_collage_svg_generation():
    """Verify full 1080p Vox Paper Collage SVG overlay assembly."""
    collage = VoxCollageData(
        beat_id="beat_0003",
        chapter_text="CHƯƠNG 1",
        headline_lines=["BỐI CẢNH RA ĐỜI", "BỨC TƯỜNG BERLIN"],
        body_paragraph="Sau Thế chiến II, nước Đức bị chia cắt thành Đông Đức và Tây Đức. Hàng triệu người Đông Đức tìm cách vượt sang Tây Đức.",
        date_milestone="13/08/1961",
        date_title="BỨC TƯỜNG BERLIN",
        date_subtitle="CHÍNH THỨC ĐƯỢC XÂY DỰNG",
        quote_text="Một bức tường không chỉ bằng bê tông, mà còn bằng nỗi sợ hãi.",
        quote_emphasis=["nỗi sợ hãi"],
        insets=[{"x": 1240.0, "y": 60.0, "w": 620.0, "h": 380.0, "taped": True}],
        accent_color="#E1B400",
    )

    svg_content = generate_vox_collage_overlay_svg(collage, canvas_w=1920, canvas_h=1080)
    assert svg_content.startswith('<svg xmlns="http://www.w3.org/2000/svg" width="1920" height="1080"')
    assert "CHƯƠNG 1" in svg_content
    assert "BỐI CẢNH RA ĐỜI" in svg_content
    assert "BỨC TƯỜNG BERLIN" in svg_content
    assert "13/08/1961" in svg_content
    assert "nỗi sợ hãi" in svg_content
    assert "transform=\"rotate(" in svg_content  # Tape strips on inset
    assert "</svg>" in svg_content

    # Ensure valid XML syntax parseable by SVG decoders
    root = ET.fromstring(svg_content)
    assert root.tag.endswith("svg")
    assert root.attrib["width"] == "1920"
    assert root.attrib["height"] == "1080"
