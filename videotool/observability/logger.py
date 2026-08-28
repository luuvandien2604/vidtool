"""Central Pipeline Observability and Logging System.

Provides extreme runtime observability across all pipeline stages, AI requests,
domain validation, editorial decisions, asset acquisition, and FFmpeg rendering.
Supports CLI terminal output, web console streaming, JSON export, secret redaction,
and correlation ID tracking.
"""
from __future__ import annotations

import datetime
import json
import re
import sys
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable


class LogLevel(str, Enum):
    TRACE = "TRACE"
    DEBUG = "DEBUG"
    INFO = "INFO"
    DECISION = "DECISION"
    AI_REQUEST = "AI_REQUEST"
    AI_RESPONSE = "AI_RESPONSE"
    DOMAIN = "DOMAIN"
    ASSET = "ASSET"
    EDITORIAL = "EDITORIAL"
    MOTION = "MOTION"
    RENDER = "RENDER"
    TYPOGRAPHY = "TYPOGRAPHY"
    FFMPEG = "FFMPEG"
    VALIDATION = "VALIDATION"
    CACHE = "CACHE"
    PERFORMANCE = "PERFORMANCE"
    ARTIFACT = "ARTIFACT"
    WARNING = "WARNING"
    ERROR = "ERROR"
    SUCCESS = "SUCCESS"


class LogFormat(str, Enum):
    HUMAN = "HUMAN"
    JSON = "JSON"


# Redaction patterns for secrets (API keys, Authorization tokens, cookies)
SECRET_PATTERNS = [
    re.compile(r"AIza[0-9A-Za-z-_]{35}"),
    re.compile(r"Bearer\s+[A-Za-z0-9\-\._~\+\/]+=*", re.IGNORECASE),
    re.compile(r"sk-[a-zA-Z0-9]{20,}"),
    re.compile(r"key=([a-zA-Z0-9_\-]{16,})", re.IGNORECASE),
    re.compile(r"(api[_-]?key[\"'\s:=]+)[\"']?([a-zA-Z0-9_\-]{16,})[\"']?", re.IGNORECASE),
]


def redact_secrets(text: str) -> str:
    """Redact API keys, tokens, and sensitive headers while preserving full payloads."""
    if not text:
        return ""
    result = str(text)
    for pat in SECRET_PATTERNS:
        result = pat.sub(r"\1[REDACTED_SECRET]" if r"\1" in pat.pattern else "[REDACTED_SECRET]", result)
    return result


@dataclass
class CorrelationContext:
    job_id: str = ""
    scene_id: str = ""
    request_id: str = ""
    asset_id: str = ""
    operation_id: str = ""


