"""Zero-dependency local HTTP server for VideoTool Web UI Dashboard.

Uses Python standard library http.server.ThreadingHTTPServer.
Provides REST endpoints, HTTP 206 partial-content video streaming,
background job execution with real-time log buffers, and static asset serving.
"""
from __future__ import annotations

import datetime
import json
import mimetypes
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.parse
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from videotool.artifacts import ArtifactStore
from videotool.cli import FIXTURES
from videotool.editorial.director.revision import RevisionService


STATIC_DIR = Path(__file__).parent / "static"


class JobState:
    """Thread-safe background job record."""

    def __init__(self, job_id: str, command_desc: str):
        self.job_id = job_id
        self.command_desc = command_desc
        self.status = "running"  # "running" | "completed" | "failed"
        self.exit_code: int | None = None
        self.start_time = time.time()
        self.end_time: float | None = None
        self.logs: list[str] = []
        self.lock = threading.Lock()

    def append_log(self, line: str) -> None:
        with self.lock:
            self.logs.append(line)

    def finish(self, exit_code: int) -> None:
        with self.lock:
            self.exit_code = exit_code
            self.status = "completed" if exit_code == 0 else "failed"
            self.end_time = time.time()

    def get_slice(self, offset: int = 0) -> dict[str, Any]:
        with self.lock:
            lines = self.logs[offset:]
            return {
                "job_id": self.job_id,
                "command_desc": self.command_desc,
                "status": self.status,
                "exit_code": self.exit_code,
                "elapsed_sec": round((self.end_time or time.time()) - self.start_time, 2),
                "lines": lines,
                "next_offset": len(self.logs),
            }


JOBS: dict[str, JobState] = {}
JOBS_LOCK = threading.Lock()


def _get_episode_video_path(artifacts_dir: Path, episode_id: str, fixture_name: str) -> Path | None:
    """Find the rendered video path for an episode."""
    candidates = [
        artifacts_dir / f"{fixture_name}.mp4",
        artifacts_dir / f"{episode_id}.mp4",
        artifacts_dir / episode_id / "rendered_video.mp4",
        artifacts_dir / episode_id / "video.mp4",
        Path("artifacts") / f"{fixture_name}.mp4",
        Path(f"{fixture_name}.mp4"),
    ]
    for c in candidates:
        if c.is_file() and c.stat().st_size > 0:
            return c
    return None


