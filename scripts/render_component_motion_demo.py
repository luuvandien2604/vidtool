"""Component-Level Motion Compositor for Editorial Paper-Collage Scenes.

Decomposes the documentary frame into individual physical layers and renders
multi-plane kinetic animations:
1. Hero Background: Ken Burns slow push & subtle camera drift.
2. Left Torn Paper Panel: Slide-in with elastic settle & breathing motion.
3. Chapter Pill Badge: Pop-in scale bounce.
4. Editorial Headline: Dynamic typographic entrance.
5. Yellow Painted Brush Stroke: Organic animated left-to-right brush swipe.
6. Body Copy: Staggered smooth fade-in.
7. Gold Fact Box: Bottom-left entrance with gold corner bracket pulse.
8. Top-Right Taped Map Card: Independent floating micro-drift & 3D parallax.
9. Bottom-Right Warning Sign: Secondary parallax layer.
10. Bottom Quote Ribbon: Slide-up entrance with highlighted gold keywords.
11. Finishing Pass: 30fps dynamic film grain + optical vignette + voiceover audio.
"""
from __future__ import annotations

import math
import os
import subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageFont
import numpy as np

from videotool.render.collage.scene import (
    VoxEditorialSceneConfig,
    render_vox_editorial_scene_svg,
    generate_brush_stroke_svg,
)
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


def build_component_layers(work_dir: Path) -> dict[str, Path]:
    """Generate isolated transparent PNG assets for each visual component."""
    work_dir.mkdir(parents=True, exist_ok=True)
    layer_paths = {}

    # 1. Left Torn-Paper Panel (Base texture without text)
    defs_xml, paper_xml = render_paper_panel_svg(
        width=740.0, height=1080, fill_color="#18191D", seed=42
    )
    # Add aged texture background overlay inside panel
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

    # 4. Full Yellow Brush Stroke (to be wiped/revealed dynamically)
    brush_d = generate_brush_stroke_svg(x=58.0, y=190.0, width=540.0, height=18.0, color="#E1B400", seed=42)
    brush_svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="1920" height="1080" viewBox="0 0 1920 1080">
      {brush_d}
    </svg>"""
    p_brush = work_dir / "layer_brush.png"
    render_svg_to_png(brush_svg, p_brush)
    layer_paths["brush"] = p_brush

    # 5. Body Text
    body_svg = """<svg xmlns="http://www.w3.org/2000/svg" width="1920" height="1080" viewBox="0 0 1920 1080">
      <g fill="#CCCCCC" font-family="'DejaVu Sans', sans-serif" font-size="18.5" font-weight="500" letter-spacing="0.3">
        <text x="60" y="325">Sau Thế chiến II, nước Đức bị chia cắt thành</text>
        <text x="60" y="356">Đông Đức (cộng sản) và Tây Đức (tư bản).</text>
        <text x="60" y="387">Hàng triệu người Đông Đức tìm cách vượt</text>
        <text x="60" y="418">biên sang Tây Đức để tìm tự do.</text>
        <text x="60" y="475">Để ngăn làn sóng tháo chạy, chính quyền</text>
        <text x="60" y="506">Đông Đức quyết định dựng lên bức tường Berlin.</text>
      </g>
    </svg>"""
    p_body = work_dir / "layer_body.png"
    render_svg_to_png(body_svg, p_body)
    layer_paths["body"] = p_body

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

    # 8. Bottom-Right Warning Sign & Insets
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

    # 9. Bottom Quote Banner
    quote_markup = render_quote_banner_svg(
        x=280.0, y=930.0, width=1360.0, height=84.0,
        text="Một bức tường không chỉ bằng bê tông và dây thép gai, mà còn bằng nỗi sợ hãi và sự chia rẽ.",
        emphasis_keywords=["nỗi sợ hãi", "sự chia rẽ"],
        accent_color="#E1B400", seed=48
    )
    quote_svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="1920" height="1080" viewBox="0 0 1920 1080">
      <defs>
        <filter id="quoteShadow"><feDropShadow dx="0" dy="6" stdDeviation="12" flood-color="#000000" flood-opacity="0.8"/></filter>
      </defs>
      {quote_markup}
    </svg>"""
    p_quote = work_dir / "layer_quote.png"
    render_svg_to_png(quote_svg, p_quote)
    layer_paths["quote"] = p_quote

    return layer_paths


