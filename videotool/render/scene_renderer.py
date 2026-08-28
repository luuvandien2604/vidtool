"""Reference-Faithful Scene Renderer (Phase 3).

Renders a declarative SceneSpec into a high-fidelity 1080p MP4 video using
real archival assets, Ken Burns slow-push motion, and the modular Vox Collage Engine.
"""
from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from videotool.domain.scene_schema import SceneSpec
from videotool.editorial.media.archival_resolver import ArchivalResolver
from videotool.render.collage import (VoxEditorialSceneConfig,
                                     render_vox_editorial_scene_svg)


class SceneRenderer:
    """Renders declarative SceneSpec to MP4."""

    def __init__(self, artifacts_dir: Path | str = "artifacts"):
        self.artifacts_dir = Path(artifacts_dir)
        self.resolver = ArchivalResolver(self.artifacts_dir)

    def render_scene(
        self,
        spec: SceneSpec,
        output_path: Path | str,
        fps: int = 30,
    ) -> Path:
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        project_id = spec.project.get("id", "scene_project")
        # 1. Resolve and download real archival media assets
        self.resolver.resolve_scene_assets(spec, project_id)

        media_dir = self.artifacts_dir / project_id / "media"
        proc_dir = media_dir / "processed"

        # Find primary hero photo
        hero_asset = next((a for a in spec.assets if a.role == "primary_visual"), None)
        if hero_asset:
            hero_img_path = proc_dir / f"{hero_asset.id}.png"
        else:
            first_asset = spec.assets[0] if spec.assets else None
            hero_img_path = proc_dir / f"{first_asset.id}.png" if first_asset else None

        # Secondary taped insets from spec assets
        secondary_cards = []
        sec_assets = [a for a in spec.assets if a.role in ("secondary_visual", "contextual_insert", "emotional_cutaway")]
        for idx, s_asset in enumerate(sec_assets):
            s_img = proc_dir / f"{s_asset.id}.png"
            if s_img.exists():
                offset_x = 1450.0 - idx * 270.0
                rot = 3.5 if idx % 2 == 0 else -4.0
                secondary_cards.append({
                    "href": str(s_img.resolve()),
                    "x": offset_x,
                    "y": 660.0 + idx * 40.0,
                    "width": 380.0 if idx == 0 else 260.0,
                    "height": 280.0 if idx == 0 else 220.0,
                    "rotation": rot,
                    "tape_corners": ("top-left", "top-right", "bottom-left", "bottom-right") if idx == 0 else ("top-left", "top-right"),
                })

        # 2. Build Vox Collage SVG Configuration
        headlines = spec.graphics.headline.get("text", "TIÊU ĐỀ\nBỐI CẢNH").split("\n")
        narration_text = spec.scene.get("narration", {}).get("text", "")
        date_card = spec.graphics.date_card
        quote = spec.graphics.quote

        config = VoxEditorialSceneConfig(
            chapter_text=spec.graphics.chapter_label.get("text", "CHƯƠNG 1"),
            headline_lines=headlines,
            body_paragraphs=narration_text,
            date_milestone=date_card.date or "1961",
            date_title=date_card.title or "SỰ KIỆN LỊCH SỬ",
            date_subtitle=date_card.subtitle or "MỐC LỊCH SỬ",
            quote_text=quote.text or "",
            quote_emphasis=quote.emphasis or [],
            show_map_card=True,
            secondary_cards=secondary_cards,
            canvas_w=spec.project.get("resolution", {}).get("width", 1920),
            canvas_h=spec.project.get("resolution", {}).get("height", 1080),
            accent_yellow=spec.style.get("palette", {}).get("yellow", "#E1B400"),
            west_blue=spec.style.get("palette", {}).get("blue", "#33495A"),
            east_red=spec.style.get("palette", {}).get("red", "#8C3932"),
        )

        svg_content = render_vox_editorial_scene_svg(config)

        # Write overlay SVG and pre-rasterize to PNG for fast hardware/software compositing
        svg_file = self.artifacts_dir / project_id / "scene_overlay.svg"
        svg_file.write_text(svg_content, encoding="utf-8")
        overlay_png = self.artifacts_dir / project_id / "scene_overlay.png"

        # Fast 1-shot rasterize SVG -> PNG
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(svg_file.resolve()), "-frames:v", "1", "-update", "1", str(overlay_png.resolve())],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True
        )

        duration_sec = float(spec.project.get("duration_seconds", 12.0))

        # 3. Render via FFmpeg with Ken Burns slow-push on the hero image under the PNG overlay
        # Conservative scale 1.00 -> 1.06 to avoid blurriness on archival asset
        total_frames = int(duration_sec * fps)
        zoom_expr = "min(zoom+0.0003,1.06)"

        filter_complex = (
            f"[0:v]zoompan=z='{zoom_expr}':d={total_frames}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1920x1080:fps={fps},format=yuv420p[hero];"
            f"[1:v]scale=1920:1080[overlay];"
            f"[hero][overlay]overlay=0:0[v]"
        )

        cmd = [
            "ffmpeg", "-y",
            "-i", str(hero_img_path.resolve()),
            "-loop", "1", "-t", str(duration_sec), "-i", str(overlay_png.resolve()),
            "-f", "lavfi", "-t", str(duration_sec), "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
            "-filter_complex", filter_complex,
            "-map", "[v]", "-map", "2:a",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast", "-crf", "18",
            "-c:a", "aac", "-b:a", "192k",
            "-shortest",
            str(output_file.resolve()),
        ]

        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        return output_file