class VideoToolRequestHandler(BaseHTTPRequestHandler):
    """Custom request handler serving REST APIs and static WebUI assets."""

    server_version = "VideoToolWeb/1.0"

    @property
    def store(self) -> ArtifactStore:
        return self.server.store  # type: ignore[attr-defined]

    @property
    def artifacts_root(self) -> Path:
        return self.server.artifacts_root  # type: ignore[attr-defined]

    def log_message(self, format: str, *args: Any) -> None:
        # Keep server quiet on standard console unless needed
        pass

    def _send_json(self, data: Any, status: int = 200) -> None:
        blob = json.dumps(data, indent=2, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(blob)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(blob)

    def _send_error_json(self, message: str, status: int = 400) -> None:
        self._send_json({"error": message, "status": status}, status=status)

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Range")
        self.end_headers()

    def do_GET(self) -> None:
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        query = urllib.parse.parse_qs(parsed_url.query)

        # 1. API: List Episodes
        if path == "/api/episodes":
            self._handle_get_episodes()
            return

        # 2. API: Episode Status
        ep_status_match = re.match(r"^/api/episodes/([^/]+)/status$", path)
        if ep_status_match:
            fixture_name = ep_status_match.group(1)
            self._handle_get_episode_status(fixture_name)
            return

        # 3. API: Shooting Script
        ep_script_match = re.match(r"^/api/episodes/([^/]+)/shooting-script$", path)
        if ep_script_match:
            fixture_name = ep_script_match.group(1)
            self._handle_get_shooting_script(fixture_name)
            return

        # 4. API: Stream Video (HTTP 206 Partial Content Byte Range)
        ep_video_match = re.match(r"^/api/episodes/([^/]+)/video$", path)
        if ep_video_match:
            fixture_name = ep_video_match.group(1)
            self._handle_stream_video(fixture_name)
            return

        # 5. API: Overrides List
        ep_overrides_match = re.match(r"^/api/episodes/([^/]+)/overrides$", path)
        if ep_overrides_match:
            fixture_name = ep_overrides_match.group(1)
            self._handle_get_overrides(fixture_name)
            return

        # 6. API: Media Asset by Checksum
        media_match = re.match(r"^/api/media/([a-f0-9]{64})$", path)
        if media_match:
            checksum = media_match.group(1)
            self._handle_get_media_asset(checksum)
            return

        # 7. API: Job Log Stream Polling
        job_match = re.match(r"^/api/commands/jobs/([^/]+)$", path)
        if job_match:
            job_id = job_match.group(1)
            offset = int(query.get("offset", ["0"])[0])
            self._handle_get_job(job_id, offset)
            return

        # 8. Static Web Assets
        self._handle_static_file(path)

    def do_POST(self) -> None:
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path

        try:
            content_len = int(self.headers.get("Content-Length", 0))
            post_body = self.rfile.read(content_len).decode("utf-8") if content_len > 0 else "{}"
            payload = json.loads(post_body) if post_body else {}
        except Exception as e:
            self._send_error_json(f"Malformed JSON request: {e}", status=400)
            return

        # 1. API: Create Episode for Arbitrary Topic
        if path == "/api/episodes/create":
            self._handle_post_create_episode(payload)
            return

        # 2. API: Propose Revision
        if path == "/api/revise/propose":
            self._handle_post_revise_propose(payload)
            return

        # 3. API: Apply Revision
        if path == "/api/revise/apply":
            self._handle_post_revise_apply(payload)
            return

        # 4. API: Delete Override
        delete_override_match = re.match(r"^/api/episodes/([^/]+)/overrides/delete$", path)
        if delete_override_match:
            fixture_name = delete_override_match.group(1)
            self._handle_post_delete_override(fixture_name, payload)
            return

        # 5. API: Execute Pipeline Command
        if path == "/api/commands/execute":
            self._handle_post_execute_command(payload)
            return

        self._send_error_json(f"Unknown POST endpoint: {path}", status=404)

    # -------------------------------------------------------------------------
    # API Handlers
    # -------------------------------------------------------------------------

    def _handle_get_episodes(self) -> None:
        episodes = []
        seen_ep_ids = set()

        # 1. Built-in fixtures
        for name in sorted(FIXTURES):
            try:
                data = FIXTURES[name]()
                ep_id = data["episode_id"]
                seen_ep_ids.add(ep_id)
                seen_ep_ids.add(name)
                video_path = _get_episode_video_path(self.artifacts_root, ep_id, name)
                has_timeline = (self.store.episode_dir(ep_id) / "timeline.json").is_file()
                has_script = (self.artifacts_root / f"{name}_shooting_script.json").is_file() or (self.store.episode_dir(ep_id) / "shooting_script.json").is_file()
                overrides = self.store.load(ep_id, "editorial_overrides") or []

                episodes.append({
                    "fixture_name": name,
                    "episode_id": ep_id,
                    "title": data.get("title", name.replace("_", " ").title()),
                    "has_timeline": has_timeline,
                    "has_video": video_path is not None,
                    "has_shooting_script": has_script,
                    "overrides_count": len(overrides) if isinstance(overrides, list) else 0,
                    "is_custom": False,
                })
            except Exception:
                continue

        # 2. Custom created projects in artifacts/
        if self.artifacts_root.is_dir():
            for ep_dir in sorted(self.artifacts_root.iterdir()):
                if not ep_dir.is_dir() or ep_dir.name in seen_ep_ids or ep_dir.name.startswith((".", "media_", "tts_", "beat_")):
                    continue
                ep_id = ep_dir.name
                meta_path = ep_dir / "meta.json"
                title = ep_id.replace("_", " ").title()
                if meta_path.is_file():
                    try:
                        meta = json.loads(meta_path.read_text(encoding="utf-8"))
                        title = meta.get("title") or meta.get("topic") or title
                    except Exception:
                        pass

                video_path = _get_episode_video_path(self.artifacts_root, ep_id, ep_id)
                has_timeline = (ep_dir / "timeline.json").is_file()
                has_script = (self.artifacts_root / f"{ep_id}_shooting_script.json").is_file() or (ep_dir / "shooting_script.json").is_file()
                overrides = self.store.load(ep_id, "editorial_overrides") or []

                episodes.append({
                    "fixture_name": ep_id,
                    "episode_id": ep_id,
                    "title": title,
                    "has_timeline": has_timeline,
                    "has_video": video_path is not None,
                    "has_shooting_script": has_script,
                    "overrides_count": len(overrides) if isinstance(overrides, list) else 0,
                    "is_custom": True,
                })

        self._send_json({"episodes": episodes})

    def _handle_get_episode_status(self, fixture_name: str) -> None:
        title = fixture_name.replace("_", " ").title()
        if fixture_name in FIXTURES:
            data = FIXTURES[fixture_name]()
            ep_id = data["episode_id"]
            title = data.get("title", title)
        else:
            ep_id = fixture_name
            meta_path = self.store.episode_dir(ep_id) / "meta.json"
            if meta_path.is_file():
                try:
                    meta = json.loads(meta_path.read_text(encoding="utf-8"))
                    title = meta.get("title") or meta.get("topic") or title
                except Exception:
                    pass

        timeline = self.store.load(ep_id, "timeline") or {}
        duration_sec = timeline.get("total_duration_sec", 0.0)
        beats = self.store.load(ep_id, "semantic_beats") or []
        overrides = self.store.load(ep_id, "editorial_overrides") or []
        video_path = _get_episode_video_path(self.artifacts_root, ep_id, fixture_name)
        audio_path = self.store.episode_dir(ep_id) / "narration_audio.wav"

        script_json_path = self.artifacts_root / f"{fixture_name}_shooting_script.json"
        has_script = script_json_path.is_file() or (self.store.episode_dir(ep_id) / "shooting_script.json").is_file()

        # Visual families breakdown
        families = list({b.get("visual_family", "unknown") for b in beats if isinstance(b, dict)})

        self._send_json({
            "fixture_name": fixture_name,
            "episode_id": ep_id,
            "title": title,
            "total_duration_sec": duration_sec,
            "beat_count": len(beats),
            "visual_families": families,
            "has_timeline": bool(timeline),
            "has_audio": audio_path.is_file(),
            "has_video": video_path is not None,
            "video_path": str(video_path) if video_path else None,
            "video_size_mb": round(video_path.stat().st_size / (1024 * 1024), 2) if video_path else None,
            "has_shooting_script": has_script,
            "overrides_count": len(overrides) if isinstance(overrides, list) else 0,
        })

    def _handle_get_shooting_script(self, fixture_name: str) -> None:
        if fixture_name in FIXTURES:
            data = FIXTURES[fixture_name]()
            ep_id = data["episode_id"]
        else:
            ep_id = fixture_name

        json_path = self.artifacts_root / f"{fixture_name}_shooting_script.json"
        md_path = self.artifacts_root / f"{fixture_name}_shooting_script.md"

        script_data = None
        md_text = ""

        if json_path.is_file():
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    script_data = json.load(f)
            except Exception:
                pass

        if md_path.is_file():
            try:
                md_text = md_path.read_text(encoding="utf-8")
            except Exception:
                pass

        # If not on disk, attempt to generate on-the-fly from current artifacts
        if not script_data:
            timeline = self.store.load(ep_id, "timeline")
            if timeline:
                from videotool.render.frame_plan import build_episode_frame_plan
                from videotool.render.shooting_script import generate_shooting_script

                geo_plans = self.store.load(ep_id, "semantic_geometry") or []
                motion_plan = self.store.load(ep_id, "motion_plan") or {}
                media_assets = self.store.load(ep_id, "media_assets") or []
                visual_comps = self.store.load(ep_id, "visual_compositions") or []
                art_dir = self.store.load(ep_id, "episode_art_direction") or {}
                semantic_beats = self.store.load(ep_id, "semantic_beats") or []
                editorial_intents = self.store.load(ep_id, "editorial_intents") or {}
                editorial_overrides = self.store.load(ep_id, "editorial_overrides") or []

                plan = build_episode_frame_plan(
                    timeline=timeline,
                    geometry_plans=geo_plans,
                    motion_plan=motion_plan,
                    media_assets=media_assets,
                    visual_compositions=visual_comps,
                    art_direction=art_dir,
                    semantic_beats=semantic_beats,
                    editorial_intents=editorial_intents,
                    editorial_overrides=editorial_overrides,
                )

                script_data, md_text = generate_shooting_script(
                    plan=plan,
                    timeline=timeline,
                    semantic_beats=semantic_beats,
                    geometry_plans=geo_plans,
                    media_assets=media_assets,
                    visual_compositions=visual_comps,
                    out_json_path=json_path,
                    out_md_path=md_path,
                )

        if not script_data:
            self._send_error_json("Shooting script not available. Run planning pipeline first.", status=404)
            return

        self._send_json({
            "fixture_name": fixture_name,
            "episode_id": ep_id,
            "script": script_data,
            "markdown": md_text,
        })

    def _handle_post_create_episode(self, payload: dict[str, Any]) -> None:
        """Create and produce a new documentary episode for an arbitrary topic."""
        topic = payload.get("topic", "").strip()
        if not topic:
            self._send_error_json("topic is required", status=400)
            return

        episode_id = payload.get("episode_id", "").strip()
        if not episode_id:
            episode_id = re.sub(r"[^\w\s-]", "", topic.lower())
            episode_id = re.sub(r"[-\s]+", "_", episode_id).strip("_")
            if not episode_id:
                episode_id = f"ep_{int(time.time())}"

        script_text = payload.get("script_text", "").strip()
        media_provider = payload.get("media_provider", "wikimedia")
        audio_provider = payload.get("audio_provider", "silence")
        ai_provider = payload.get("ai_provider", "gemini")
        ai_model = payload.get("ai_model", "gemini-3.1-flash-lite").strip()
        mode = payload.get("mode", "final")
        auto_render = bool(payload.get("auto_render", True))
        voice = payload.get("voice", "vi-VN-HoaiMyNeural")

        job_id = f"job_{int(time.time() * 1000)}_create_{episode_id}"
        desc = f"Auto Vox Pipeline: {topic} ({episode_id})"
        job_state = JobState(job_id=job_id, command_desc=desc)

        with JOBS_LOCK:
            JOBS[job_id] = job_state

        def _worker() -> None:
            active_ai = ai_provider
            active_audio = audio_provider
            job_state.append_log("================================================================================")
            job_state.append_log(f"🚀 AUTO VOX PRODUCTION PIPELINE: {topic}")
            job_state.append_log(f"   Episode ID:     {episode_id}")
            job_state.append_log(f"   Media Provider: {media_provider}")
            job_state.append_log(f"   Audio Provider: {active_audio}")
            job_state.append_log(f"   AI Provider:    {active_ai} (Model: {ai_model if active_ai == 'gemini' else 'default'})")
            job_state.append_log("================================================================================")

            try:
                from videotool.domain.narration import Narration, synthetic_word_timings
                from videotool.pipeline.narration_intake import NarrationIntakeService
                from videotool.pipeline.runner import PipelineRunner, EpisodeInput
                from videotool.editorial.media import MediaAcquisitionConfig
                from videotool.pipeline.policy import ExecutionPolicy

                # 1. Narration Intake
                if not script_text:
                    job_state.append_log(f"📝 [1/4] Đang nghiên cứu & biên soạn kịch bản lời bình với AI ({active_ai} / {ai_model})...")
                    try:
                        intake_svc = NarrationIntakeService(
                            writer_provider_name=active_ai,
                            verifier_provider_name=active_ai,
                            mode=mode,
                            allow_uncertain_claims=True,
                            writer_model=ai_model if active_ai == "gemini" else None,
                            verifier_model=ai_model if active_ai == "gemini" else None,
                        )
                        narration, fact_report = intake_svc.process(topic=topic)
                        job_state.append_log(f"✓ Lời bình hoàn tất: {len(narration.text.split())} từ, {len(fact_report.claims)} sự kiện kiểm chứng")
                    except Exception as e:
                        job_state.append_log(f"⚠️ AI {active_ai} giới hạn quota ({e}). Tự động dùng Heuristic Script để hoàn tất...")
                        intake_svc = NarrationIntakeService(
                            writer_provider_name="mock",
                            verifier_provider_name="mock",
                            mode=mode,
                            allow_uncertain_claims=True,
                        )
                        narration, fact_report = intake_svc.process(topic=topic)
                        active_ai = "mock"
                        job_state.append_log(f"✓ Lời bình hoàn tất: {len(narration.text.split())} từ")
                else:
                    job_state.append_log(f"📝 [1/4] Sử dụng kịch bản lời bình do người dùng nhập ({len(script_text.split())} từ)...")
                    narration = Narration(text=script_text, words=synthetic_word_timings(script_text))

                # 1.5. Azure Speech Synthesis & Alignment (if requested)
                ep_dir = self.store.episode_dir(episode_id)
                ep_dir.mkdir(parents=True, exist_ok=True)

                if active_audio == "azure":
                    job_state.append_log(f"🎙️ [1.5/4] Đang tổng hợp giọng đọc AI Azure Speech ({voice})...")
                    try:
                        import shutil
                        from videotool.providers.azure_speech import synthesize_azure_speech
                        tts_cache_dir = self.artifacts_root / "tts_cache"
                        audio_wav, timing = synthesize_azure_speech(narration, voice=voice, cache_dir=tts_cache_dir)
                        # Update narration with real word-level timings from Azure Speech
                        narration = Narration(text=narration.text, words=timing.words)
                        self.store.save(episode_id, "narration_timing", timing.to_dict())
                        audio_dest = ep_dir / "narration_audio.wav"
                        shutil.copy(audio_wav, audio_dest)
                        job_state.append_log(f"✓ Giọng đọc hoàn tất ({timing.duration_sec:.2f}s, {len(timing.words)} từ)")
                    except Exception as e:
                        job_state.append_log(f"⚠️ Azure Speech error ({e}). Tự động dùng Silence provider...")
                        active_audio = "silence"

                # Save meta.json and narration.json
                meta_data = {
                    "episode_id": episode_id,
                    "topic": topic,
                    "title": topic,
                    "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    "media_provider": media_provider,
                    "audio_provider": active_audio,
                    "ai_model": ai_model,
                }
                (ep_dir / "meta.json").write_text(json.dumps(meta_data, indent=2, ensure_ascii=False), encoding="utf-8")
                self.store.save(episode_id, "narration", narration.to_dict())

                # 2. Planning Pipeline
                job_state.append_log(f"⚙️ [2/4] Chạy Planning Pipeline (Bố cục, Bàn cắt dán, Tư liệu: {media_provider})...")
                media_config = MediaAcquisitionConfig(provider=media_provider)
                policy = ExecutionPolicy(
                    mode=mode,
                    editorial_ai_enabled=True,
                    editorial_ai_provider=active_ai,
                    editorial_ai_model=ai_model if active_ai == "gemini" else None,
                )
                runner = PipelineRunner(self.store, policy=policy, media_config=media_config)
                ep_input = EpisodeInput(
                    episode_id=episode_id,
                    subject=topic,
                    narration=narration,
                    catalog=[],
                )
                try:
                    res = runner.run(ep_input)
                except Exception as run_err:
                    job_state.append_log(f"⚠️ Lỗi xử lý AI ({run_err}). Tự động chuyển sang Mock Editorial để hoàn thành...")
                    policy = ExecutionPolicy(
                        mode=mode,
                        editorial_ai_enabled=True,
                        editorial_ai_provider="mock",
                    )
                    runner = PipelineRunner(self.store, policy=policy, media_config=media_config)
                    res = runner.run(ep_input)
                job_state.append_log(f"✓ Planning hoàn tất: {len(res.beats)} Beats, {len(res.compositions)} Visual Compositions (Status: {res.ok})")

                # 3. Generate Shooting Script
                job_state.append_log("📋 [3/4] Xuất Shooting Script 13 cột (JSON & Markdown)...")
                from videotool.render.frame_plan import build_episode_frame_plan
                from videotool.render.shooting_script import generate_shooting_script

                timeline = self.store.load(episode_id, "timeline")
                geo_plans = self.store.load(episode_id, "semantic_geometry") or []
                motion_plan = self.store.load(episode_id, "motion_plan") or {}
                media_assets = self.store.load(episode_id, "media_assets") or []
                visual_comps = self.store.load(episode_id, "visual_compositions") or []
                art_dir = self.store.load(episode_id, "episode_art_direction") or {}
                semantic_beats = self.store.load(episode_id, "semantic_beats") or []
                editorial_intents = self.store.load(episode_id, "editorial_intents") or {}
                editorial_overrides = self.store.load(episode_id, "editorial_overrides") or []

                plan = build_episode_frame_plan(
                    timeline=timeline,
                    geometry_plans=geo_plans,
                    motion_plan=motion_plan,
                    media_assets=media_assets,
                    visual_compositions=visual_comps,
                    art_direction=art_dir,
                    semantic_beats=semantic_beats,
                    editorial_intents=editorial_intents,
                    editorial_overrides=editorial_overrides,
                )
                json_path = self.artifacts_root / f"{episode_id}_shooting_script.json"
                md_path = self.artifacts_root / f"{episode_id}_shooting_script.md"
                generate_shooting_script(plan, timeline, semantic_beats, geo_plans, media_assets, visual_comps, json_path, md_path)
                job_state.append_log(f"✓ Shooting script đã xuất: {json_path.name}")

                # 4. Optional Render
                if auto_render:
                    job_state.append_log("🎬 [4/4] Render Video MP4 phong cách Vox (FFmpeg & Beat Cache)...")
                    from videotool.render import render_episode
                    out_mp4 = self.artifacts_root / f"{episode_id}.mp4"
                    render_res = render_episode(
                        episode_id=episode_id,
                        store=self.store,
                        output_path=out_mp4,
                        audio_provider_name=audio_provider if audio_provider != "none" else None,
                        voice=voice,
                    )
                    job_state.append_log(f"🎉 RENDER HOÀN TẤT: {out_mp4.name} (Thời lượng: {render_res.duration_sec:.2f}s, Beats: {render_res.metadata.get('beats_rendered')})")

                job_state.append_log("================================================================================")
                job_state.append_log(f"✨ TẬP PHIM ĐÃ SẴN SÀNG! Vui lòng chọn '{episode_id}' trên thanh menu để xem.")
                job_state.append_log("================================================================================")
                job_state.finish(0)
            except Exception as e:
                import traceback
                job_state.append_log(f"❌ Pipeline failed: {e}")
                job_state.append_log(traceback.format_exc())
                job_state.finish(1)

        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()

        self._send_json({"success": True, "episode_id": episode_id, "job_id": job_id})

    def _handle_stream_video(self, fixture_name: str) -> None:
        """Stream video MP4 file with HTTP 206 Partial Content Byte Range support."""
        if fixture_name in FIXTURES:
            ep_id = FIXTURES[fixture_name]()["episode_id"]
        else:
            ep_id = fixture_name

        video_path = _get_episode_video_path(self.artifacts_root, ep_id, fixture_name)

        if not video_path or not video_path.is_file():
            self._send_error_json(f"Rendered video for '{fixture_name}' not found. Run render first.", status=404)
            return

        file_size = video_path.stat().st_size
        range_header = self.headers.get("Range")

        if range_header:
            range_match = re.search(r"bytes=(\d+)-(\d*)", range_header)
            if range_match:
                start = int(range_match.group(1))
                end = int(range_match.group(2)) if range_match.group(2) else file_size - 1
                end = min(end, file_size - 1)
                length = end - start + 1

                self.send_response(HTTPStatus.PARTIAL_CONTENT)
                self.send_header("Content-Type", "video/mp4")
                self.send_header("Accept-Ranges", "bytes")
                self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
                self.send_header("Content-Length", str(length))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()

                with open(video_path, "rb") as f:
                    f.seek(start)
                    remaining = length
                    while remaining > 0:
                        chunk_size = min(64 * 1024, remaining)
                        chunk = f.read(chunk_size)
                        if not chunk:
                            break
                        self.wfile.write(chunk)
                        remaining -= len(chunk)
                return

        # Full file streaming
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "video/mp4")
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(file_size))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        with open(video_path, "rb") as f:
            shutil.copyfileobj(f, self.wfile)

    def _handle_get_overrides(self, fixture_name: str) -> None:
        if fixture_name in FIXTURES:
            ep_id = FIXTURES[fixture_name]()["episode_id"]
        else:
            ep_id = fixture_name

        overrides = self.store.load(ep_id, "editorial_overrides") or []
        self._send_json({"episode_id": ep_id, "overrides": overrides})

    def _handle_get_media_asset(self, checksum: str) -> None:
        prefix = checksum[:2]
        media_dir = self.artifacts_root / "media_cache" / prefix
        if media_dir.is_dir():
            for p in media_dir.glob(f"{checksum}.*"):
                if p.suffix != ".json":
                    mime, _ = mimetypes.guess_type(str(p))
                    self.send_response(HTTPStatus.OK)
                    self.send_header("Content-Type", mime or "image/jpeg")
                    self.send_header("Content-Length", str(p.stat().st_size))
                    self.send_header("Cache-Control", "public, max-age=86400")
                    self.end_headers()
                    with open(p, "rb") as f:
                        shutil.copyfileobj(f, self.wfile)
                    return

        self._send_error_json(f"Media asset '{checksum}' not found in cache", status=404)

    def _handle_get_job(self, job_id: str, offset: int) -> None:
        with JOBS_LOCK:
            job = JOBS.get(job_id)
        if not job:
            self._send_error_json(f"Job '{job_id}' not found", status=404)
            return
        self._send_json(job.get_slice(offset))

    def _handle_post_revise_propose(self, payload: dict[str, Any]) -> None:
        fixture_name = payload.get("fixture") or (next(iter(FIXTURES)) if FIXTURES else "")
        feedback_text = payload.get("feedback_text", "").strip()
        provider = payload.get("provider", "mock")

        if fixture_name in FIXTURES:
            ep_id = FIXTURES[fixture_name]()["episode_id"]
        elif (self.store.episode_dir(fixture_name)).is_dir():
            ep_id = fixture_name
        else:
            self._send_error_json(f"Episode '{fixture_name}' not found", status=404)
            return

        if not feedback_text:
            self._send_error_json("feedback_text is required", status=400)
            return

        try:
            service = RevisionService(provider_name=provider)
            proposal = service.propose_revision(
                episode_id=ep_id,
                feedback_text=feedback_text,
                store=self.store,
            )
            self._send_json(proposal.to_dict())
        except Exception as exc:
            self._send_error_json(f"Revision error: {exc}", status=500)

    def _handle_post_revise_apply(self, payload: dict[str, Any]) -> None:
        fixture_name = payload.get("fixture") or (next(iter(FIXTURES)) if FIXTURES else "")
        proposal_id = payload.get("proposal_id", "").strip()

        if fixture_name in FIXTURES:
            ep_id = FIXTURES[fixture_name]()["episode_id"]
        elif (self.store.episode_dir(fixture_name)).is_dir():
            ep_id = fixture_name
        else:
            self._send_error_json(f"Episode '{fixture_name}' not found", status=404)
            return

        if not proposal_id:
            self._send_error_json("proposal_id is required", status=400)
            return

        try:
            service = RevisionService(provider_name="mock")
            overrides = service.apply_revision(
                episode_id=ep_id,
                proposal_id=proposal_id,
                store=self.store,
            )
            self._send_json({"success": True, "proposal_id": proposal_id, "overrides": overrides})
        except Exception as exc:
            self._send_error_json(f"Apply error: {exc}", status=500)

    def _handle_post_delete_override(self, fixture_name: str, payload: dict[str, Any]) -> None:
        if fixture_name in FIXTURES:
            ep_id = FIXTURES[fixture_name]()["episode_id"]
        else:
            ep_id = fixture_name

        override_id = payload.get("override_id")
        if not override_id:
            self._send_error_json("override_id is required", status=400)
            return

        overrides = self.store.load(ep_id, "editorial_overrides") or []
        new_overrides = [ovr for ovr in overrides if ovr.get("override_id") != override_id]
        self.store.save(ep_id, "editorial_overrides", new_overrides)
        self._send_json({"success": True, "remaining_count": len(new_overrides), "overrides": new_overrides})

    def _handle_post_execute_command(self, payload: dict[str, Any]) -> None:
        """Spawn background process to execute pipeline or render command."""
        command_type = payload.get("command", "plan")  # "plan" | "render" | "shooting-script"
        fixture_name = payload.get("fixture") or (next(iter(FIXTURES)) if FIXTURES else "")
        options = payload.get("options", {})

        if fixture_name not in FIXTURES:
            self._send_error_json(f"Fixture '{fixture_name}' not found", status=400)
            return

        job_id = f"job_{int(time.time() * 1000)}_{command_type}"
        desc = f"CLI {command_type} on {fixture_name}"
        job_state = JobState(job_id=job_id, command_desc=desc)

        with JOBS_LOCK:
            JOBS[job_id] = job_state

        cmd_args = [sys.executable, "-m", "videotool.cli"]

        if command_type == "plan":
            cmd_args.extend([fixture_name])
            if options.get("mode"):
                cmd_args.extend(["--mode", options["mode"]])
            if options.get("editorial_ai_enabled"):
                cmd_args.append("--editorial-ai-enabled")
            if options.get("media_provider"):
                cmd_args.extend(["--media-provider", options["media_provider"]])

        elif command_type == "render":
            cmd_args.extend(["render", fixture_name])
            if options.get("no_audio"):
                cmd_args.append("--no-audio")
            elif options.get("audio_provider"):
                cmd_args.extend(["--audio-provider", options["audio_provider"]])
            if options.get("click_track"):
                cmd_args.append("--click-track")
            if options.get("voice"):
                cmd_args.extend(["--voice", options["voice"]])

        elif command_type == "shooting-script":
            cmd_args.extend(["shooting-script", fixture_name])

        else:
            self._send_error_json(f"Unsupported command '{command_type}'", status=400)
            return

        def _worker() -> None:
            job_state.append_log(f"$ {' '.join(cmd_args)}")
            try:
                proc = subprocess.Popen(
                    cmd_args,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                )
                if proc.stdout:
                    for line in iter(proc.stdout.readline, ""):
                        if line:
                            job_state.append_log(line.rstrip("\r\n"))
                proc.wait()
                job_state.finish(proc.returncode)
            except Exception as e:
                job_state.append_log(f"Execution failed: {e}")
                job_state.finish(1)

        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()

        self._send_json({"job_id": job_id, "command_desc": desc})

    def _handle_static_file(self, req_path: str) -> None:
        """Serve index.html, CSS, and JS from static directory."""
        if req_path in ("/", ""):
            file_path = STATIC_DIR / "index.html"
        else:
            rel = req_path.lstrip("/")
            file_path = STATIC_DIR / rel

        if not file_path.is_file():
            self._send_error_json(f"Static file not found: {req_path}", status=404)
            return

        mime, _ = mimetypes.guess_type(str(file_path))
        if file_path.suffix == ".css":
            mime = "text/css"
        elif file_path.suffix == ".js":
            mime = "application/javascript"
        elif file_path.suffix == ".html":
            mime = "text/html; charset=utf-8"

        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", mime or "application/octet-stream")
        self.send_header("Content-Length", str(file_path.stat().st_size))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()

        with open(file_path, "rb") as f:
            shutil.copyfileobj(f, self.wfile)


