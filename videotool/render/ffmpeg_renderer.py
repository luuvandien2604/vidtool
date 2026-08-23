"""FFmpeg renderer implementation with per-beat rendering and lossless concat.

Renders each beat into an isolated video clip, joins them losslessly via the
FFmpeg concat demuxer, and burns in the full-episode ASS subtitle track.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import xml.sax.saxutils as saxutils
from pathlib import Path
from typing import Any

from videotool.domain.narration import NarrationAudio
from videotool.editorial.media.cache import MediaCache
from videotool.render.frame_plan import BeatFramePlan, EpisodeFramePlan, MediaRenderElement
from videotool.render.interfaces import Renderer, RenderResult
from videotool.render.subtitles import escape_ass_text


def check_ffmpeg_available() -> tuple[bool, str]:
    """Check if ffmpeg and ffprobe are available on PATH."""
    ffmpeg_path = shutil.which("ffmpeg")
    ffprobe_path = shutil.which("ffprobe")
    if not ffmpeg_path or not ffprobe_path:
        return False, f"ffmpeg ({ffmpeg_path}) or ffprobe ({ffprobe_path}) missing from PATH"
    return True, "ok"


def probe_media_file(path: str | Path) -> dict[str, Any]:
    """Run ffprobe on a media file and return parsed JSON metadata."""
    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        str(path),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return json.loads(res.stdout)


def _generate_placeholder_card_svg(desc: str, kind: str, role: str,
                                   width: int, height: int) -> str:
    """Generate a clean SVG placeholder card for missing/placeholder assets."""
    w = max(64, width)
    h = max(64, height)
    title = f"{kind.upper()} [{role}]"
    clean_desc = saxutils.escape(desc[:60] + ("..." if len(desc) > 60 else ""))

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">\n'
        f'  <defs>\n'
        f'    <linearGradient id="cardBg" x1="0%" y1="0%" x2="100%" y2="100%">\n'
        f'      <stop offset="0%" stop-color="#242830"/>\n'
        f'      <stop offset="100%" stop-color="#181a20"/>\n'
        f'    </linearGradient>\n'
        f'  </defs>\n'
        f'  <rect width="{w}" height="{h}" fill="url(#cardBg)"/>\n'
        f'  <rect x="4" y="4" width="{max(1, w-8)}" height="{max(1, h-8)}" fill="none" stroke="#E6C280" stroke-width="2" opacity="0.4"/>\n'
        f'  <text x="{w//2}" y="{max(24, h//2 - 10)}" fill="#E6C280" font-family="DejaVu Sans, sans-serif" font-size="{max(14, min(24, w//20))}" font-weight="bold" text-anchor="middle">{saxutils.escape(title)}</text>\n'
        f'  <text x="{w//2}" y="{max(44, h//2 + 20)}" fill="#A0AEC0" font-family="DejaVu Sans, sans-serif" font-size="{max(11, min(16, w//28))}" text-anchor="middle">{clean_desc}</text>\n'
        f'</svg>\n'
    )


class FFmpegRenderer(Renderer):
    """Concrete FFmpeg renderer implementing per-beat isolation + concat."""
    renderer_name: str = "ffmpeg"

    def __init__(self, ffmpeg_bin: str = "ffmpeg", ffprobe_bin: str = "ffprobe"):
        self.ffmpeg_bin = ffmpeg_bin
        self.ffprobe_bin = ffprobe_bin

    def _render_beat_clip(self, beat: BeatFramePlan, work_dir: Path,
                          cache: MediaCache | None, beat_index: int) -> Path:
        """Render one beat into a pinned, byte-compatible MP4 clip."""
        out_clip = work_dir / f"beat_{beat_index:04d}_{beat.beat_id}.mp4"
        duration = max(0.1, beat.duration_sec)
        num_frames = int(round(duration * 30))

        # Inputs array and filtergraph building
        # Input 0: Color canvas base
        inputs: list[str] = [
            "-f", "lavfi",
            "-i", f"color=c=0x141619:s=1920x1080:d={duration:.3f}:r=30",
        ]

        filter_chains: list[str] = []
        current_layer = "[0:v]"
        input_idx = 1

        # Process media elements
        for m_elem in beat.media_elements:
            img_path: Path | None = None
            if cache and m_elem.checksum and not m_elem.is_placeholder:
                img_path = cache.get_path(m_elem.checksum)

            if img_path is None or not img_path.exists():
                # Create a placeholder card SVG
                card_svg = _generate_placeholder_card_svg(
                    desc=m_elem.description or m_elem.element_id,
                    kind=m_elem.media_kind,
                    role=m_elem.role,
                    width=m_elem.bounds_px.width,
                    height=m_elem.bounds_px.height,
                )
                card_path = work_dir / f"placeholder_{beat_index:04d}_{m_elem.element_id.replace(':', '_')}.svg"
                card_path.write_text(card_svg, encoding="utf-8")
                img_path = card_path

            inputs.extend(["-i", str(img_path)])

            w = m_elem.bounds_px.width
            h = m_elem.bounds_px.height
            px_x = m_elem.bounds_px.x
            px_y = m_elem.bounds_px.y

            # Scale and crop to fit the solved rectangle bounds
            scaled_label = f"[m_{input_idx}_scaled]"
            filter_chains.append(
                f"[{input_idx}:v]scale={w}:{h}:force_original_aspect_ratio=increase,"
                f"crop={w}:{h},format=rgba{scaled_label}"
            )

            # Apply Ken Burns subtle zoom on emphasis if requested
            if m_elem.camera_motion in ("KEN_BURNS_ZOOM_IN", "SLOW_PUSH"):
                # Smooth slow zoom in from 1.0 to 1.07
                zoomed_label = f"[m_{input_idx}_zoomed]"
                filter_chains.append(
                    f"{scaled_label}zoompan=z='min(zoom+0.0006,1.07)':d={num_frames}:s={w}x{h}:fps=30{zoomed_label}"
                )
                overlay_src = zoomed_label
            else:
                overlay_src = scaled_label

            next_layer = f"[v_layer_{input_idx}]"
            filter_chains.append(
                f"{current_layer}{overlay_src}overlay={px_x}:{px_y}:eof_action=repeat{next_layer}"
            )
            current_layer = next_layer
            input_idx += 1

        # Process SVG connector overlay if present
        if beat.svg_overlay_content:
            svg_path = work_dir / f"connectors_{beat_index:04d}_{beat.beat_id}.svg"
            svg_path.write_text(beat.svg_overlay_content, encoding="utf-8")
            inputs.extend(["-i", str(svg_path)])

            svg_label = f"[svg_{input_idx}]"
            filter_chains.append(f"[{input_idx}:v]scale=1920:1080,format=rgba{svg_label}")
            next_layer = f"[v_layer_{input_idx}]"
            filter_chains.append(f"{current_layer}{svg_label}overlay=0:0:eof_action=repeat{next_layer}")
            current_layer = next_layer
            input_idx += 1

        # Process per-beat text elements (labels, quotes, timeline dates) via ASS
        if beat.text_elements:
            ass_lines = [
                "[Script Info]",
                "ScriptType: v4.00+",
                "PlayResX: 1920",
                "PlayResY: 1080",
                "WrapStyle: 0",
                "ScaledBorderAndShadow: yes",
                "",
                "[V4+ Styles]",
                "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
                "Style: NodeLabel,DejaVu Sans,26,&H00F9FAFB,&H000000FF,&H00141619,&H90000000,-1,0,0,0,100,100,0,0,1,2,1,5,10,10,10,1",
                "Style: NodeQuote,DejaVu Sans,28,&H00F9FAFB,&H000000FF,&H00141619,&H90000000,0,-1,0,0,100,100,0,0,1,2,1,5,10,10,10,1",
                "Style: NodeTimeline,DejaVu Sans,24,&H0000D1FF,&H000000FF,&H00141619,&H90000000,-1,0,0,0,100,100,0,0,1,2,1,5,10,10,10,1",
                "",
                "[Events]",
                "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
            ]
            for elem in beat.text_elements:
                # Per-beat relative times for this clip
                start_rel = max(0.0, elem.entrance_sec - beat.start_sec)
                end_rel = min(duration, elem.exit_sec - beat.start_sec)
                start_str = f"0:{int(start_rel//60):02d}:{int(start_rel%60):02d}.{int(round((start_rel%1)*100)):02d}"
                end_str = f"0:{int(end_rel//60):02d}:{int(end_rel%60):02d}.{int(round((end_rel%1)*100)):02d}"
                clean_text = escape_ass_text(elem.text)
                pos_tag = f"{{\\an5\\pos({elem.bounds_px.center_x},{elem.bounds_px.center_y})}}"
                ass_lines.append(
                    f"Dialogue: 1,{start_str},{end_str},{elem.style_name},,0,0,0,,{pos_tag}{clean_text}"
                )

            ass_path = work_dir / f"text_{beat_index:04d}_{beat.beat_id}.ass"
            ass_path.write_text("\n".join(ass_lines) + "\n", encoding="utf-8")

            ass_escaped = str(ass_path).replace("\\", "/").replace(":", "\\:")
            next_layer = f"[v_text_{input_idx}]"
            filter_chains.append(f"{current_layer}ass='{ass_escaped}'{next_layer}")
            current_layer = next_layer

        # Final output format filter
        filter_chains.append(f"{current_layer}format=yuv420p[vout]")

        full_filter = ";".join(filter_chains)

        cmd = [
            self.ffmpeg_bin,
            "-y",
            *inputs,
            "-filter_complex", full_filter,
            "-map", "[vout]",
            # Pinned encoding parameters to guarantee 100% byte compatibility across clips for concat
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-profile:v", "high",
            "-level:v", "4.1",
            "-pix_fmt", "yuv420p",
            "-r", "30",
            "-t", f"{duration:.3f}",
            str(out_clip),
        ]

        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            raise RuntimeError(
                f"FFmpeg failed rendering beat {beat.beat_id}:\n"
                f"Command: {' '.join(cmd)}\n"
                f"Stderr: {res.stderr}\n"
            )

        return out_clip

    def render(self, plan: EpisodeFramePlan, output_path: str | Path,
               cache_dir: str | Path | None = None,
               audio: NarrationAudio | None = None) -> RenderResult:
        """Render the complete episode from frame plan with optional narration audio."""
        ok, msg = check_ffmpeg_available()
        if not ok:
            raise RuntimeError(f"FFmpeg build prerequisite check failed: {msg}")

        out_dest = Path(output_path).resolve()
        out_dest.parent.mkdir(parents=True, exist_ok=True)

        if audio is not None:
            if not audio.audio_path.exists():
                raise FileNotFoundError(f"Narration audio file not found: {audio.audio_path}")
            # Pre-mux duration assertion: fail loudly if audio duration and video plan disagree
            dur_delta = abs(float(audio.duration_sec) - float(plan.total_duration_sec))
            if dur_delta > 0.05:
                raise ValueError(
                    f"Audio and video duration mismatch: audio duration is {audio.duration_sec:.3f}s "
                    f"but video frame plan duration is {plan.total_duration_sec:.3f}s "
                    f"(delta: {dur_delta:.3f}s exceeds 0.05s tolerance)"
                )

        cache = MediaCache(cache_dir) if cache_dir else None
        warnings: list[str] = []

        with tempfile.TemporaryDirectory(prefix="vidtool_render_") as tmp_str:
            work_dir = Path(tmp_str)

            # Step 1: Render each beat clip in isolation
            beat_clips: list[Path] = []
            for i, beat in enumerate(plan.beats):
                clip_path = self._render_beat_clip(beat, work_dir, cache, i)
                beat_clips.append(clip_path)

            # Step 2: Lossless concatenation using concat demuxer
            concat_list_file = work_dir / "concat_list.txt"
            concat_entries = [f"file '{clip.resolve()}'" for clip in beat_clips]
            concat_list_file.write_text("\n".join(concat_entries) + "\n", encoding="utf-8")

            raw_concat_mp4 = work_dir / "concat_raw.mp4"
            concat_cmd = [
                self.ffmpeg_bin,
                "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", str(concat_list_file),
                "-c", "copy",
                str(raw_concat_mp4),
            ]
            concat_res = subprocess.run(concat_cmd, capture_output=True, text=True)
            if concat_res.returncode != 0:
                raise RuntimeError(
                    f"FFmpeg concat demuxer failed:\n{concat_res.stderr}"
                )

            # Step 3: Burn in Episode ASS Subtitles and mux Audio onto final MP4
            subtitles_file = work_dir / "episode_subtitles.ass"
            subtitles_file.write_text(plan.subtitles_ass, encoding="utf-8")
            subtitles_escaped = str(subtitles_file).replace("\\", "/").replace(":", "\\:")

            burn_cmd = [
                self.ffmpeg_bin,
                "-y",
                "-i", str(raw_concat_mp4),
            ]
            if audio is not None:
                burn_cmd.extend(["-i", str(audio.audio_path.resolve())])

            burn_cmd.extend([
                "-vf", f"ass='{subtitles_escaped}'",
                "-c:v", "libx264",
                "-preset", "veryfast",
                "-profile:v", "high",
                "-level:v", "4.1",
                "-pix_fmt", "yuv420p",
                "-r", "30",
            ])

            if audio is not None:
                burn_cmd.extend([
                    "-c:a", "aac",
                    "-b:a", "128k",
                    "-ar", "48000",
                    "-ac", "1",
                ])
            else:
                burn_cmd.extend(["-an"])

            burn_cmd.append(str(out_dest))

            burn_res = subprocess.run(burn_cmd, capture_output=True, text=True)
            if burn_res.returncode != 0:
                raise RuntimeError(
                    f"FFmpeg subtitle burn-in / audio mux failed:\n{burn_res.stderr}"
                )

        # Step 4: Validate output with ffprobe
        meta = probe_media_file(out_dest)
        format_info = meta.get("format", {})
        actual_duration = float(format_info.get("duration", 0.0))

        audio_streams = [s for s in meta.get("streams", []) if s.get("codec_type") == "audio"]
        if audio is not None and not audio_streams:
            raise RuntimeError("Render verification failed: expected audio stream in output MP4, but none found")
        elif audio is None and audio_streams:
            raise RuntimeError("Render verification failed: expected no audio stream in output MP4, but audio stream was found")

        return RenderResult(
            output_path=out_dest,
            duration_sec=actual_duration,
            warnings=warnings,
            metadata={
                "streams": len(meta.get("streams", [])),
                "audio_streams": len(audio_streams),
                "format_name": format_info.get("format_name", ""),
                "size_bytes": int(format_info.get("size", 0)),
                "actual_duration_sec": actual_duration,
                "expected_duration_sec": plan.total_duration_sec,
            },
            audio_is_placeholder=audio.is_placeholder if audio else None,
            audio_path=audio.audio_path if audio else None,
        )
