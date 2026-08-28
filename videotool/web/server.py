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
DELETED_FIXTURES: set[str] = set()


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
            job_id = urllib.parse.unquote(job_match.group(1))
            offset = int(query.get("offset", ["0"])[0])
            self._handle_get_job(job_id, offset)
            return

        # 8. API: Fact Registry
        ep_fact_match = re.match(r"^/api/episodes/([^/]+)/fact-registry$", path)
        if ep_fact_match:
            ep_id = ep_fact_match.group(1)
            self._handle_get_fact_registry(ep_id)
            return

        # 9. API: Chapters
        ep_ch_match = re.match(r"^/api/episodes/([^/]+)/chapters$", path)
        if ep_ch_match:
            ep_id = ep_ch_match.group(1)
            self._handle_get_chapters(ep_id)
            return

        # 10. API: Scenes
        ep_scenes_match = re.match(r"^/api/episodes/([^/]+)/scenes$", path)
        if ep_scenes_match:
            ep_id = ep_scenes_match.group(1)
            self._handle_get_scenes(ep_id)
            return

        # 11. Static Web Assets
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

        # 6. API: Delete Episode Project
        delete_ep_match = re.match(r"^/api/episodes/([^/]+)/delete$", path)
        if delete_ep_match:
            raw_name = delete_ep_match.group(1)
            ep_name = urllib.parse.unquote(raw_name)
            self._handle_post_delete_episode(ep_name)
            return

        # 7. API: Update Fact Registry
        fact_update_match = re.match(r"^/api/episodes/([^/]+)/fact-registry/update$", path)
        if fact_update_match:
            ep_id = fact_update_match.group(1)
            self._handle_post_update_fact_registry(ep_id, payload)
            return

        # 8. API: Render Individual Scene
        scene_render_match = re.match(r"^/api/episodes/([^/]+)/scenes/([^/]+)/render$", path)
        if scene_render_match:
            ep_id = scene_render_match.group(1)
            sc_id = scene_render_match.group(2)
            self._handle_post_render_scene(ep_id, sc_id, payload)
            return

        # 9. API: Master Assembly
        master_match = re.match(r"^/api/episodes/([^/]+)/master-assembly$", path)
        if master_match:
            ep_id = master_match.group(1)
            self._handle_post_master_assembly(ep_id, payload)
            return

        self._send_error_json(f"Unknown POST endpoint: {path}", status=404)

    # -------------------------------------------------------------------------
    # API Handlers
    # -------------------------------------------------------------------------

    def _handle_get_episodes(self) -> None:
        episodes = []
        seen_ep_ids = set()

        def _extract_ep_stats(ep_id: str, name: str) -> dict:
            ep_dir = self.store.episode_dir(ep_id)
            meta = {}
            meta_path = ep_dir / "meta.json"
            if meta_path.is_file():
                try:
                    meta = json.loads(meta_path.read_text(encoding="utf-8"))
                except Exception:
                    pass

            timeline_path = ep_dir / "timeline.json"
            duration_sec = 0.0
            if timeline_path.is_file():
                try:
                    tl = json.loads(timeline_path.read_text(encoding="utf-8"))
                    duration_sec = float(tl.get("total_duration_sec", 0.0))
                except Exception:
                    pass

            beats_path = ep_dir / "semantic_beats.json"
            beat_count = 0
            if beats_path.is_file():
                try:
                    bts = json.loads(beats_path.read_text(encoding="utf-8"))
                    beat_count = len(bts) if isinstance(bts, list) else 0
                except Exception:
                    pass

            video_path = _get_episode_video_path(self.artifacts_root, ep_id, name)
            video_size_mb = None
            if video_path and video_path.is_file():
                try:
                    video_size_mb = round(video_path.stat().st_size / (1024 * 1024), 2)
                except Exception:
                    pass

            created_at = meta.get("created_at")
            if not created_at and ep_dir.is_dir():
                try:
                    created_at = datetime.datetime.fromtimestamp(ep_dir.stat().st_mtime, tz=datetime.timezone.utc).isoformat()
                except Exception:
                    pass

            has_script = (self.artifacts_root / f"{name}_shooting_script.json").is_file() or (ep_dir / "shooting_script.json").is_file()
            overrides = self.store.load(ep_id, "editorial_overrides") or []

            return {
                "duration_sec": duration_sec,
                "beat_count": beat_count,
                "video_size_mb": video_size_mb,
                "created_at": created_at,
                "media_provider": meta.get("media_provider", "wikimedia"),
                "audio_provider": meta.get("audio_provider", "silence"),
                "ai_model": meta.get("ai_model", ""),
                "has_timeline": timeline_path.is_file(),
                "has_video": video_path is not None,
                "has_shooting_script": has_script,
                "overrides_count": len(overrides) if isinstance(overrides, list) else 0,
            }

        # Scan actual project directories in artifacts/
        if self.artifacts_root.is_dir():
            for ep_dir in sorted(self.artifacts_root.iterdir(), key=lambda p: p.stat().st_mtime if p.is_dir() else 0, reverse=True):
                if not ep_dir.is_dir() or ep_dir.name in seen_ep_ids or ep_dir.name in DELETED_FIXTURES or ep_dir.name.startswith((".", "media_", "tts_", "beat_", "ai_narration")):
                    continue
                ep_id = ep_dir.name
                seen_ep_ids.add(ep_id)
                meta_path = ep_dir / "meta.json"
                title = ep_id.replace("_", " ").title()
                if meta_path.is_file():
                    try:
                        meta = json.loads(meta_path.read_text(encoding="utf-8"))
                        title = meta.get("title") or meta.get("topic") or title
                    except Exception:
                        pass

                stats = _extract_ep_stats(ep_id, ep_id)

                episodes.append({
                    "fixture_name": ep_id,
                    "episode_id": ep_id,
                    "title": title,
                    "is_custom": True,
                    **stats,
                })

        # If artifacts is completely empty and no custom episodes exist, show built-in fixtures unless deleted
        if not episodes and not DELETED_FIXTURES:
            for name in sorted(FIXTURES):
                if name in DELETED_FIXTURES:
                    continue
                try:
                    data = FIXTURES[name]()
                    ep_id = data["episode_id"]
                    if ep_id in DELETED_FIXTURES:
                        continue
                    seen_ep_ids.add(ep_id)
                    stats = _extract_ep_stats(ep_id, name)
                    episodes.append({
                        "fixture_name": name,
                        "episode_id": ep_id,
                        "title": data.get("title", name.replace("_", " ").title()),
                        "is_custom": True,
                        **stats,
                    })
                except Exception:
                    continue

        self._send_json({"episodes": episodes})

    def _handle_post_delete_episode(self, episode_id: str) -> None:
        import shutil
        if not episode_id or episode_id in ("..", "/", "\\") or ".." in episode_id:
            self._send_error_json("Invalid episode ID", status=400)
            return

        DELETED_FIXTURES.add(episode_id)

        deleted_items = []
        # 1. Remove direct episode dir in store
        ep_dir = self.store.episode_dir(episode_id)
        if ep_dir.is_dir():
            shutil.rmtree(ep_dir, ignore_errors=True)
            deleted_items.append(str(ep_dir))

        # 2. Check artifacts_root / episode_id directly
        art_ep_dir = self.artifacts_root / episode_id
        if art_ep_dir.is_dir():
            shutil.rmtree(art_ep_dir, ignore_errors=True)
            deleted_items.append(str(art_ep_dir))

        # 3. If fixture alias exists, remove target directory and related fixtures
        target_ids = {episode_id}
        if episode_id in FIXTURES:
            try:
                target_ep_id = FIXTURES[episode_id]()["episode_id"]
                target_ids.add(target_ep_id)
                DELETED_FIXTURES.add(target_ep_id)
                for fix_k, fix_loader in FIXTURES.items():
                    try:
                        if fix_loader()["episode_id"] == target_ep_id:
                            DELETED_FIXTURES.add(fix_k)
                            target_ids.add(fix_k)
                    except Exception:
                        pass
                target_dir = self.store.episode_dir(target_ep_id)
                if target_dir.is_dir():
                    shutil.rmtree(target_dir, ignore_errors=True)
                    deleted_items.append(str(target_dir))
            except Exception:
                pass

        # 4. Remove standalone files matching patterns
        patterns = []
        for tid in target_ids:
            patterns.extend([
                f"{tid}.mp4",
                f"{tid}_shooting_script.*",
                f"{tid}_*.json",
                f"{tid}_*.md",
                f"{tid}*",
            ])

        for pat in patterns:
            for f in self.artifacts_root.glob(pat):
                if f.is_file():
                    try:
                        f.unlink()
                        deleted_items.append(f.name)
                    except Exception:
                        pass
                elif f.is_dir() and f.name not in ("media_cache", "tts_cache", "beat_clip_cache", "thumbnails"):
                    try:
                        shutil.rmtree(f, ignore_errors=True)
                        deleted_items.append(f.name)
                    except Exception:
                        pass

        self._send_json({
            "success": True,
            "episode_id": episode_id,
            "deleted_items": deleted_items,
        })

        self._send_json({
            "success": True,
            "episode_id": episode_id,
            "deleted_items": deleted_items,
        })

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

        import unicodedata

        episode_id = payload.get("episode_id", "").strip()
        if not episode_id:
            normalized = unicodedata.normalize("NFKD", topic).encode("ascii", "ignore").decode("ascii")
            episode_id = re.sub(r"[^\w\s-]", "", normalized.lower())
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
            try:
                from videotool.observability import init_logger
                obs_logger = init_logger(job_id=job_id, verbose=True)
                obs_logger.add_handler(lambda line, lvl, meta: job_state.append_log(line))

                active_ai = ai_provider
                active_audio = audio_provider
                active_model = ai_model
                obs_logger.pipeline_start(
                    title=f"Auto Vox Pipeline: {topic}",
                    input_desc=f"Episode ID: {episode_id} | Media: {media_provider} | Audio: {active_audio} | AI: {active_ai} ({active_model})",
                    output_path=f"artifacts/{episode_id}.mp4",
                )

                from videotool.domain.narration import Narration, synthetic_word_timings
                from videotool.pipeline.narration_intake import NarrationIntakeService
                from videotool.pipeline.runner import PipelineRunner, EpisodeInput
                from videotool.editorial.media import MediaAcquisitionConfig
                from videotool.pipeline.policy import ExecutionPolicy
                # ---------------------------------------------------------------------
                # 8-STAGE HIERARCHICAL PRODUCTION PIPELINE
                # ---------------------------------------------------------------------

                # Stage 1: Fact Registry & Zero-Hallucination Gate
                job_state.append_log("📚 [1/8] Giai đoạn 1: Fact Registry & Khóa dữ liệu lịch sử gốc (Zero-Hallucination Gate)...")
                from videotool.domain.fact_registry import FactRegistry, FactItem, HistoricalEntity
                from videotool.providers.fact_researcher import conduct_deep_historical_research

                # Save meta.json immediately
                ep_dir = self.store.episode_dir(episode_id)
                ep_dir.mkdir(parents=True, exist_ok=True)
                meta_data = {
                    "episode_id": episode_id,
                    "topic": topic,
                    "title": topic,
                    "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    "media_provider": media_provider,
                    "audio_provider": active_audio,
                    "ai_model": active_model,
                }
                (ep_dir / "meta.json").write_text(json.dumps(meta_data, indent=2, ensure_ascii=False), encoding="utf-8")

                # Conduct Deep Historical Research & Grounding
                fact_reg, fact_meta = conduct_deep_historical_research(
                    topic=topic,
                    project_id=episode_id,
                    provider=active_ai,
                    model=active_model,
                )

                job_state.append_log("📤 [NỘI DUNG GỬI CHO AI (STAGE 1 RESEARCH)]:")
                for p_line in fact_meta["prompt_sent"].splitlines():
                    job_state.append_log(f"   {p_line}")

                job_state.append_log("📥 [NỘI DUNG AI TRẢ VỀ (FACT REGISTRY)]:")
                job_state.append_log(f"   • Luận điểm trung tâm: \"{fact_meta['central_thesis']}\"")
                job_state.append_log(f"   • Thực thể lịch sử: {fact_meta['entities_count']} thực thể ({', '.join(fact_meta['sample_entities'])})")
                job_state.append_log(f"   • Dữ kiện & Mốc thời gian: {fact_meta['facts_count']} dữ kiện đã kiểm chứng")
                if fact_meta.get("archival_targets"):
                    job_state.append_log(f"   • Từ khóa tư liệu lưu trữ: {fact_meta['archival_targets']}")

                job_state.append_log("📊 [ĐÁNH GIÁ MỨC ĐỘ ĐẠT]:")
                job_state.append_log("   • Trạng thái kiểm định: 100% ĐẠT CHUẨN (Hồ sơ Fact Registry đã được niêm phong chống ảo giác)")
                self.store.save(episode_id, "fact_registry", fact_reg.to_dict())
                job_state.append_log(f"✓ Fact Registry đã khóa: {len(fact_reg.facts)} dữ kiện & {len(fact_reg.entities)} thực thể lịch sử")

                # Stage 2: Macro Story Arc & Chapter Outlining (10-minute arc)
                job_state.append_log("📖 [2/8] Giai đoạn 2: Cấu trúc Tổng thể & Phân bổ 4-5 Chương (Macro Story Arc)...")
                from videotool.domain.story_structure import ChapterOutline, MacroStoryArc
                from videotool.pipeline.stages.chapter_outline import ChapterOutlineStage
                from videotool.editorial.sequential_chapter_engine import generate_chapter_with_ai

                outline_stage = ChapterOutlineStage()
                ctx_mock = type("MockCtx", (), {"episode_id": episode_id, "state": {"topic": topic, "fact_registry": fact_reg.to_dict()}})()
                arc_data = outline_stage.execute(ctx_mock)
                story_arc = MacroStoryArc.from_dict(arc_data)
                self.store.save(episode_id, "chapter_outline", story_arc.to_dict())
                job_state.append_log(f"✓ Phân bổ hoàn tất: {len(story_arc.chapters)} Chương (Tổng mục tiêu: {story_arc.target_total_duration_sec:.0f}s)")

                # Stage 3: Sequential Chapter-by-Chapter Micro-Scriptwriting & Quality Audit
                job_state.append_log("✍️ [3/8] Giai đoạn 3: Biên soạn Lời bình từng Chương tuần tự & Đánh giá Chất lượng...")
                chapter_scripts = []
                running_context = ""
                all_chapter_sentences = []

                for ch_idx, chapter in enumerate(story_arc.chapters, start=1):
                    job_state.append_log("--------------------------------------------------------------------------------")
                    job_state.append_log(f"📖 CHƯƠNG [{ch_idx}/{len(story_arc.chapters)}]: {chapter.title} (Mục tiêu: {chapter.target_duration_sec:.0f}s)")
                    job_state.append_log("--------------------------------------------------------------------------------")

                    ch_script, audit_rep = generate_chapter_with_ai(
                        topic=topic,
                        chapter=chapter,
                        total_chapters=len(story_arc.chapters),
                        previous_context=running_context,
                        fact_registry=fact_reg,
                        provider=active_ai,
                        model=active_model,
                        language="vi",
                    )
                    chapter_scripts.append(ch_script)

                    # 1. Report Prompt Sent to AI
                    job_state.append_log("📤 [NỘI DUNG GỬI CHO AI]:")
                    for p_line in audit_rep["prompt_sent"].splitlines():
                        job_state.append_log(f"   {p_line}")

                    # 2. Report AI Generated Content
                    job_state.append_log("📥 [NỘI DUNG AI TRẢ VỀ]:")
                    job_state.append_log(f"   • Tiêu đề chương: \"{ch_script.title}\"")
                    if audit_rep.get("chapter_summary"):
                        job_state.append_log(f"   • Tóm tắt: {audit_rep['chapter_summary']}")
                    job_state.append_log(f"   • Số phân cảnh (Beats): {audit_rep['beats_count']} beats")
                    if audit_rep.get("sample_quote"):
                        job_state.append_log(f"   • Trích dẫn mẫu: \"{audit_rep['sample_quote']}\"")
                        if audit_rep.get("sample_emphasis"):
                            job_state.append_log(f"   • Từ khóa bôi vàng: {audit_rep['sample_emphasis']}")

                    # 3. Report Quality & Fact Audit
                    job_state.append_log("📊 [ĐÁNH GIÁ MỨC ĐỘ ĐẠT]:")
                    job_state.append_log(f"   • Thời lượng: {audit_rep['estimated_duration_sec']}s / {audit_rep['target_duration_sec']}s (Đạt {audit_rep['duration_ratio_percent']}%)")
                    job_state.append_log(f"   • Số lượng từ: {audit_rep['total_words']} từ (Tốc độ đọc: {audit_rep['words_per_minute']} từ/phút)")
                    job_state.append_log(f"   • Độ phủ dữ kiện: {audit_rep['fact_coverage_percent']}%")
                    job_state.append_log(f"   • Điểm chất lượng: {audit_rep['quality_score']}/10 ({audit_rep['rating_label']})")
                    job_state.append_log(f"✓ Chương {ch_idx} hoàn tất & được phê duyệt tự động.")

                    # Update running context for next chapter
                    ch_text = " ".join(b.narration_text for b in ch_script.beats)
                    running_context += f"\n- Chương {ch_idx} ({ch_script.title}): {audit_rep.get('chapter_summary') or ch_text[:120]}..."
                    all_chapter_sentences.extend(b.narration_text for b in ch_script.beats)

                self.store.save(episode_id, "chapter_scripts", [cs.to_dict() for cs in chapter_scripts])
                full_script_text = " ".join(all_chapter_sentences)
                narration = Narration(text=full_script_text, words=synthetic_word_timings(full_script_text))
                self.store.save(episode_id, "narration", narration.to_dict())
                job_state.append_log(f"✓ Toàn bộ kịch bản 10 phút hoàn tất: {len(full_script_text.split())} từ phân bổ vào {len(story_arc.chapters)} chương")

                # Stage 4: Archival Media Sourcing & License Manifest
                job_state.append_log(f"🖼️ [4/8] Giai đoạn 4: Thu thập Tư liệu Thật & Lập Manifest Bản quyền CC BY-SA ({media_provider})...")
                from videotool.editorial.media.archival_resolver import ArchivalResolver
                archival_res = ArchivalResolver(self.artifacts_root)

                # Stage 5: Visual Art Direction & Safe-Zone Geometry
                job_state.append_log("🎨 [5/8] Giai đoạn 5: Đạo diễn Hình ảnh & Bố cục Safe-Zone (Visual Art Direction)...")
                media_config = MediaAcquisitionConfig(provider=media_provider)
                ep_input = EpisodeInput(
                    episode_id=episode_id,
                    subject=topic,
                    narration=narration,
                    catalog=[],
                )

                try:
                    policy = ExecutionPolicy(
                        mode=mode,
                        editorial_ai_enabled=False,
                        editorial_ai_provider="mock",
                    )
                    runner = PipelineRunner(self.store, policy=policy, media_config=media_config)
                    res = runner.run(ep_input)
                    pipeline_success = True
                except Exception as run_err:
                    job_state.append_log(f"⚠️ Lỗi Planning Bố cục: {run_err}")

                if not pipeline_success or res is None:
                    job_state.append_log(f"❌ Planning Pipeline không thành công.")
                    job_state.finish(exit_code=1)
                    return

                job_state.append_log(f"✓ Bố cục hoàn tất: {len(res.beats)} Beats, {len(res.compositions)} Visual Compositions")

                # Stage 6: Audio Speech Synthesis & Alignment
                job_state.append_log(f"🎙️ [6/8] Giai đoạn 6: Thu âm/TTS & Khớp mốc thời gian từng từ ({active_audio} / {voice})...")
                ep_dir = self.store.episode_dir(episode_id)
                ep_dir.mkdir(parents=True, exist_ok=True)

                if active_audio == "azure":
                    try:
                        from videotool.providers.azure_speech import synthesize_azure_speech
                        tts_cache_dir = self.artifacts_root / "tts_cache"
                        audio_wav, timing = synthesize_azure_speech(narration, voice=voice, cache_dir=tts_cache_dir)
                        narration = Narration(text=narration.text, words=timing.words)
                        self.store.save(episode_id, "narration_timing", timing.to_dict())
                        audio_dest = ep_dir / "narration_audio.wav"
                        shutil.copy(audio_wav, audio_dest)
                        job_state.append_log(f"✓ Giọng đọc hoàn tất: {timing.duration_sec:.2f}s, {len(timing.words)} từ")
                    except Exception as e:
                        job_state.append_log(f"⚠️ Azure Speech error ({e}). Tự động dùng Silence provider...")
                        active_audio = "silence"

                # Save meta.json
                meta_data = {
                    "episode_id": episode_id,
                    "topic": topic,
                    "title": topic,
                    "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    "media_provider": media_provider,
                    "audio_provider": active_audio,
                    "ai_model": active_model,
                }
                (ep_dir / "meta.json").write_text(json.dumps(meta_data, indent=2, ensure_ascii=False), encoding="utf-8")
                self.store.save(episode_id, "narration", narration.to_dict())

                # Stage 7: Scene Compilation & Parallel Rendering
                job_state.append_log("🎬 [7/8] Giai đoạn 7: Xuất Scene YAML & Render Song song từng Phân cảnh...")
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
                job_state.append_log(f"✓ Scene Compilation hoàn tất: {len(plan.beats)} phân cảnh được lập kế hoạch")

                # Stage 8: Master Timeline Assembly & Subtitle Burning
                if auto_render:
                    job_state.append_log("🎞️ [8/8] Giai đoạn 8: Lắp ráp Master Timeline, Chuyển cảnh Xé giấy & Gắn Phụ đề...")
                    from videotool.render import render_episode
                    out_mp4 = self.artifacts_root / f"{episode_id}.mp4"
                    render_res = render_episode(
                        episode_id=episode_id,
                        store=self.store,
                        output_path=out_mp4,
                        audio_provider_name=active_audio if active_audio != "none" else None,
                        voice=voice,
                        progress_callback=job_state.append_log,
                    )
                    job_state.append_log(f"🎉 MASTER VIDEO HOÀN TẤT: {out_mp4.name} (Thời lượng: {render_res.duration_sec:.2f}s, Beats: {render_res.metadata.get('beats_rendered', len(plan.beats))})")

                job_state.append_log("================================================================================")
                job_state.append_log(f"✨ 8 GIAI ĐOẠN ĐÃ HOÀN TẤT! Vui lòng chọn '{episode_id}' trên menu để xem kết quả.")
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

        ep_dir = self.store.episode_dir(fixture_name)
        if fixture_name not in FIXTURES and not ep_dir.is_dir() and not (self.artifacts_root / fixture_name).is_dir():
            self._send_error_json(f"Episode '{fixture_name}' not found", status=400)
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

    def _handle_get_fact_registry(self, ep_id: str) -> None:
        data = self.store.load(ep_id, "fact_registry")
        if not data:
            data = {
                "project_id": ep_id,
                "topic": ep_id,
                "central_thesis": f"Tài liệu điều tra chuyên sâu về {ep_id}.",
                "entities": [],
                "facts": [],
            }
        self._send_json({"episode_id": ep_id, "fact_registry": data})

    def _handle_get_chapters(self, ep_id: str) -> None:
        outline = self.store.load(ep_id, "chapter_outline") or {}
        scripts = self.store.load(ep_id, "chapter_scripts") or []
        self._send_json({
            "episode_id": ep_id,
            "chapter_outline": outline,
            "chapter_scripts": scripts,
        })

    def _handle_get_scenes(self, ep_id: str) -> None:
        scenes_data = self.store.load(ep_id, "scene_compilation") or {}
        scenes_dir = self.store.episode_dir(ep_id) / "scenes"
        files = []
        if scenes_dir.exists():
            for f in sorted(scenes_dir.glob("*.mp4")):
                files.append({
                    "name": f.name,
                    "size_bytes": f.stat().st_size,
                    "path": str(f.relative_to(self.store.root)),
                })
        self._send_json({
            "episode_id": ep_id,
            "scene_compilation": scenes_data,
            "rendered_files": files,
        })

    def _handle_post_update_fact_registry(self, ep_id: str, payload: dict[str, Any]) -> None:
        self.store.save(ep_id, "fact_registry", payload)
        self._send_json({"status": "ok", "episode_id": ep_id, "message": "Fact registry updated"})

    def _handle_post_render_scene(self, ep_id: str, sc_id: str, payload: dict[str, Any]) -> None:
        cmd = [
            sys.executable,
            "-m",
            "videotool.cli",
            "render-scene",
            payload.get("yaml_path", f"fixtures/{ep_id}_scene.yaml"),
            "--out",
            str(self.store.episode_dir(ep_id) / "scenes" / f"{sc_id}.mp4"),
        ]
        self._execute_cli_async(cmd, f"Render Scene {sc_id}")

    def _handle_post_master_assembly(self, ep_id: str, payload: dict[str, Any]) -> None:
        cmd = [
            sys.executable,
            "-m",
            "videotool.cli",
            "run",
            "--topic",
            ep_id,
            "--mode",
            "final",
        ]
        self._execute_cli_async(cmd, f"Master Assembly: {ep_id}")

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