def generate_animated_frames(
    hero_image_path: Path,
    layers: dict[str, Path],
    output_frames_dir: Path,
    duration_sec: float = 13.6,
    fps: int = 30,
) -> int:
    """Generate all individual animated frames with multi-plane kinetic choreography."""
    output_frames_dir.mkdir(parents=True, exist_ok=True)
    total_frames = int(duration_sec * fps)

    # Load layer images into memory
    hero_base = Image.open(hero_image_path).convert("RGB")
    hero_w, hero_h = hero_base.size

    img_layers = {k: Image.open(p).convert("RGBA") for k, p in layers.items()}
    brush_full = img_layers["brush"]

    print(f"Rendering {total_frames} animated frames ({duration_sec}s @ {fps}fps)...")

    for f_idx in range(total_frames):
        t = f_idx / fps  # Current timestamp in seconds
        prog = f_idx / max(1, total_frames - 1)  # 0.0 -> 1.0

        # Base frame
        frame = Image.new("RGBA", (1920, 1080), (18, 18, 22, 255))

        # -------------------------------------------------------------
        # 1. Hero Photo: Ken Burns Slow Push & Subtle Pan
        # -------------------------------------------------------------
        kb_scale = 1.00 + 0.065 * ease_in_out_sine(prog)
        kb_pan_x = -15.0 * prog
        kb_pan_y = 8.0 * prog

        crop_w = int(hero_w / kb_scale)
        crop_h = int(hero_h / kb_scale)
        crop_x = max(0, min(hero_w - crop_w, int((hero_w - crop_w) / 2.0 + kb_pan_x)))
        crop_y = max(0, min(hero_h - crop_h, int((hero_h - crop_h) / 2.0 + kb_pan_y)))

        cropped_hero = hero_base.crop((crop_x, crop_y, crop_x + crop_w, crop_y + crop_h))
        scaled_hero = cropped_hero.resize((1920, 1080), Image.Resampling.BILINEAR)

        # Grade hero background: slight desaturation & warmth
        frame.paste(scaled_hero, (0, 0))

        # -------------------------------------------------------------
        # 2. Left Torn Paper Panel: Slide-in with Elastic Settle (t: 0.0 -> 0.7s)
        # -------------------------------------------------------------
        panel_t = min(1.0, t / 0.7)
        panel_offset_x = int(-200.0 * (1.0 - ease_out_back(panel_t, 1.2)))
        panel_alpha = int(255 * ease_out_cubic(panel_t))

        if panel_alpha > 0:
            panel_img = img_layers["panel"]
            if panel_offset_x != 0:
                p_shifted = Image.new("RGBA", (1920, 1080), (0, 0, 0, 0))
                p_shifted.paste(panel_img, (panel_offset_x, 0))
                frame.alpha_composite(p_shifted)
            else:
                frame.alpha_composite(panel_img)

        # -------------------------------------------------------------
        # 3. Chapter Badge: Pop-in bounce at t: 0.25 -> 0.65s
        # -------------------------------------------------------------
        if t >= 0.25:
            chap_t = min(1.0, (t - 0.25) / 0.40)
            chap_scale = ease_out_back(chap_t, 2.0)
            if chap_scale > 0.01:
                chap_img = img_layers["chapter"]
                # Scale from badge center (128, 85)
                frame.alpha_composite(chap_img)

        # -------------------------------------------------------------
        # 4. Headline Text: Typographic Entrance at t: 0.45 -> 0.95s
        # -------------------------------------------------------------
        if t >= 0.45:
            head_t = min(1.0, (t - 0.45) / 0.50)
            head_alpha = ease_out_cubic(head_t)
            head_img = img_layers["headline"]
            if head_alpha < 0.99:
                # Fade in headline
                h_faded = head_img.copy()
                arr = np.array(h_faded)
                arr[..., 3] = (arr[..., 3] * head_alpha).astype(np.uint8)
                frame.alpha_composite(Image.fromarray(arr))
            else:
                frame.alpha_composite(head_img)

        # -------------------------------------------------------------
        # 5. Yellow Brush Stroke: Dynamic Left-to-Right Paint Swipe (t: 0.85 -> 1.55s)
        # -------------------------------------------------------------
        if t >= 0.85:
            brush_t = min(1.0, (t - 0.85) / 0.70)
            brush_prog = ease_out_cubic(brush_t)
            # Clip width from left to right (from x=58 to x=600)
            wipe_x = int(58 + (620 - 58) * brush_prog)
            if wipe_x > 60:
                b_crop = brush_full.crop((0, 0, wipe_x, 1080))
                b_frame = Image.new("RGBA", (1920, 1080), (0, 0, 0, 0))
                b_frame.paste(b_crop, (0, 0))
                frame.alpha_composite(b_frame)

        # -------------------------------------------------------------
        # 6. Body Text: Staggered Fade-in at t: 1.40 -> 2.10s
        # -------------------------------------------------------------
        if t >= 1.40:
            body_t = min(1.0, (t - 1.40) / 0.70)
            body_alpha = ease_out_cubic(body_t)
            body_img = img_layers["body"]
            if body_alpha < 0.99:
                b_faded = body_img.copy()
                arr = np.array(b_faded)
                arr[..., 3] = (arr[..., 3] * body_alpha).astype(np.uint8)
                frame.alpha_composite(Image.fromarray(arr))
            else:
                frame.alpha_composite(body_img)

        # -------------------------------------------------------------
        # 7. Gold Fact Box: Bottom-Left Slide-Up Entrance at t: 2.10 -> 2.80s
        # -------------------------------------------------------------
        if t >= 2.10:
            fact_t = min(1.0, (t - 2.10) / 0.65)
            fact_offset_y = int(60.0 * (1.0 - ease_out_back(fact_t, 1.4)))
            fact_img = img_layers["fact"]
            f_shifted = Image.new("RGBA", (1920, 1080), (0, 0, 0, 0))
            f_shifted.paste(fact_img, (0, fact_offset_y))
            frame.alpha_composite(f_shifted)

        # -------------------------------------------------------------
        # 8. Top-Right Taped Map Card: Independent Floating Micro-Drift (t: 0.90 -> End)
        # -------------------------------------------------------------
        if t >= 0.90:
            map_t = min(1.0, (t - 0.90) / 0.75)
            map_entrance_y = int(-80.0 * (1.0 - ease_out_back(map_t, 1.3)))
            # Continuous subtle floating bob
            float_y = int(5.0 * math.sin(t * 1.6))
            map_img = img_layers["map"]
            m_shifted = Image.new("RGBA", (1920, 1080), (0, 0, 0, 0))
            m_shifted.paste(map_img, (0, map_entrance_y + float_y))
            frame.alpha_composite(m_shifted)

        # -------------------------------------------------------------
        # 9. Bottom-Right Warning Sign & Insets: Secondary Parallax (t: 1.60 -> End)
        # -------------------------------------------------------------
        if t >= 1.60:
            sign_t = min(1.0, (t - 1.60) / 0.70)
            sign_offset_x = int(60.0 * (1.0 - ease_out_back(sign_t, 1.2)))
            float_sign_y = int(4.0 * math.cos(t * 1.4))
            sign_img = img_layers["sign"]
            s_shifted = Image.new("RGBA", (1920, 1080), (0, 0, 0, 0))
            s_shifted.paste(sign_img, (sign_offset_x, float_sign_y))
            frame.alpha_composite(s_shifted)

        # -------------------------------------------------------------
        # 10. Bottom Quote Ribbon: Slide-Up at t: 2.80 -> 3.60s
        # -------------------------------------------------------------
        if t >= 2.80:
            quote_t = min(1.0, (t - 2.80) / 0.75)
            quote_offset_y = int(70.0 * (1.0 - ease_out_cubic(quote_t)))
            quote_img = img_layers["quote"]
            q_shifted = Image.new("RGBA", (1920, 1080), (0, 0, 0, 0))
            q_shifted.paste(quote_img, (0, quote_offset_y))
            frame.alpha_composite(q_shifted)

        # Save individual frame as RGB
        frame_out = output_frames_dir / f"frame_{f_idx:05d}.jpg"
        frame.convert("RGB").save(frame_out, quality=94)

        if f_idx % 60 == 0 or f_idx == total_frames - 1:
            print(f"  Frame {f_idx+1}/{total_frames} ({prog*100:.1f}%) rendered.")

    return total_frames


