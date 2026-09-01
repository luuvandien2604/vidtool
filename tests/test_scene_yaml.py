"""Tests for Scene YAML Schema, Archival Resolver, Manifest, and Modular Collage Engine."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
import pytest

from videotool.domain.scene_schema import SceneSpec
from videotool.editorial.media.archival_resolver import ArchivalResolver
from videotool.render.collage import (
    render_paper_panel_svg,
    render_tape_strip_svg,
    render_fact_card_svg,
    render_quote_banner_svg,
    render_map_card_svg,
    render_taped_media_card_svg,
    highlight_keywords_in_quote,
    VoxEditorialSceneConfig,
    render_vox_editorial_scene_svg,
)
from videotool.render.scene_renderer import SceneRenderer


SAMPLE_DICT = {
    "version": "2.0",
    "project": {
        "id": "test_scene_project",
        "title": "Bức tường Berlin",
        "language": "vi",
        "resolution": {"width": 1920, "height": 1080},
        "duration_seconds": 1.0,
    },
    "scene": {
        "title": "Đêm Berlin bị phong tỏa",
        "historical_date": "1961-08-13",
        "narration": {
            "text": "Sau Thế chiến II, nước Đức bị chia cắt thành Đông Đức và Tây Đức.",
        },
    },
    "style": {
        "palette": {
            "paper": "#E7E0D2",
            "charcoal": "#161616",
            "yellow": "#E1B400",
            "red": "#8C3932",
            "blue": "#33495A",
        },
    },
    "license_policy": {
        "license_url": "https://creativecommons.org/licenses/by-sa/3.0/de/deed.en",
    },
    "assets": [
        {
            "id": "test_hero",
            "type": "archival_photo",
            "role": "primary_visual",
            "source": {
                "title": "Bundesarchiv Bild 173-1321",
                "page_url": "https://commons.wikimedia.org/wiki/File:Bundesarchiv_Bild_173-1321,_Berlin,_Mauerbau.jpg",
            },
            "license": {
                "name": "CC BY-SA 3.0 DE",
                "url": "https://creativecommons.org/licenses/by-sa/3.0/de/deed.en",
                "attribution": "Bundesarchiv, Bild 173-1321 / CC-BY-SA 3.0",
            },
        },
    ],
    "layout": {
        "main_visual": {"x": 34, "y": 0, "width": 58, "height": 78},
    },
    "graphics": {
        "chapter_label": {"text": "CHƯƠNG 1"},
        "headline": {"text": "BỐI CẢNH RA ĐỜI\nBỨC TƯỜNG BERLIN"},
        "date_card": {
            "date": "13/08/1961",
            "title": "BỨC TƯỜNG BERLIN",
            "subtitle": "CHÍNH THỨC ĐƯỢC XÂY DỰNG",
        },
        "quote": {
            "text": "Một bức tường không chỉ bằng bê tông, mà bằng nỗi sợ hãi.",
            "emphasis": ["nỗi sợ hãi"],
        },
    },
    "timeline": [
        {"time": "0.0-1.0", "action": "Fade from black."},
    ],
    "credits": [
        "Bundesarchiv / CC-BY-SA 3.0 DE",
    ],
}


def test_scene_schema_parsing():
    data = SAMPLE_DICT
    spec = SceneSpec.from_dict(data)
    assert spec.version == "2.0"
    assert spec.project["id"] == "test_scene_project"
    assert len(spec.assets) == 1
    assert spec.assets[0].id == "test_hero"
    assert spec.graphics.chapter_label["text"] == "CHƯƠNG 1"
    assert spec.graphics.date_card.date == "13/08/1961"
    assert "nỗi sợ hãi" in spec.graphics.quote.emphasis


def test_modular_collage_primitives():
    defs, paper = render_paper_panel_svg(width=720, height=1080)
    assert "url(#paperGrain)" in paper
    assert "paperShadow" in defs

    tape = render_tape_strip_svg(cx=100, cy=100, width=120, height=30, angle_deg=-15)
    assert "<polygon" in tape
    assert "points=" in tape

    fact = render_fact_card_svg(x=50, y=500, date_text="13/08/1961", title_text="TITLE", subtitle_text="SUB")
    assert "13/08/1961" in fact
    assert "#E1B400" in fact

    quote = render_quote_banner_svg(x=400, y=900, text="Một câu nói nỗi sợ hãi", emphasis_keywords=["nỗi sợ hãi"])
    assert 'fill="#E1B400"' in quote
    assert "nỗi sợ hãi" in quote

    map_card = render_map_card_svg(x=1400, y=50, width=380, height=300, pin_label="BERLIN")
    assert "TÂY ĐỨC" in map_card
    assert "ĐÔNG ĐỨC" in map_card
    assert "BERLIN" in map_card


def test_vietnamese_diacritics_in_quote():
    raw = "BỐI CẢNH ĐỘC LẬP CHIA CẮT nỗi sợ hãi và sự chia rẽ"
    highlighted = highlight_keywords_in_quote(raw, ["nỗi sợ hãi", "sự chia rẽ"], accent_color="#E1B400")
    assert '<tspan fill="#E1B400" font-weight="900">nỗi sợ hãi</tspan>' in highlighted
    assert '<tspan fill="#E1B400" font-weight="900">sự chia rẽ</tspan>' in highlighted


def test_archival_resolver_manifest_generation():
    with tempfile.TemporaryDirectory() as tmpdir:
        data = SAMPLE_DICT
        spec = SceneSpec.from_dict(data)
        resolver = ArchivalResolver(tmpdir)
        manifest_path = resolver.resolve_scene_assets(spec, "test_proj")
        assert manifest_path.exists()
        manifest_content = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert manifest_content["version"] == "2.0"
        assert len(manifest_content["assets"]) >= 1
        record = manifest_content["assets"][0]
        assert record["id"] == "test_hero"
        assert record["license_name"] == "CC BY-SA 3.0 DE"
        assert "sha256_original" in record