class PipelineLogger:
    """Central structured logger for VideoTool production pipeline."""

    def __init__(
        self,
        job_id: str = "",
        verbose: bool = True,
        trace: bool = False,
        trace_ffmpeg: bool = False,
        log_format: LogFormat = LogFormat.HUMAN,
    ):
        self.context = CorrelationContext(job_id=job_id)
        self.verbose = verbose
        self.trace = trace
        self.trace_ffmpeg = trace_ffmpeg
        self.log_format = log_format
        self.handlers: list[Callable[[str, LogLevel, dict[str, Any]], None]] = []
        self.stage_timings: dict[str, float] = {}
        self.stage_start_times: dict[str, float] = {}
        self.ai_call_count = 0
        self.asset_download_count = 0
        self.asset_cache_count = 0
        self.start_wall_time = time.time()
        self.current_stage_num = 0
        self.current_stage_name = ""

    def add_handler(self, handler: Callable[[str, LogLevel, dict[str, Any]], None]) -> None:
        """Register a custom stream handler (e.g. Web UI console callback or file sink)."""
        self.handlers.append(handler)

    def _emit(self, level: LogLevel, message: str, meta: dict[str, Any] | None = None) -> None:
        clean_msg = redact_secrets(message)
        now_str = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
        payload = meta or {}

        if self.log_format == LogFormat.JSON:
            json_entry = {
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "level": level.value,
                "job_id": self.context.job_id,
                "stage": self.current_stage_name,
                "message": clean_msg,
                "meta": payload,
            }
            line = json.dumps(json_entry, ensure_ascii=False)
            print(line, file=sys.stdout, flush=True)
            for h in self.handlers:
                try:
                    h(line, level, json_entry)
                except Exception:
                    pass
            return

        # Human-readable formatted line
        tag = f"[{level.value}]"
        prefix = f"[{now_str}] {tag:<14}"
        formatted_line = f"{prefix} {clean_msg}"

        print(formatted_line, file=sys.stdout, flush=True)

        for h in self.handlers:
            try:
                h(formatted_line, level, payload)
            except Exception:
                pass

    # -------------------------------------------------------------------------
    # Pipeline & Stage Lifecycle
    # -------------------------------------------------------------------------

    def pipeline_start(self, title: str, input_desc: str = "", output_path: str = "") -> None:
        self.start_wall_time = time.time()
        border = "═" * 78
        msg = (
            f"\n╔{border}╗\n"
            f"║  🚀 BẮT ĐẦU PIPELINE SẢN XUẤT: {title.upper():<43} ║\n"
            f"║  Job ID: {self.context.job_id:<62} ║\n"
            f"╚{border}╝"
        )
        self._emit(LogLevel.INFO, msg)
        if input_desc:
            self._emit(LogLevel.INFO, f"Input:  {input_desc}")
        if output_path:
            self._emit(LogLevel.INFO, f"Output: {output_path}")

    def stage_header(self, stage_number: int, stage_name: str, description: str = "") -> None:
        self.current_stage_num = stage_number
        self.current_stage_name = stage_name
        self.stage_start_times[stage_name] = time.time()

        border = "─" * 78
        header = (
            f"\n┌{border}┐\n"
            f"│ 📌 STAGE {stage_number:02d} — {stage_name.upper():<59} │\n"
            f"└{border}┘"
        )
        self._emit(LogLevel.INFO, header)
        if description:
            self._emit(LogLevel.INFO, f"   Mô tả: {description}")

    def stage_complete(self, stage_name: str, status: str = "PASS", details: str = "") -> None:
        elapsed = 0.0
        if stage_name in self.stage_start_times:
            elapsed = time.time() - self.stage_start_times[stage_name]
            self.stage_timings[stage_name] = elapsed

        detail_str = f" ({details})" if details else ""
        self._emit(LogLevel.SUCCESS, f"✓ STAGE {self.current_stage_num:02d} [{stage_name}] {status} [{elapsed:.3f}s]{detail_str}")

    def section_header(self, title: str) -> None:
        self._emit(LogLevel.INFO, f"--- {title} ---")

    # -------------------------------------------------------------------------
    # AI / LLM Observability
    # -------------------------------------------------------------------------

    def log_ai_request(
        self,
        provider: str,
        model: str,
        purpose: str,
        input_context: Any,
        system_prompt: str,
        user_prompt: str,
        expected_schema: Any = None,
    ) -> str:
        self.ai_call_count += 1
        req_id = f"ai_req_{self.ai_call_count:03d}"
        self.context.request_id = req_id

        self._emit(LogLevel.AI_REQUEST, f"📤 [AI REQUEST] Request ID: {req_id} | Provider: {provider} | Model: {model}")
        self._emit(LogLevel.AI_REQUEST, f"   • Mục đích: {purpose}")

        if self.verbose:
            if system_prompt:
                self._emit(LogLevel.AI_REQUEST, f"   • SYSTEM INSTRUCTION:\n{_indent_text(system_prompt, 8)}")
            if user_prompt:
                self._emit(LogLevel.AI_REQUEST, f"   • USER PROMPT:\n{_indent_text(user_prompt, 8)}")
            if expected_schema:
                schema_str = json.dumps(expected_schema, indent=2) if isinstance(expected_schema, (dict, list)) else str(expected_schema)
                self._emit(LogLevel.AI_REQUEST, f"   • EXPECTED SCHEMA:\n{_indent_text(schema_str, 8)}")

        return req_id

    def log_ai_response(
        self,
        duration_sec: float,
        raw_response: str,
        parsed_json: Any = None,
        tokens_info: Any = None,
    ) -> None:
        self._emit(LogLevel.AI_RESPONSE, f"📥 [AI RESPONSE] Thời gian: {duration_sec:.2f}s | Request ID: {self.context.request_id}")
        if tokens_info:
            self._emit(LogLevel.AI_RESPONSE, f"   • Token usage: {tokens_info}")

        if parsed_json is not None:
            if self.trace:
                parsed_str = json.dumps(parsed_json, indent=2, ensure_ascii=False)
                self._emit(LogLevel.AI_RESPONSE, f"   • Parsed JSON Output:\n{_indent_text(parsed_str, 8)}")
            else:
                summary = _summarize_json(parsed_json)
                self._emit(LogLevel.AI_RESPONSE, f"   • Cấu trúc trích xuất: {summary}")
        elif raw_response and self.verbose:
            self._emit(LogLevel.AI_RESPONSE, f"   • Raw response snippet: {raw_response[:300]}...")

    def log_domain_validation(self, check_name: str, passed: bool, details: Any = None) -> None:
        status_tag = "PASS" if passed else "FAIL"
        detail_msg = f" | {details}" if details else ""
        level = LogLevel.DOMAIN if passed else LogLevel.ERROR
        self._emit(level, f"⚖️ [DOMAIN VALIDATION] {check_name}: {status_tag}{detail_msg}")

    def log_editorial_decision(self, component: str, decision: str, rationale: str = "") -> None:
        rationale_str = f" | Lý do: {rationale}" if rationale else ""
        self._emit(LogLevel.DECISION, f"🎯 [EDITORIAL DECISION] {component}: {decision}{rationale_str}")

    # -------------------------------------------------------------------------
    # Asset Acquisition Observability
    # -------------------------------------------------------------------------

    def log_asset_candidate(self, candidate_info: dict[str, Any]) -> None:
        title = candidate_info.get("title", "Unknown")
        score = candidate_info.get("score", 0.0)
        status = candidate_info.get("status", "CONSIDERING")
        reason = candidate_info.get("reason", "")
        reason_str = f" (Lý do: {reason})" if reason else ""
        self._emit(LogLevel.ASSET, f"   • Ứng viên: '{title}' | Score: {score:.2f} | Status: {status}{reason_str}")

    def log_asset_resolution(
        self,
        asset_id: str,
        source: str,
        status: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        d = details or {}
        cache_status = d.get("cache", "MISS")
        if cache_status == "HIT":
            self.asset_cache_count += 1
        else:
            self.asset_download_count += 1

        dims = d.get("dimensions", "")
        dims_str = f" | Kích thước: {dims}" if dims else ""
        lic = d.get("license", "")
        lic_str = f" | Bản quyền: {lic}" if lic else ""
        path = d.get("path", "")
        path_str = f" | File: {path}" if path else ""

        self._emit(
            LogLevel.ASSET,
            f"🖼️ [ASSET] {asset_id} | Nguồn: {source} | Trạng thái: {status} | Cache: {cache_status}{dims_str}{lic_str}{path_str}"
        )

    # -------------------------------------------------------------------------
    # Composition & Motion Observability
    # -------------------------------------------------------------------------

    def log_composition(self, beat_id: str, family: str, layout_desc: dict[str, Any], rationale: str = "") -> None:
        rat_str = f" | Đạo diễn: {rationale}" if rationale else ""
        self._emit(LogLevel.EDITORIAL, f"📐 [COMPOSITION] Beat {beat_id} | Family: {family}{rat_str}")
        if self.verbose:
            for k, v in layout_desc.items():
                self._emit(LogLevel.EDITORIAL, f"      • {k}: {v}")

    def log_motion(self, beat_id: str, layer_name: str, motion_type: str, details: str = "") -> None:
        det_str = f" ({details})" if details else ""
        self._emit(LogLevel.MOTION, f"🎞️ [MOTION] Beat {beat_id} | Layer: {layer_name} | Hiệu ứng: {motion_type}{det_str}")

    # -------------------------------------------------------------------------
    # Typography & SVG Observability
    # -------------------------------------------------------------------------

    def log_typography(self, element_id: str, text: str, font: str, size: float, diacritics_pass: bool = True) -> None:
        dia_str = "PASS" if diacritics_pass else "WARN (Diacritics Check)"
        if self.verbose:
            self._emit(LogLevel.TYPOGRAPHY, f"🔤 [TYPOGRAPHY] {element_id} | Font: {font} ({size}px) | Text: '{text}' | Tiếng Việt: {dia_str}")

    # -------------------------------------------------------------------------
    # FFmpeg Observability
    # -------------------------------------------------------------------------

    def log_ffmpeg_command(self, cmd: list[str], beat_id: str = "") -> None:
        beat_str = f" [Beat {beat_id}]" if beat_id else ""
        wrapped_cmd = " \\\n      ".join(cmd)
        self._emit(LogLevel.FFMPEG, f"⚙️ [FFMPEG COMMAND]{beat_str}:\n      {wrapped_cmd}")

    def log_ffmpeg_progress(self, line: str) -> None:
        if self.trace_ffmpeg:
            self._emit(LogLevel.FFMPEG, f"   {line.strip()}")

    def log_ffmpeg_result(self, exit_code: int, duration_sec: float, output_path: str, size_bytes: int = 0) -> None:
        size_mb = size_bytes / (1024 * 1024) if size_bytes > 0 else 0.0
        status_tag = "SUCCESS" if exit_code == 0 else f"FAILED (Exit {exit_code})"
        level = LogLevel.SUCCESS if exit_code == 0 else LogLevel.ERROR
        self._emit(level, f"🎬 [FFMPEG RESULT] {status_tag} | Thời gian: {duration_sec:.2f}s | Output: {output_path} ({size_mb:.2f} MB)")

    # -------------------------------------------------------------------------
    # Artifact & File System Observability
    # -------------------------------------------------------------------------

    def log_artifact(self, artifact_type: str, path: str, size_bytes: int = 0) -> None:
        size_str = f" ({size_bytes / 1024:.1f} KB)" if size_bytes > 0 else ""
        self._emit(LogLevel.ARTIFACT, f"💾 [ARTIFACT] {artifact_type} -> {path}{size_str}")

    # -------------------------------------------------------------------------
    # Final Execution Summary
    # -------------------------------------------------------------------------

    def pipeline_summary(
        self,
        result: str = "SUCCESS",
        output_file: str = "",
        total_beats: int = 0,
        total_duration_sec: float = 0.0,
    ) -> None:
        total_wall_time = time.time() - self.start_wall_time
        border = "═" * 78
        lines = [
            f"\n╔{border}╗",
            f"║  🏁 TỔNG KẾT THỰC THI PIPELINE: {result.upper():<44} ║",
            f"╚{border}╝",
            f"• Job ID:              {self.context.job_id}",
            f"• Thời lượng video:    {total_duration_sec:.2f}s ({total_beats} Beats)",
            f"• File hoàn tất:       {output_file}",
            f"• Tổng thời gian chạy: {total_wall_time:.2f}s",
            f"• Tương tác AI:        {self.ai_call_count} Requests",
            f"• Tư liệu lưu trữ:     {self.asset_download_count} Tải mới, {self.asset_cache_count} Tái sử dụng Cache",
            "",
            "📊 CHI TIẾT THỜI GIAN TỪNG GIAI ĐOẠN (STAGE BREAKDOWN):",
        ]
        for s_name, s_dur in self.stage_timings.items():
            pct = (s_dur / total_wall_time * 100.0) if total_wall_time > 0 else 0.0
            lines.append(f"   - {s_name:<30}: {s_dur:6.3f}s  ({pct:4.1f}%)")

        lines.append(border)
        summary_text = "\n".join(lines)
        self._emit(LogLevel.SUCCESS if result == "SUCCESS" else LogLevel.ERROR, summary_text)


def _indent_text(text: str, spaces: int = 4) -> str:
    pad = " " * spaces
    return "\n".join(pad + line for line in text.splitlines())


def _summarize_json(data: Any) -> str:
    if isinstance(data, dict):
        keys = list(data.keys())
        return f"Object with {len(keys)} keys ({', '.join(keys[:5])}{'...' if len(keys) > 5 else ''})"
    elif isinstance(data, list):
        return f"List with {len(data)} items"
    return str(data)[:100]


# Global default logger instance
_GLOBAL_LOGGER: PipelineLogger | None = None


def get_logger() -> PipelineLogger:
    global _GLOBAL_LOGGER
    if _GLOBAL_LOGGER is None:
        _GLOBAL_LOGGER = PipelineLogger()
    return _GLOBAL_LOGGER


def init_logger(
    job_id: str = "",
    verbose: bool = True,
    trace: bool = False,
    trace_ffmpeg: bool = False,
    log_format: LogFormat = LogFormat.HUMAN,
) -> PipelineLogger:
    global _GLOBAL_LOGGER
    _GLOBAL_LOGGER = PipelineLogger(
        job_id=job_id,
        verbose=verbose,
        trace=trace,
        trace_ffmpeg=trace_ffmpeg,
        log_format=log_format,
    )
    return _GLOBAL_LOGGER
