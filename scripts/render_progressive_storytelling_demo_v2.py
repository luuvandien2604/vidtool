"""Master Cut Progressive Storytelling Motion Graphic Engine with Dynamic Word-Highlight Subtitles.

Enhancements:
1. Authentic 1961 Archival Photo (November 1961 construction scene with cranes and soldiers).
2. Dynamic Word-Synchronized Subtitle Pill (Karaoke Gold Highlight on active spoken word).
3. Punchy Editorial Kinetic Callout Cards (Replaces long paragraph copy with high-impact data).
4. High-detail Vintage Cartography Card (Migration route arrow, Berlin pulsing marker, tape strips).
5. Weathered German Historical Warning Sign (Enamel grunge texture, drop shadow).
6. Multi-plane physical choreography synchronized to exact ms Azure Vietnamese speech.
"""
from __future__ import annotations

import math
import os
import subprocess
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from videotool.render.collage.scene import generate_brush_stroke_svg
from videotool.render.collage.paper_panel import render_paper_panel_svg
from videotool.render.collage.fact_card import render_fact_card_svg
from videotool.render.collage.quote_banner import render_quote_banner_svg


def ease_out_cubic(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return 1.0 - math.pow(1.0 - t, 3)


def ease_out_back(t: float, s: float = 1.70158) -> float:
    t = max(0.0, min(1.0, t))
    return 1.0 + (s + 1.0) * math.pow(t - 1.0, 3) + s * math.pow(t - 1.0, 2)


def ease_in_out_sine(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return -(math.cos(math.pi * t) - 1.0) / 2.0


def render_svg_to_png(svg_str: str, out_png: Path, width: int = 1920, height: int = 1080) -> Image.Image:
    tmp_svg = out_png.with_suffix(".tmp.svg")
    tmp_svg.write_text(svg_str, encoding="utf-8")
    cmd = [
        "ffmpeg", "-y",
        "-i", str(tmp_svg),
        "-vf", f"scale={width}:{height}",
        str(out_png),
    ]
    subprocess.run(cmd, capture_output=True, check=True)
    if tmp_svg.exists():
        tmp_svg.unlink()
    return Image.open(out_png).convert("RGBA")


# Timing data extracted from Azure Neural Voice
# 79 words across 4 sentences
WORD_TIMINGS = [
    (0.050, 0.337, "Sau"), (0.338, 0.513, "Thế"), (0.513, 0.787, "chiến"), (0.787, 1.262, "II,"),
    (1.438, 1.713, "nước"), (1.713, 1.924, "Đức"), (1.925, 2.125, "bị"), (2.125, 2.362, "chia"),
    (2.362, 2.550, "cắt"), (2.550, 2.762, "thành"), (2.763, 2.963, "Đông"), (2.963, 3.137, "Đức"),
    (3.138, 3.363, "và"), (3.363, 3.587, "Tây"), (3.587, 3.787, "Đức."),
    
    (4.625, 4.900, "Hàng"), (4.900, 5.100, "triệu"), (5.100, 5.300, "người"), (5.300, 5.525, "Đông"),
    (5.525, 5.675, "Đức"), (5.675, 5.925, "tìm"), (5.925, 6.112, "cách"), (6.112, 6.300, "vượt"),
    (6.300, 6.525, "biên"), (6.525, 6.812, "sang"), (6.812, 7.000, "Tây"), (7.000, 7.188, "Đức"),
    (7.188, 7.338, "để"), (7.338, 7.601, "tìm"), (7.601, 7.812, "tự"), (7.812, 8.125, "do."),
    
    (8.963, 9.188, "Để"), (9.188, 9.438, "ngăn"), (9.438, 9.626, "làn"), (9.626, 9.850, "sóng"),
    (9.850, 10.012, "tháo"), (10.012, 10.362, "chạy,"), (10.512, 10.700, "vào"), (10.700, 11.142, "ngày"),
    (11.252, 11.473, "13"), (11.583, 12.135, "tháng"), (12.246, 12.356, "8"), (12.467, 12.798, "năm"),
    (12.908, 13.350, "1961,"),
    
    (13.562, 13.800, "chính"), (13.800, 14.025, "quyền"), (14.025, 14.213, "Đông"), (14.213, 14.363, "Đức"),
    (14.363, 14.550, "quyết"), (14.550, 14.763, "định"), (14.763, 15.037, "dựng"), (15.037, 15.262, "lên"),
    (15.262, 15.450, "bức"), (15.450, 15.712, "tường"), (15.713, 15.938, "ngăn"), (15.938, 16.151, "cách"),
    (16.151, 16.637, "Berlin."),
    
    (17.475, 17.838, "Một"), (17.838, 18.037, "bức"), (18.038, 18.313, "tường"), (18.313, 18.537, "không"),
    (18.538, 18.688, "chỉ"), (18.688, 18.900, "bằng"), (18.900, 19.062, "bê"), (19.062, 19.350, "tông"),
    (19.350, 19.475, "và"), (19.475, 19.663, "dây"), (19.663, 19.851, "thép"), (19.851, 20.200, "gai,"),
    (20.375, 20.587, "mà"), (20.587, 20.799, "còn"), (20.800, 20.963, "bằng"), (20.963, 21.137, "nỗi"),
    (21.137, 21.375, "sợ"), (21.375, 21.712, "hãi"), (21.712, 21.862, "và"), (21.863, 22.050, "sự"),
    (22.050, 22.288, "chia"), (22.288, 23.475, "rẽ.")
]

SUBTITLE_CHUNKS = [
    # (start_t, end_t, [(word_text, word_start, word_end)])
    (0.00, 4.20, WORD_TIMINGS[0:15]),
    (4.30, 8.50, WORD_TIMINGS[15:31]),
    (8.60, 13.40, WORD_TIMINGS[31:44]),
    (13.45, 17.00, WORD_TIMINGS[44:57]),
    (17.20, 24.50, WORD_TIMINGS[57:79]),
]


def build_master_layers(work_dir: Path) -> dict[str, Path]:
    """Generate all refined vector & collage layers."""
    work_dir.mkdir(parents=True, exist_ok=True)
    layer_paths = {}

    # 1. Left Torn-Paper Panel
    defs_xml, paper_xml = render_paper_panel_svg(
        width=740.0, height=1080, fill_color="#141518", seed=42
    )
    panel_svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="1920" height="1080" viewBox="0 0 1920 1080">
      <defs>{defs_xml}</defs>
      {paper_xml}
    </svg>"""
    p_panel = work_dir / "layer_panel.png"
    render_svg_to_png(panel_svg, p_panel)
    layer_paths["panel"] = p_panel

    # 2. Chapter Badge ("CHƯƠNG 1")
    chap_svg = """<svg xmlns="http://www.w3.org/2000/svg" width="1920" height="1080" viewBox="0 0 1920 1080">
      <g transform="translate(60, 68)">
        <rect x="0" y="0" width="136" height="34" rx="17" fill="#0A0B0D" stroke="#E1B400" stroke-width="2.0" />
        <text x="68" y="23" text-anchor="middle" font-family="'DejaVu Sans', sans-serif" font-size="14" font-weight="900" fill="#F0ECE1" letter-spacing="1.8">CHƯƠNG 1</text>
      </g>
    </svg>"""
    p_chap = work_dir / "layer_chapter.png"
    render_svg_to_png(chap_svg, p_chap)
    layer_paths["chapter"] = p_chap

    # 3. Headline Text
    head_svg = """<svg xmlns="http://www.w3.org/2000/svg" width="1920" height="1080" viewBox="0 0 1920 1080">
      <text x="60" y="180" font-family="'DejaVu Sans', 'Liberation Sans', sans-serif" font-size="58" font-weight="900" fill="#FFFFFF" letter-spacing="1.2">BỐI CẢNH RA ĐỜI</text>
      <text x="60" y="252" font-family="'DejaVu Sans', 'Liberation Sans', sans-serif" font-size="58" font-weight="900" fill="#FFFFFF" letter-spacing="1.2">BỨC TƯỜNG BERLIN</text>
    </svg>"""
    p_head = work_dir / "layer_headline.png"
    render_svg_to_png(head_svg, p_head)
    layer_paths["headline"] = p_head

    # 4. Brush Stroke under headline
    brush_d = generate_brush_stroke_svg(x=58.0, y=190.0, width=540.0, height=20.0, color="#E1B400", seed=42)
    brush_svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="1920" height="1080" viewBox="0 0 1920 1080">
      {brush_d}
    </svg>"""
    p_brush = work_dir / "layer_brush.png"
    render_svg_to_png(brush_svg, p_brush)
    layer_paths["brush"] = p_brush

    # 5. Editorial Kinetic Callout Block 1 (Replaces small 6-line paragraph)
    callout1_svg = """<svg xmlns="http://www.w3.org/2000/svg" width="1920" height="1080" viewBox="0 0 1920 1080">
      <g transform="translate(60, 320)">
        <!-- Pill tag -->
        <rect x="0" y="0" width="220" height="26" rx="4" fill="#E1B400" fill-opacity="0.18" stroke="#E1B400" stroke-width="1.2" />
        <text x="110" y="18" text-anchor="middle" font-family="'DejaVu Sans', sans-serif" font-size="12" font-weight="900" fill="#E1B400" letter-spacing="1.5">CHIẾN TRANH LẠNH / 1961</text>
        <!-- Big Stat Line -->
        <text x="0" y="70" font-family="'DejaVu Sans', sans-serif" font-size="34" font-weight="900" fill="#FFFFFF" letter-spacing="0.5">2.7 TRIỆU NGƯỜI</text>
        <text x="0" y="105" font-family="'DejaVu Sans', sans-serif" font-size="20" font-weight="700" fill="#E1B400" letter-spacing="0.8">TÌM CÁCH VƯỢT BIÊN SANG TÂY ĐỨC</text>
      </g>
    </svg>"""
    p_callout1 = work_dir / "layer_callout1.png"
    render_svg_to_png(callout1_svg, p_callout1)
    layer_paths["callout1"] = p_callout1

    # 6. Editorial Kinetic Callout Block 2 (Appears at t: 8.9s)
    callout2_svg = """<svg xmlns="http://www.w3.org/2000/svg" width="1920" height="1080" viewBox="0 0 1920 1080">
      <g transform="translate(60, 470)">
        <rect x="0" y="0" width="5" height="54" fill="#E1B400" />
        <text x="18" y="24" font-family="'DejaVu Sans', sans-serif" font-size="20" font-weight="800" fill="#FFFFFF">NGĂN CHẶN LÀN SÓNG THÁO CHẠY</text>
        <text x="18" y="50" font-family="'DejaVu Sans', sans-serif" font-size="16" font-weight="500" fill="#A8A398">Lệnh phong tỏa toàn diện biên giới Berlin</text>
      </g>
    </svg>"""
    p_callout2 = work_dir / "layer_callout2.png"
    render_svg_to_png(callout2_svg, p_callout2)
    layer_paths["callout2"] = p_callout2

    # 7. Gold Fact Card (13/08/1961)
    fact_svg = render_fact_card_svg(
        x=60.0, y=710.0, width=490.0, height=130.0,
        date_text="13/08/1961",
        title_text="BỨC TƯỜNG BERLIN",
        subtitle_text="CHÍNH THỨC ĐƯỢC XÂY DỰNG",
        accent_color="#E1B400"
    )
    full_fact_svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="1920" height="1080" viewBox="0 0 1920 1080">
      <defs>
        <filter id="fact-drop-shadow"><feDropShadow dx="6" dy="10" stdDeviation="12" flood-color="#000000" flood-opacity="0.75"/></filter>
      </defs>
      {fact_svg}
    </svg>"""
    p_fact = work_dir / "layer_fact.png"
    render_svg_to_png(full_fact_svg, p_fact)
    layer_paths["fact"] = p_fact

    # 8. High-Detail Cartography Card (Top-Right)
    map_svg = """<svg xmlns="http://www.w3.org/2000/svg" width="1920" height="1080" viewBox="0 0 1920 1080">
      <defs>
        <filter id="mapShadow"><feDropShadow dx="8" dy="14" stdDeviation="14" flood-color="#000000" flood-opacity="0.75"/></filter>
        <pattern id="grid" width="20" height="20" patternUnits="userSpaceOnUse">
          <path d="M 20 0 L 0 0 0 20" fill="none" stroke="#FFFFFF" stroke-opacity="0.08" stroke-width="0.8"/>
        </pattern>
      </defs>
      <g transform="translate(1420, 60) rotate(-2)" filter="url(#mapShadow)">
        <!-- Card Base -->
        <rect x="0" y="0" width="440" height="340" rx="6" fill="#181A1F" stroke="#3A3D45" stroke-width="2" />
        <rect x="0" y="0" width="440" height="340" fill="url(#grid)" />
        
        <!-- Header -->
        <text x="20" y="32" font-family="'DejaVu Sans', sans-serif" font-size="14" font-weight="900" fill="#E1B400" letter-spacing="1.5">BẢN ĐỒ PHÂN CHIA NƯỚC ĐỨC</text>
        <line x1="20" y1="42" x2="420" y2="42" stroke="#3A3D45" stroke-width="1" />

        <!-- West Germany Polygon (Blue) -->
        <polygon points="40,60 210,60 210,300 40,280" fill="#24384A" stroke="#466A8A" stroke-width="2" />
        <text x="125" y="170" text-anchor="middle" font-family="'DejaVu Sans', sans-serif" font-size="18" font-weight="900" fill="#A8D0F0" letter-spacing="1">TÂY ĐỨC</text>
        <text x="125" y="195" text-anchor="middle" font-family="'DejaVu Sans', sans-serif" font-size="12" font-weight="700" fill="#6B95B8">(Tư Bản)</text>

        <!-- East Germany Polygon (Red) -->
        <polygon points="215,60 400,75 400,290 215,300" fill="#6E231D" stroke="#A83C32" stroke-width="2" />
        <text x="310" y="170" text-anchor="middle" font-family="'DejaVu Sans', sans-serif" font-size="18" font-weight="900" fill="#F5A89E" letter-spacing="1">ĐÔNG ĐỨC</text>
        <text x="310" y="195" text-anchor="middle" font-family="'DejaVu Sans', sans-serif" font-size="12" font-weight="700" fill="#BD6258">(Cộng Sản)</text>

        <!-- Division Border line -->
        <line x1="212" y1="58" x2="212" y2="302" stroke="#E1B400" stroke-width="3" stroke-dasharray="6,4" />

        <!-- Berlin Marker -->
        <circle cx="285" cy="115" r="9" fill="#E1B400" stroke="#FFFFFF" stroke-width="2" />
        <circle cx="285" cy="115" r="16" fill="none" stroke="#E1B400" stroke-width="1.5" stroke-opacity="0.8" stroke-dasharray="3,3" />
        <text x="302" y="120" font-family="'DejaVu Sans', sans-serif" font-size="14" font-weight="900" fill="#FFFFFF">BERLIN</text>

        <!-- Migration escape route arrow -->
        <path d="M 275 125 Q 230 150 170 140" fill="none" stroke="#FFFFFF" stroke-width="3" stroke-dasharray="5,4" />
        <polygon points="165,140 176,133 176,147" fill="#FFFFFF" />

        <!-- Masking Tape Strips -->
        <polygon points="-15,-8 45,-14 38,18 -22,24" fill="#F4F0DC" fill-opacity="0.85" />
        <polygon points="390,-12 450,-5 442,26 382,19" fill="#F4F0DC" fill-opacity="0.85" />
      </g>
    </svg>"""
    p_map = work_dir / "layer_map.png"
    render_svg_to_png(map_svg, p_map)
    layer_paths["map"] = p_map

    # 9. Authentic German Historical Warning Sign (Bottom-Right)
    sign_svg = """<svg xmlns="http://www.w3.org/2000/svg" width="1920" height="1080" viewBox="0 0 1920 1080">
      <defs>
        <filter id="signShadow"><feDropShadow dx="8" dy="12" stdDeviation="14" flood-color="#000000" flood-opacity="0.8"/></filter>
      </defs>
      <g transform="translate(1450, 680) rotate(3)" filter="url(#signShadow)">
        <!-- Enamel Plate with metal rim -->
        <rect x="0" y="0" width="400" height="250" rx="6" fill="#EAE5D8" stroke="#524E48" stroke-width="4" />
        <rect x="8" y="8" width="384" height="234" rx="4" fill="none" stroke="#8C8476" stroke-width="1.5" />
        
        <!-- Screws at corners -->
        <circle cx="16" cy="16" r="4" fill="#403C36" />
        <circle cx="384" cy="16" r="4" fill="#403C36" />
        <circle cx="16" cy="234" r="4" fill="#403C36" />
        <circle cx="384" cy="234" r="4" fill="#403C36" />

        <!-- German Warning text -->
        <text x="200" y="60" text-anchor="middle" font-family="'DejaVu Sans', sans-serif" font-size="38" font-weight="900" fill="#B81D13" letter-spacing="1.5">Achtung !</text>
        <text x="200" y="112" text-anchor="middle" font-family="'DejaVu Sans', sans-serif" font-size="22" font-weight="700" fill="#161618">Sie verlassen jetzt</text>
        <text x="200" y="156" text-anchor="middle" font-family="'DejaVu Sans', sans-serif" font-size="28" font-weight="900" fill="#161618" letter-spacing="1">West-Berlin</text>

        <!-- Subtext in 3 languages -->
        <text x="200" y="200" text-anchor="middle" font-family="'DejaVu Sans', sans-serif" font-size="13" font-weight="600" fill="#5E5950">Zone Border Checkpoint / 1961</text>

        <!-- Tape at corners -->
        <polygon points="12,-10 60,-16 52,18 4,24" fill="#F4F0DC" fill-opacity="0.8" />
        <polygon points="340,-14 390,-8 382,24 332,18" fill="#F4F0DC" fill-opacity="0.8" />
      </g>
    </svg>"""
    p_sign = work_dir / "layer_sign.png"
    render_svg_to_png(sign_svg, p_sign)
    layer_paths["sign"] = p_sign

    # 10. Refined Quote Banner (with torn paper borders)
    quote_svg = """<svg xmlns="http://www.w3.org/2000/svg" width="1920" height="1080" viewBox="0 0 1920 1080">
      <defs>
        <filter id="quoteShadow"><feDropShadow dx="0" dy="8" stdDeviation="14" flood-color="#000000" flood-opacity="0.85"/></filter>
      </defs>
      <g transform="translate(240, 890)" filter="url(#quoteShadow)">
        <rect x="0" y="0" width="1440" height="74" rx="4" fill="#0C0D10" stroke="#E1B400" stroke-width="1.5" />
        <text x="720" y="46" text-anchor="middle" font-family="'DejaVu Sans', sans-serif" font-size="22" font-weight="700" fill="#E8E5DC">
          " Một bức tường không chỉ bằng bê tông và dây thép gai, mà còn bằng <tspan fill="#E1B400" font-weight="900">nỗi sợ hãi</tspan> và <tspan fill="#E1B400" font-weight="900">sự chia rẽ</tspan>. "
        </text>
      </g>
    </svg>"""
    p_quote = work_dir / "layer_quote.png"
    render_svg_to_png(quote_svg, p_quote)
    layer_paths["quote"] = p_quote

    return layer_paths


def draw_dynamic_subtitles(
    frame: Image.Image,
    current_time: float,
    font: ImageFont.FreeTypeFont,
) -> None:
    """Render animated active-word highlighted subtitle pill at the bottom."""
    # Find active chunk
    active_chunk = None
    for chunk in SUBTITLE_CHUNKS:
        start_t, end_t, words = chunk
        if start_t <= current_time <= end_t:
            active_chunk = chunk
            break

    if not active_chunk:
        return

    _, _, words_data = active_chunk
    if not words_data:
        return

    # Calculate total width of sentence
    words_list = [w[2] for w in words_data]
    total_w = sum(font.getbbox(w + " ")[2] for w in words_list)
    start_x = int((1920 - total_w) / 2)
    sub_y = 990

    # Draw semi-transparent background pill
    draw = ImageDraw.Draw(frame)
    pad_x, pad_y = 28, 10
    pill_rect = [
        start_x - pad_x, sub_y - pad_y,
        start_x + total_w + pad_x, sub_y + 36 + pad_y
    ]
    draw.rounded_rectangle(
        pill_rect,
        radius=14,
        fill=(10, 11, 14, 220),
        outline=(225, 180, 0, 150),
        width=1,
    )

    # Draw each word with active timestamp highlight
    curr_x = start_x
    for w_start, w_end, w_text in words_data:
        w_str = w_text + " "
        is_active = (w_start <= current_time <= w_end + 0.08)
        
        if is_active:
            fill_color = (255, 215, 0, 255) # Bright Gold
            # Draw slight text shadow
            draw.text((curr_x + 1, sub_y + 1), w_str, font=font, fill=(0, 0, 0, 200))
        else:
            fill_color = (245, 245, 245, 255) # Pure White
            
        draw.text((curr_x, sub_y), w_str, font=font, fill=fill_color)
        curr_x += font.getbbox(w_str)[2]


def render_master_cut_frames(
    hero_image_path: Path,
    layers: dict[str, Path],
    output_frames_dir: Path,
    duration_sec: float = 24.5,
    fps: int = 30,
) -> int:
    """Render all 735 master frames with complete typography and subtitle engine."""
    output_frames_dir.mkdir(parents=True, exist_ok=True)
    total_frames = int(duration_sec * fps)

    hero_base = Image.open(hero_image_path).convert("RGB")
    hero_w, hero_h = hero_base.size

    img_layers = {k: Image.open(p).convert("RGBA") for k, p in layers.items()}
    brush_full = img_layers["brush"]

    try:
        sub_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
    except Exception:
        sub_font = ImageFont.load_default()

    print(f"🎬 Rendering {total_frames} Master Cut frames ({duration_sec:.1f}s @ {fps}fps)...")

    for f_idx in range(total_frames):
        t = f_idx / fps
        prog = f_idx / max(1, total_frames - 1)

        # Base Frame Canvas (#121216)
        frame = Image.new("RGBA", (1920, 1080), (14, 15, 18, 255))

        # -------------------------------------------------------------
        # 1. 1961 Archival Hero Photo: Ken Burns Slow Push & Drift
        # -------------------------------------------------------------
        kb_scale = 1.00 + 0.10 * ease_in_out_sine(prog)
        kb_pan_x = -35.0 * prog
        kb_pan_y = 12.0 * prog

        crop_w = int(hero_w / kb_scale)
        crop_h = int(hero_h / kb_scale)
        crop_x = max(0, min(hero_w - crop_w, int((hero_w - crop_w) / 2.0 + kb_pan_x)))
        crop_y = max(0, min(hero_h - crop_h, int((hero_h - crop_h) / 2.0 + kb_pan_y)))

        cropped_hero = hero_base.crop((crop_x, crop_y, crop_x + crop_w, crop_y + crop_h))
        scaled_hero = cropped_hero.resize((1920, 1080), Image.Resampling.BILINEAR)
        frame.paste(scaled_hero, (0, 0))

        # -------------------------------------------------------------
        # 2. Left Torn Paper Panel: Slide-in with Settle (t: 0.05 -> 0.70s)
        # -------------------------------------------------------------
        if t >= 0.05:
            panel_t = min(1.0, (t - 0.05) / 0.65)
            panel_offset_x = int(-220.0 * (1.0 - ease_out_back(panel_t, 1.1)))
            panel_img = img_layers["panel"]
            if panel_offset_x != 0:
                p_shifted = Image.new("RGBA", (1920, 1080), (0, 0, 0, 0))
                p_shifted.paste(panel_img, (panel_offset_x, 0))
                frame.alpha_composite(p_shifted)
            else:
                frame.alpha_composite(panel_img)

        # -------------------------------------------------------------
        # 3. Chapter Badge ('CHƯƠNG 1'): Pop & Bounce (t: 0.35 -> 0.75s)
        # -------------------------------------------------------------
        if t >= 0.35:
            chap_t = min(1.0, (t - 0.35) / 0.40)
            chap_scale = ease_out_back(chap_t, 2.0)
            if chap_scale > 0.05:
                frame.alpha_composite(img_layers["chapter"])

        # -------------------------------------------------------------
        # 4. Headline Text & Yellow Brush Swipe (t: 0.60 -> 1.60s)
        # -------------------------------------------------------------
        if t >= 0.60:
            head_t = min(1.0, (t - 0.60) / 0.50)
            head_alpha = ease_out_cubic(head_t)
            head_img = img_layers["headline"]
            if head_alpha < 0.99:
                h_faded = head_img.copy()
                arr = np.array(h_faded)
                arr[..., 3] = (arr[..., 3] * head_alpha).astype(np.uint8)
                frame.alpha_composite(Image.fromarray(arr))
            else:
                frame.alpha_composite(head_img)

        if t >= 0.90:
            brush_t = min(1.0, (t - 0.90) / 0.75)
            brush_prog = ease_out_cubic(brush_t)
            wipe_x = int(58 + (620 - 58) * brush_prog)
            if wipe_x > 60:
                b_crop = brush_full.crop((0, 0, wipe_x, 1080))
                b_frame = Image.new("RGBA", (1920, 1080), (0, 0, 0, 0))
                b_frame.paste(b_crop, (0, 0))
                frame.alpha_composite(b_frame)

        # -------------------------------------------------------------
        # 5. Punchy Callout Block 1: '2.7 TRIỆU NGƯỜI' (t: 1.40 -> end)
        # -------------------------------------------------------------
        if t >= 1.40:
            c1_t = min(1.0, (t - 1.40) / 0.60)
            c1_alpha = ease_out_cubic(c1_t)
            c1_offset_y = int(16.0 * (1.0 - ease_out_back(c1_t, 1.2)))
            c1_img = img_layers["callout1"]
            if c1_alpha < 0.99 or c1_offset_y > 0:
                arr = np.array(c1_img)
                arr[..., 3] = (arr[..., 3] * c1_alpha).astype(np.uint8)
                f_temp = Image.fromarray(arr)
                f_shifted = Image.new("RGBA", (1920, 1080), (0, 0, 0, 0))
                f_shifted.paste(f_temp, (0, -c1_offset_y))
                frame.alpha_composite(f_shifted)
            else:
                frame.alpha_composite(c1_img)

        # -------------------------------------------------------------
        # 6. Top-Right Taped Cartography Map Card (t: 2.75 -> end)
        # -------------------------------------------------------------
        if t >= 2.75:
            map_t = min(1.0, (t - 2.75) / 0.70)
            map_bounce = ease_out_back(map_t, 1.6)
            map_offset_y = int(-140.0 * (1.0 - map_bounce))
            map_img = img_layers["map"]

            drift_y = int(3.0 * math.sin(t * 1.8))
            total_map_y = map_offset_y + drift_y

            m_shifted = Image.new("RGBA", (1920, 1080), (0, 0, 0, 0))
            m_shifted.paste(map_img, (0, total_map_y))
            frame.alpha_composite(m_shifted)

        # -------------------------------------------------------------
        # 7. Callout Block 2: 'NGĂN CHẶN LÀN SÓNG THÁO CHẠY' (t: 8.90 -> end)
        # -------------------------------------------------------------
        if t >= 8.90:
            c2_t = min(1.0, (t - 8.90) / 0.60)
            c2_alpha = ease_out_cubic(c2_t)
            c2_offset_y = int(14.0 * (1.0 - ease_out_cubic(c2_t)))
            c2_img = img_layers["callout2"]
            if c2_alpha < 0.99 or c2_offset_y > 0:
                arr = np.array(c2_img)
                arr[..., 3] = (arr[..., 3] * c2_alpha).astype(np.uint8)
                f_temp = Image.fromarray(arr)
                f_shifted = Image.new("RGBA", (1920, 1080), (0, 0, 0, 0))
                f_shifted.paste(f_temp, (0, -c2_offset_y))
                frame.alpha_composite(f_shifted)
            else:
                frame.alpha_composite(c2_img)

        # -------------------------------------------------------------
        # 8. Gold Milestone Fact Card ('13/08/1961') (t: 10.70 -> end)
        # -------------------------------------------------------------
        if t >= 10.70:
            fact_t = min(1.0, (t - 10.70) / 0.75)
            fact_offset_y = int(75.0 * (1.0 - ease_out_back(fact_t, 1.4)))
            fact_alpha = ease_out_cubic(fact_t)
            fact_img = img_layers["fact"]

            if fact_alpha < 0.99 or fact_offset_y > 0:
                arr = np.array(fact_img)
                arr[..., 3] = (arr[..., 3] * fact_alpha).astype(np.uint8)
                f_temp = Image.fromarray(arr)
                f_shifted = Image.new("RGBA", (1920, 1080), (0, 0, 0, 0))
                f_shifted.paste(f_temp, (0, fact_offset_y))
                frame.alpha_composite(f_shifted)
            else:
                frame.alpha_composite(fact_img)

        # -------------------------------------------------------------
        # 9. Enamel Warning Sign ('Achtung!') (t: 15.40 -> end)
        # -------------------------------------------------------------
        if t >= 15.40:
            sign_t = min(1.0, (t - 15.40) / 0.65)
            sign_scale = ease_out_back(sign_t, 1.7)
            sign_offset_y = int(45.0 * (1.0 - sign_scale))
            sign_alpha = ease_out_cubic(sign_t)
            sign_img = img_layers["sign"]

            drift_sign_y = int(2.5 * math.sin(t * 1.5 + 1.0))
            total_sign_y = sign_offset_y + drift_sign_y

            arr = np.array(sign_img)
            if sign_alpha < 0.99:
                arr[..., 3] = (arr[..., 3] * sign_alpha).astype(np.uint8)
            f_temp = Image.fromarray(arr)

            s_shifted = Image.new("RGBA", (1920, 1080), (0, 0, 0, 0))
            s_shifted.paste(f_temp, (0, total_sign_y))
            frame.alpha_composite(s_shifted)

        # -------------------------------------------------------------
        # 10. Refined Quote Banner (t: 17.45 -> end)
        # -------------------------------------------------------------
        if t >= 17.45:
            q_t = min(1.0, (t - 17.45) / 0.80)
            q_alpha = ease_out_cubic(q_t)
            q_offset_y = int(40.0 * (1.0 - ease_out_back(q_t, 1.3)))
            q_img = img_layers["quote"]

            arr = np.array(q_img)
            if q_alpha < 0.99:
                arr[..., 3] = (arr[..., 3] * q_alpha).astype(np.uint8)
            f_temp = Image.fromarray(arr)

            q_shifted = Image.new("RGBA", (1920, 1080), (0, 0, 0, 0))
            q_shifted.paste(f_temp, (0, q_offset_y))
            frame.alpha_composite(q_shifted)

        # -------------------------------------------------------------
        # 11. Dynamic Word-Highlight Subtitles (Before 17.45s to avoid clutter with quote)
        # -------------------------------------------------------------
        if t < 17.40:
            draw_dynamic_subtitles(frame, current_time=t, font=sub_font)

        # Save frame
        frame_rgb = frame.convert("RGB")
        frame_out_path = output_frames_dir / f"frame_{f_idx:05d}.jpg"
        frame_rgb.save(str(frame_out_path), "JPEG", quality=95)

        if f_idx % 60 == 0 or f_idx == total_frames - 1:
            print(f"  Frame {f_idx+1:04d}/{total_frames} ({t:.2f}s, {prog*100:.1f}%) rendered.")

    return total_frames


def encode_master_cut_video(
    frames_dir: Path,
    audio_wav: Path,
    output_mp4: Path,
    fps: int = 30,
) -> None:
    """Compile master video with audio, dynamic 30fps film grain, and optical vignette."""
    output_mp4.parent.mkdir(parents=True, exist_ok=True)
    filter_comp = (
        "[0:v]noise=alls=11:allf=t+u,"
        "vignette=PI/4.6,"
        "eq=contrast=1.06:saturation=0.92:brightness=0.01,"
        "format=yuv420p[vout]"
    )
    cmd = [
        "ffmpeg", "-y",
        "-framerate", str(fps),
        "-i", str(frames_dir / "frame_%05d.jpg"),
        "-i", str(audio_wav),
        "-filter_complex", filter_comp,
        "-map", "[vout]",
        "-map", "1:a",
        "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-profile:v", "high", "-level:v", "4.1", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest",
        str(output_mp4),
    ]
    print(f"🎬 Compiling master cut storytelling video to {output_mp4}...")
    subprocess.run(cmd, capture_output=True, check=True)
    print("✓ Master video encoding complete!")


def main():
    work_dir = Path("/home/luuvandien/.gemini/antigravity-ide/brain/21dc8a17-be9c-4323-b4c2-5b4aa028e2a3/scratch/master_cut_motion")
    frames_dir = work_dir / "frames"
    hero_img = Path("artifacts/berlin_1961_archival.jpg")
    audio_wav = Path("artifacts/tts_cache/dbe89b0cb306b9a5.wav")
    out_mp4 = Path("artifacts/berlin_storytelling_master_cut.mp4")

    print("================================================================================")
    print("🚀 BẮT ĐẦU DỰNG PHIÊN BẢN MASTER CUT: MOTION GRAPHIC + SUBTITLE ĐỘNG KARAOKE")
    print("================================================================================")

    print("Step 1: Tạo các lớp đồ họa nâng cấp (Clean Callout, Detailed Map, Enamel Sign)...")
    layers = build_master_layers(work_dir)

    print("Step 2: Dựng hoạt ảnh chuyển động 1961 + Subtitle Highlight vàng theo từng từ...")
    duration_sec = 24.5
    render_master_cut_frames(hero_img, layers, frames_dir, duration_sec=duration_sec, fps=30)

    print("Step 3: Mux âm thanh Azure Neural Voice + Film Grain + Optical Vignette...")
    encode_master_cut_video(frames_dir, audio_wav, out_mp4, fps=30)

    print("================================================================================")
    print(f"🎉 MASTER CUT HOÀN TẤT! Video tại: {out_mp4}")
    print("================================================================================")


if __name__ == "__main__":
    main()
