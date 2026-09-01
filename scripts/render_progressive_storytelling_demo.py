"""Progressive Storytelling Motion Graphic Engine.

Voice-Synchronized Progressive Reveal Motion Architecture:
Every visual element enters the frame dynamically at the exact millisecond
its entity / keyword is spoken by the voiceover narrator.

Choreography Map:
- 0.00s - 0.70s: Base Canvas + Ken Burns photo push-in starts + Left Paper Tear panel slides in.
- 0.40s - 0.90s: Chapter Badge ('CHƯƠNG 1') pops in with spring bounce.
- 0.70s - 1.50s: Headline ('BỐI CẢNH RA ĐỜI BỨC TƯỜNG BERLIN') + Animated Yellow Paint Brush Wipe.
- 1.40s - 3.80s [Voice: 'Sau Thế chiến II...']: Paragraph lines 1 & 2 reveal.
- 2.75s - 4.50s [Voice: 'Đông Đức và Tây Đức']: Taped Map Card drops in on top-right + East/West regions pulse highlight.
- 4.60s - 8.00s [Voice: 'Hàng triệu người...']: Paragraph lines 3 & 4 reveal.
- 8.90s - 10.50s [Voice: 'Để ngăn làn sóng...']: Paragraph lines 5 & 6 reveal.
- 10.70s - 13.50s [Voice: 'ngày 13 tháng 8 năm 1961']: Milestone Fact Card ('13/08/1961') slides up with gold brackets.
- 15.40s - 17.50s [Voice: 'ngăn cách Berlin']: Warning Sign ('Achtung!') pops into bottom-right.
- 17.45s - 23.50s [Voice: 'Một bức tường không chỉ...']: Quote Ribbon sweeps in; keywords 'nỗi sợ hãi' & 'sự chia rẽ' light up in gold.
- 23.50s - 25.00s: Master cinematic hold with dynamic 30fps film grain and optical vignette.
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
from videotool.render.collage.map_card import render_map_card_svg
from videotool.render.collage.fact_card import render_fact_card_svg
from videotool.render.collage.quote_banner import render_quote_banner_svg
from videotool.render.collage.tape_decoration import render_tape_strip_svg


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
    """Render an SVG string into a transparent PIL Image via FFmpeg librsvg."""
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


def build_scene_asset_layers(work_dir: Path) -> dict[str, Path]:
    """Generate isolated transparent PNG assets for each visual component."""
    work_dir.mkdir(parents=True, exist_ok=True)
    layer_paths = {}

    # 1. Left Torn-Paper Panel (Base texture without text)
    defs_xml, paper_xml = render_paper_panel_svg(
        width=740.0, height=1080, fill_color="#18191D", seed=42
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
        <rect x="0" y="0" width="136" height="34" rx="17" fill="#0D0E10" stroke="#E1B400" stroke-width="1.8" />
        <text x="68" y="23" text-anchor="middle" font-family="'DejaVu Sans', sans-serif" font-size="14" font-weight="900" fill="#E7E0D2" letter-spacing="1.5">CHƯƠNG 1</text>
      </g>
    </svg>"""
    p_chap = work_dir / "layer_chapter.png"
    render_svg_to_png(chap_svg, p_chap)
    layer_paths["chapter"] = p_chap

    # 3. Headline Text (2 lines)
    head_svg = """<svg xmlns="http://www.w3.org/2000/svg" width="1920" height="1080" viewBox="0 0 1920 1080">
      <text x="60" y="180" font-family="'DejaVu Sans', 'Liberation Sans', sans-serif" font-size="58" font-weight="900" fill="#FFFFFF" letter-spacing="1.0">BỐI CẢNH RA ĐỜI</text>
      <text x="60" y="252" font-family="'DejaVu Sans', 'Liberation Sans', sans-serif" font-size="58" font-weight="900" fill="#FFFFFF" letter-spacing="1.0">BỨC TƯỜNG BERLIN</text>
    </svg>"""
    p_head = work_dir / "layer_headline.png"
    render_svg_to_png(head_svg, p_head)
    layer_paths["headline"] = p_head

    # 4. Yellow Brush Stroke (to be wiped/revealed dynamically under headline)
    brush_d = generate_brush_stroke_svg(x=58.0, y=190.0, width=540.0, height=18.0, color="#E1B400", seed=42)
    brush_svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="1920" height="1080" viewBox="0 0 1920 1080">
      {brush_d}
    </svg>"""
    p_brush = work_dir / "layer_brush.png"
    render_svg_to_png(brush_svg, p_brush)
    layer_paths["brush"] = p_brush

    # 5. Paragraph Body Text (split into 3 staggered blocks)
    # Block A: Lines 1 & 2
    body_a_svg = """<svg xmlns="http://www.w3.org/2000/svg" width="1920" height="1080" viewBox="0 0 1920 1080">
      <g fill="#D5D0C6" font-family="'DejaVu Sans', sans-serif" font-size="18.5" font-weight="500" letter-spacing="0.3">
        <text x="60" y="325">Sau Thế chiến II, nước Đức bị chia cắt thành</text>
        <text x="60" y="356">Đông Đức (cộng sản) và Tây Đức (tư bản).</text>
      </g>
    </svg>"""
    p_body_a = work_dir / "layer_body_a.png"
    render_svg_to_png(body_a_svg, p_body_a)
    layer_paths["body_a"] = p_body_a

    # Block B: Lines 3 & 4
    body_b_svg = """<svg xmlns="http://www.w3.org/2000/svg" width="1920" height="1080" viewBox="0 0 1920 1080">
      <g fill="#D5D0C6" font-family="'DejaVu Sans', sans-serif" font-size="18.5" font-weight="500" letter-spacing="0.3">
        <text x="60" y="405">Hàng triệu người Đông Đức tìm cách vượt</text>
        <text x="60" y="436">biên sang Tây Đức để tìm tự do.</text>
      </g>
    </svg>"""
    p_body_b = work_dir / "layer_body_b.png"
    render_svg_to_png(body_b_svg, p_body_b)
    layer_paths["body_b"] = p_body_b

    # Block C: Lines 5 & 6
    body_c_svg = """<svg xmlns="http://www.w3.org/2000/svg" width="1920" height="1080" viewBox="0 0 1920 1080">
      <g fill="#D5D0C6" font-family="'DejaVu Sans', sans-serif" font-size="18.5" font-weight="500" letter-spacing="0.3">
        <text x="60" y="485">Để ngăn làn sóng tháo chạy, chính quyền</text>
        <text x="60" y="516">Đông Đức quyết định dựng lên bức tường ngăn cách Berlin.</text>
      </g>
    </svg>"""
    p_body_c = work_dir / "layer_body_c.png"
    render_svg_to_png(body_c_svg, p_body_c)
    layer_paths["body_c"] = p_body_c

    # 6. Gold Fact Card (13/08/1961)
    fact_svg = render_fact_card_svg(
        x=60.0, y=740.0, width=490.0, height=130.0,
        date_text="13/08/1961",
        title_text="BỨC TƯỜNG BERLIN",
        subtitle_text="CHÍNH THỨC ĐƯỢC XÂY DỰNG",
        accent_color="#E1B400"
    )
    full_fact_svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="1920" height="1080" viewBox="0 0 1920 1080">
      <defs>
        <filter id="fact-drop-shadow"><feDropShadow dx="4" dy="8" stdDeviation="10" flood-color="#000000" flood-opacity="0.7"/></filter>
      </defs>
      {fact_svg}
    </svg>"""
    p_fact = work_dir / "layer_fact.png"
    render_svg_to_png(full_fact_svg, p_fact)
    layer_paths["fact"] = p_fact

    # 7. Top-Right Taped Map Card
    map_markup = render_map_card_svg(
        x=1440.0, y=55.0, width=400.0, height=310.0,
        west_color="#33495A", east_color="#8C3932", tape_seed=52
    )
    map_svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="1920" height="1080" viewBox="0 0 1920 1080">
      <defs>
        <filter id="mapShadow"><feDropShadow dx="6" dy="10" stdDeviation="12" flood-color="#000000" flood-opacity="0.65"/></filter>
      </defs>
      {map_markup}
    </svg>"""
    p_map = work_dir / "layer_map.png"
    render_svg_to_png(map_svg, p_map)
    layer_paths["map"] = p_map

    # 8. Bottom-Right Warning Sign
    sign_svg = """<svg xmlns="http://www.w3.org/2000/svg" width="1920" height="1080" viewBox="0 0 1920 1080">
      <g transform="translate(1480, 680) rotate(3 180 120)" filter="drop-shadow(6px 10px 14px rgba(0,0,0,0.7))">
        <!-- Sign board -->
        <rect x="0" y="0" width="370" height="240" rx="4" fill="#EAE6DC" stroke="#B8B0A2" stroke-width="2" />
        <text x="185" y="55" text-anchor="middle" font-family="'DejaVu Sans', sans-serif" font-size="34" font-weight="900" fill="#B32014" letter-spacing="1">Achtung !</text>
        <text x="185" y="105" text-anchor="middle" font-family="'DejaVu Sans', sans-serif" font-size="20" font-weight="bold" fill="#18181A">Sie verlassen jetzt</text>
        <text x="185" y="145" text-anchor="middle" font-family="'DejaVu Sans', sans-serif" font-size="24" font-weight="900" fill="#18181A">West-Berlin</text>
        <!-- Tape at corners -->
        <polygon points="10,-8 50,-14 44,16 4,22" fill="#F4F0DC" fill-opacity="0.75" />
        <polygon points="320,-12 360,-6 354,24 314,18" fill="#F4F0DC" fill-opacity="0.75" />
      </g>
    </svg>"""
    p_sign = work_dir / "layer_sign.png"
    render_svg_to_png(sign_svg, p_sign)
    layer_paths["sign"] = p_sign

    # 9. Bottom Quote Banner Base (without glowing gold keywords)
    quote_base_markup = render_quote_banner_svg(
        x=280.0, y=930.0, width=1360.0, height=84.0,
        text="Một bức tường không chỉ bằng bê tông và dây thép gai, mà còn bằng nỗi sợ hãi và sự chia rẽ.",
        emphasis_keywords=[],  # all white text initially
        accent_color="#E1B400", seed=48
    )
    quote_base_svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="1920" height="1080" viewBox="0 0 1920 1080">
      <defs>
        <filter id="quoteShadow"><feDropShadow dx="0" dy="6" stdDeviation="12" flood-color="#000000" flood-opacity="0.8"/></filter>
      </defs>
      {quote_base_markup}
    </svg>"""
    p_quote_base = work_dir / "layer_quote_base.png"
    render_svg_to_png(quote_base_svg, p_quote_base)
    layer_paths["quote_base"] = p_quote_base

    # 10. Bottom Quote Banner with highlighted gold keywords ("nỗi sợ hãi", "sự chia rẽ")
    quote_gold_markup = render_quote_banner_svg(
        x=280.0, y=930.0, width=1360.0, height=84.0,
        text="Một bức tường không chỉ bằng bê tông và dây thép gai, mà còn bằng nỗi sợ hãi và sự chia rẽ.",
        emphasis_keywords=["nỗi sợ hãi", "sự chia rẽ"],
        accent_color="#E1B400", seed=48
    )
    quote_gold_svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="1920" height="1080" viewBox="0 0 1920 1080">
      <defs>
        <filter id="quoteShadow"><feDropShadow dx="0" dy="6" stdDeviation="12" flood-color="#000000" flood-opacity="0.8"/></filter>
      </defs>
      {quote_gold_markup}
    </svg>"""
    p_quote_gold = work_dir / "layer_quote_gold.png"
    render_svg_to_png(quote_gold_svg, p_quote_gold)
    layer_paths["quote_gold"] = p_quote_gold

    return layer_paths


def render_progressive_storytelling_frames(
    hero_image_path: Path,
    layers: dict[str, Path],
    output_frames_dir: Path,
    duration_sec: float = 24.5,
    fps: int = 30,
) -> int:
    """Choreograph and render all 735 frames with exact voice-synchronized progressive entrances."""
    output_frames_dir.mkdir(parents=True, exist_ok=True)
    total_frames = int(duration_sec * fps)

    # Load layer images into RAM
    hero_base = Image.open(hero_image_path).convert("RGB")
    hero_w, hero_h = hero_base.size

    img_layers = {k: Image.open(p).convert("RGBA") for k, p in layers.items()}
    brush_full = img_layers["brush"]

    print(f"🎬 Rendering {total_frames} progressive storytelling frames ({duration_sec:.1f}s @ {fps}fps)...")

    for f_idx in range(total_frames):
        t = f_idx / fps  # Current timestamp in seconds
        prog = f_idx / max(1, total_frames - 1)

        # Base Frame Canvas (#121216)
        frame = Image.new("RGBA", (1920, 1080), (18, 18, 22, 255))

        # -------------------------------------------------------------
        # 1. Hero Background: Ken Burns Continuous Slow Push-In (t: 0 -> end)
        # -------------------------------------------------------------
        kb_scale = 1.00 + 0.08 * ease_in_out_sine(prog)
        kb_pan_x = -20.0 * prog
        kb_pan_y = 10.0 * prog

        crop_w = int(hero_w / kb_scale)
        crop_h = int(hero_h / kb_scale)
        crop_x = max(0, min(hero_w - crop_w, int((hero_w - crop_w) / 2.0 + kb_pan_x)))
        crop_y = max(0, min(hero_h - crop_h, int((hero_h - crop_h) / 2.0 + kb_pan_y)))

        cropped_hero = hero_base.crop((crop_x, crop_y, crop_x + crop_w, crop_y + crop_h))
        scaled_hero = cropped_hero.resize((1920, 1080), Image.Resampling.BILINEAR)
        frame.paste(scaled_hero, (0, 0))

        # -------------------------------------------------------------
        # 2. Left Torn Paper Panel: Slide-in with Elastic Settle (t: 0.05 -> 0.70s)
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
            chap_scale = ease_out_back(chap_t, 2.2)
            if chap_scale > 0.05:
                chap_img = img_layers["chapter"]
                frame.alpha_composite(chap_img)

        # -------------------------------------------------------------
        # 4. Headline Text: Typographic Entrance (t: 0.60 -> 1.10s)
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

        # -------------------------------------------------------------
        # 5. Yellow Brush Swipe: Left-to-Right Paint Wipe (t: 0.90 -> 1.70s)
        # -------------------------------------------------------------
        if t >= 0.90:
            brush_t = min(1.0, (t - 0.90) / 0.80)
            brush_prog = ease_out_cubic(brush_t)
            wipe_x = int(58 + (620 - 58) * brush_prog)
            if wipe_x > 60:
                b_crop = brush_full.crop((0, 0, wipe_x, 1080))
                b_frame = Image.new("RGBA", (1920, 1080), (0, 0, 0, 0))
                b_frame.paste(b_crop, (0, 0))
                frame.alpha_composite(b_frame)

        # -------------------------------------------------------------
        # 6. Body Text Block A: 'Sau Thế chiến II...' (t: 1.40 -> 2.20s)
        # -------------------------------------------------------------
        if t >= 1.40:
            ba_t = min(1.0, (t - 1.40) / 0.60)
            ba_alpha = ease_out_cubic(ba_t)
            ba_offset_y = int(12.0 * (1.0 - ease_out_cubic(ba_t)))
            ba_img = img_layers["body_a"]
            if ba_alpha < 0.99 or ba_offset_y > 0:
                ba_faded = ba_img.copy()
                arr = np.array(ba_faded)
                arr[..., 3] = (arr[..., 3] * ba_alpha).astype(np.uint8)
                f_temp = Image.fromarray(arr)
                f_shifted = Image.new("RGBA", (1920, 1080), (0, 0, 0, 0))
                f_shifted.paste(f_temp, (0, -ba_offset_y))
                frame.alpha_composite(f_shifted)
            else:
                frame.alpha_composite(ba_img)

        # -------------------------------------------------------------
        # 7. Top-Right Taped Map Card: Drops In at Voice 'Đông Đức và Tây Đức' (t: 2.75 -> 3.75s)
        # -------------------------------------------------------------
        if t >= 2.75:
            map_t = min(1.0, (t - 2.75) / 0.70)
            map_bounce = ease_out_back(map_t, 1.6)
            map_offset_y = int(-140.0 * (1.0 - map_bounce))
            map_img = img_layers["map"]

            # Slight floating breathing drift after landing
            drift_y = int(3.5 * math.sin(t * 1.8))
            total_map_y = map_offset_y + drift_y

            m_shifted = Image.new("RGBA", (1920, 1080), (0, 0, 0, 0))
            m_shifted.paste(map_img, (0, total_map_y))
            frame.alpha_composite(m_shifted)

        # -------------------------------------------------------------
        # 8. Body Text Block B: 'Hàng triệu người Đông Đức...' (t: 4.60 -> 5.40s)
        # -------------------------------------------------------------
        if t >= 4.60:
            bb_t = min(1.0, (t - 4.60) / 0.60)
            bb_alpha = ease_out_cubic(bb_t)
            bb_offset_y = int(12.0 * (1.0 - ease_out_cubic(bb_t)))
            bb_img = img_layers["body_b"]
            if bb_alpha < 0.99 or bb_offset_y > 0:
                bb_faded = bb_img.copy()
                arr = np.array(bb_faded)
                arr[..., 3] = (arr[..., 3] * bb_alpha).astype(np.uint8)
                f_temp = Image.fromarray(arr)
                f_shifted = Image.new("RGBA", (1920, 1080), (0, 0, 0, 0))
                f_shifted.paste(f_temp, (0, -bb_offset_y))
                frame.alpha_composite(f_shifted)
            else:
                frame.alpha_composite(bb_img)

        # -------------------------------------------------------------
        # 9. Body Text Block C: 'Để ngăn làn sóng tháo chạy...' (t: 8.90 -> 9.70s)
        # -------------------------------------------------------------
        if t >= 8.90:
            bc_t = min(1.0, (t - 8.90) / 0.60)
            bc_alpha = ease_out_cubic(bc_t)
            bc_offset_y = int(12.0 * (1.0 - ease_out_cubic(bc_t)))
            bc_img = img_layers["body_c"]
            if bc_alpha < 0.99 or bc_offset_y > 0:
                bc_faded = bc_img.copy()
                arr = np.array(bc_faded)
                arr[..., 3] = (arr[..., 3] * bc_alpha).astype(np.uint8)
                f_temp = Image.fromarray(arr)
                f_shifted = Image.new("RGBA", (1920, 1080), (0, 0, 0, 0))
                f_shifted.paste(f_temp, (0, -bc_offset_y))
                frame.alpha_composite(f_shifted)
            else:
                frame.alpha_composite(bc_img)

        # -------------------------------------------------------------
        # 10. Gold Milestone Fact Card ('13/08/1961'): Slide-up at Voice Date (t: 10.70 -> 11.60s)
        # -------------------------------------------------------------
        if t >= 10.70:
            fact_t = min(1.0, (t - 10.70) / 0.80)
            fact_offset_y = int(80.0 * (1.0 - ease_out_back(fact_t, 1.4)))
            fact_alpha = ease_out_cubic(fact_t)
            fact_img = img_layers["fact"]

            if fact_alpha < 0.99 or fact_offset_y > 0:
                f_faded = fact_img.copy()
                arr = np.array(f_faded)
                arr[..., 3] = (arr[..., 3] * fact_alpha).astype(np.uint8)
                f_temp = Image.fromarray(arr)
                f_shifted = Image.new("RGBA", (1920, 1080), (0, 0, 0, 0))
                f_shifted.paste(f_temp, (0, fact_offset_y))
                frame.alpha_composite(f_shifted)
            else:
                frame.alpha_composite(fact_img)

        # -------------------------------------------------------------
        # 11. Warning Sign ('Achtung!'): Pops In at Voice 'ngăn cách Berlin' (t: 15.40 -> 16.30s)
        # -------------------------------------------------------------
        if t >= 15.40:
            sign_t = min(1.0, (t - 15.40) / 0.65)
            sign_scale = ease_out_back(sign_t, 1.8)
            sign_offset_y = int(50.0 * (1.0 - sign_scale))
            sign_alpha = ease_out_cubic(sign_t)
            sign_img = img_layers["sign"]

            # Subtle secondary drift
            drift_sign_y = int(2.5 * math.sin(t * 1.5 + 1.0))
            total_sign_y = sign_offset_y + drift_sign_y

            s_faded = sign_img.copy()
            if sign_alpha < 0.99:
                arr = np.array(s_faded)
                arr[..., 3] = (arr[..., 3] * sign_alpha).astype(np.uint8)
                s_faded = Image.fromarray(arr)

            s_shifted = Image.new("RGBA", (1920, 1080), (0, 0, 0, 0))
            s_shifted.paste(s_faded, (0, total_sign_y))
            frame.alpha_composite(s_shifted)

        # -------------------------------------------------------------
        # 12. Bottom Quote Ribbon + Progressive Gold Keyword Glow (t: 17.45 -> end)
        # -------------------------------------------------------------
        if t >= 17.45:
            q_t = min(1.0, (t - 17.45) / 0.85)
            q_alpha = ease_out_cubic(q_t)
            q_offset_y = int(45.0 * (1.0 - ease_out_back(q_t, 1.3)))

            # Before 20.90s: Base quote ribbon
            # From 20.90s onwards (Voice: 'nỗi sợ hãi và sự chia rẽ'): Blend into gold keyword ribbon
            if t < 20.90:
                q_img = img_layers["quote_base"]
            else:
                # Smooth cross-fade to glowing gold keywords
                gold_prog = min(1.0, (t - 20.90) / 0.80)
                base_img = img_layers["quote_base"]
                gold_img = img_layers["quote_gold"]
                q_img = Image.blend(base_img, gold_img, gold_prog)

            q_faded = q_img.copy()
            if q_alpha < 0.99:
                arr = np.array(q_faded)
                arr[..., 3] = (arr[..., 3] * q_alpha).astype(np.uint8)
                q_faded = Image.fromarray(arr)

            q_shifted = Image.new("RGBA", (1920, 1080), (0, 0, 0, 0))
            q_shifted.paste(q_faded, (0, q_offset_y))
            frame.alpha_composite(q_shifted)

        # -------------------------------------------------------------
        # Save output frame as high-quality JPEG
        # -------------------------------------------------------------
        frame_rgb = frame.convert("RGB")
        frame_out_path = output_frames_dir / f"frame_{f_idx:05d}.jpg"
        frame_rgb.save(str(frame_out_path), "JPEG", quality=95)

        if f_idx % 60 == 0 or f_idx == total_frames - 1:
            print(f"  Frame {f_idx+1:04d}/{total_frames} ({t:.2f}s, {prog*100:.1f}%) rendered.")

    return total_frames


def encode_cinematic_storytelling_movie(
    frames_dir: Path,
    audio_wav: Path,
    output_mp4: Path,
    fps: int = 30,
) -> None:
    """Encode rendered frames with audio, 30fps dynamic film grain, and subtle optical vignette."""
    output_mp4.parent.mkdir(parents=True, exist_ok=True)
    filter_comp = (
        "[0:v]noise=alls=10:allf=t+u,"
        "vignette=PI/4.5,"
        "eq=contrast=1.05:saturation=0.94:brightness=0.01,"
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
    print(f"🎬 Compiling cinematic storytelling video to {output_mp4}...")
    subprocess.run(cmd, capture_output=True, check=True)
    print("✓ Video encoding complete!")


def main():
    work_dir = Path("/home/luuvandien/.gemini/antigravity-ide/brain/21dc8a17-be9c-4323-b4c2-5b4aa028e2a3/scratch/storytelling_motion")
    frames_dir = work_dir / "frames"
    user_img = Path("artifacts/berlin_hero_clean.jpg")
    audio_wav = Path("/home/luuvandien/videotool/artifacts/tts_cache/dbe89b0cb306b9a5.wav")
    out_mp4 = Path("/home/luuvandien/videotool/artifacts/berlin_storytelling_motion.mp4")

    print("================================================================================")
    print("🚀 BẮT ĐẦU DỰNG VIDEO MOTION GRAPHIC KỂ CHUYỆN ĐỒNG BỘ GIỌNG NÓI")
    print("================================================================================")

    print("Step 1: Trích xuất các lớp đồ họa vật lý độc lập (Isolated Visual Layers)...")
    layers = build_scene_asset_layers(work_dir)

    print("Step 2: Dựng hoạt ảnh chuyển động tuần tự khớp với từng mốc từ vựng...")
    duration_sec = 24.5  # Matches 23.48s audio duration + 1s cinematic hold
    render_progressive_storytelling_frames(user_img, layers, frames_dir, duration_sec=duration_sec, fps=30)

    print("Step 3: Mux âm thanh Azure Neural Voice + Film Grain + Optical Vignette...")
    encode_cinematic_storytelling_movie(frames_dir, audio_wav, out_mp4, fps=30)

    print("================================================================================")
    print(f"🎉 HOÀN TẤT! Video master sẵn sàng tại: {out_mp4}")
    print("================================================================================")


if __name__ == "__main__":
    main()