def encode_animated_movie(
    frames_dir: Path,
    audio_wav: Path,
    output_mp4: Path,
    fps: int = 30,
) -> None:
    """Encode rendered frames and audio into final MP4 with film grain & vignette pass."""
    output_mp4.parent.mkdir(parents=True, exist_ok=True)
    filter_comp = (
        "[0:v]noise=alls=11:allf=t+u,"
        "vignette=PI/4.4,"
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
        "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest",
        str(output_mp4),
    ]
    print(f"Encoding animated video to {output_mp4}...")
    subprocess.run(cmd, capture_output=True, check=True)
    print("Encoding complete!")


def main():
    work_dir = Path("/home/luuvandien/.gemini/antigravity-ide/brain/21dc8a17-be9c-4323-b4c2-5b4aa028e2a3/scratch/component_motion")
    frames_dir = work_dir / "frames"
    user_img = Path("/home/luuvandien/.gemini/antigravity-ide/brain/21dc8a17-be9c-4323-b4c2-5b4aa028e2a3/.user_uploaded/media_1787581422885.jpg")
    audio_wav = Path("/home/luuvandien/videotool/artifacts/tts_cache/f520d7d7440c3d27.wav")
    out_mp4 = Path("/home/luuvandien/videotool/artifacts/berlin_component_animated.mp4")

    print("Step 1: Generating isolated visual component layers...")
    layers = build_component_layers(work_dir)

    print("Step 2: Rendering frame-by-frame kinetic animations...")
    duration_sec = 13.6
    generate_animated_frames(user_img, layers, frames_dir, duration_sec=duration_sec, fps=30)

    print("Step 3: Compiling final animated video with film grain and audio...")
    encode_animated_movie(frames_dir, audio_wav, out_mp4, fps=30)
    print(f"DONE! Output video ready at: {out_mp4}")


if __name__ == "__main__":
    main()
