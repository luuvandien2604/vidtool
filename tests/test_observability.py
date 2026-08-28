"""Tests for VideoTool Observability and Structured Logging Subsystem."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from videotool.observability import (
    LogFormat,
    LogLevel,
    PipelineLogger,
    get_logger,
    init_logger,
    redact_secrets,
)


def test_redact_secrets():
    # Google AI API Key
    text1 = "API key is AIzaSyD3x-abc1234567890abcdefghijklmnopqr in headers"
    redacted1 = redact_secrets(text1)
    assert "AIzaSyD3x-abc1234567890abcdefghijklmnopqr" not in redacted1
    assert "[REDACTED_SECRET]" in redacted1

    # Bearer token
    text2 = "Authorization: Bearer ya29.a0AfH6SMD_secret_token_12345"
    redacted2 = redact_secrets(text2)
    assert "ya29.a0AfH6SMD_secret_token_12345" not in redacted2

    # OpenAI sk- key
    text3 = "OpenAI key sk-123456789012345678901234567890"
    redacted3 = redact_secrets(text3)
    assert "sk-123456789012345678901234567890" not in redacted3


def test_pipeline_logger_human_mode():
    logs: list[str] = []
    logger = PipelineLogger(job_id="test_job_001", verbose=True, log_format=LogFormat.HUMAN)
    logger.add_handler(lambda line, lvl, meta: logs.append(line))

    logger.pipeline_start("Test Pipeline", input_desc="Test Input", output_path="out.mp4")
    logger.stage_header(1, "narration_timing", "Extract word timings")
    logger.stage_complete("narration_timing", status="PASS", details="10 words")
    logger.log_domain_validation("Beat Consistency", True, "All beats aligned")
    logger.log_editorial_decision("Hero Visual", "Accepted", "Matches archival tone")
    logger.pipeline_summary(result="SUCCESS", total_beats=5, total_duration_sec=30.0)

    assert any("BẮT ĐẦU PIPELINE" in line for line in logs)
    assert any("STAGE 01" in line for line in logs)
    assert any("DOMAIN VALIDATION" in line for line in logs)
    assert any("EDITORIAL DECISION" in line for line in logs)
    assert any("TỔNG KẾT THỰC THI PIPELINE" in line for line in logs)


def test_pipeline_logger_json_mode():
    json_logs: list[dict] = []
    logger = PipelineLogger(job_id="test_job_json", verbose=True, log_format=LogFormat.JSON)
    logger.add_handler(lambda line, lvl, meta: json_logs.append(meta))

    logger.stage_header(2, "semantic_beats", "Partition narration into beats")
    logger.log_domain_validation("Grammar Check", True)

    assert len(json_logs) >= 2
    assert json_logs[0]["job_id"] == "test_job_json"
    assert json_logs[0]["level"] in (LogLevel.INFO.value, LogLevel.DOMAIN.value)


def test_pipeline_logger_ai_observability():
    logs: list[str] = []
    logger = PipelineLogger(job_id="test_ai_job", verbose=True, trace=True)
    logger.add_handler(lambda line, lvl, meta: logs.append(line))

    req_id = logger.log_ai_request(
        provider="Gemini",
        model="gemini-2.5-flash",
        purpose="Editorial Advisory",
        input_context={"scene": "berlin_wall"},
        system_prompt="You are a documentary editor.",
        user_prompt="Analyze scene 1.",
        expected_schema={"hero_asset": "str"},
    )
    assert req_id == "ai_req_001"

    logger.log_ai_response(
        duration_sec=1.45,
        raw_response='{"hero_asset": "berlin_wall_01"}',
        parsed_json={"hero_asset": "berlin_wall_01"},
    )

    assert any("[AI_REQUEST]" in l for l in logs)
    assert any("gemini-2.5-flash" in l for l in logs)
    assert any("[AI_RESPONSE]" in l for l in logs)
    assert any("1.45s" in l for l in logs)