def create_web_server(
    host: str = "127.0.0.1",
    port: int = 8080,
    artifacts_dir: str | Path = "artifacts",
) -> ThreadingHTTPServer:
    """Instantiate a ThreadingHTTPServer configured for VideoTool."""
    ThreadingHTTPServer.allow_reuse_address = True
    server_address = (host, port)
    server = ThreadingHTTPServer(server_address, VideoToolRequestHandler)
    server.artifacts_root = Path(artifacts_dir).resolve()  # type: ignore[attr-defined]
    server.store = ArtifactStore(server.artifacts_root)    # type: ignore[attr-defined]
    return server


def run_web_server(
    host: str = "127.0.0.1",
    port: int = 8080,
    artifacts_dir: str | Path = "artifacts",
    open_browser: bool = False,
) -> None:
    """Run the web server synchronously until interrupted."""
    try:
        server = create_web_server(host=host, port=port, artifacts_dir=artifacts_dir)
    except OSError as exc:
        if getattr(exc, "errno", None) == 98 or "Address already in use" in str(exc):
            url = f"http://{host}:{port}/"
            print("================================================================================")
            print("                    VIDEOTOOL LOCAL WEB UI DASHBOARD")
            print("================================================================================")
            print(f"  [INFO] Web server is ALREADY running at: {url}")
            print(f"  Open {url} in your browser to view the dashboard.")
            print("================================================================================")
            if open_browser:
                try:
                    import webbrowser
                    webbrowser.open(url)
                except Exception:
                    pass
            return
        raise

    url = f"http://{host}:{port}/"
    print("================================================================================")
    print("                    VIDEOTOOL LOCAL WEB UI DASHBOARD")
    print("================================================================================")
    print(f"  Server URL:    {url}")
    print(f"  Artifacts:     {server.artifacts_root}")  # type: ignore[attr-defined]
    print(f"  Active Host:   {host}:{port}")
    print("  Press Ctrl+C to stop the server.")
    print("================================================================================")

    if open_browser:
        try:
            import webbrowser
            webbrowser.open(url)
        except Exception:
            pass

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping VideoTool Web UI server...")
    finally:
        server.server_close()
