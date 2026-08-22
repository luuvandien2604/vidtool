"""Environment and credentials loading utilities for providers."""
from __future__ import annotations

import os
from pathlib import Path


def load_env_fallback() -> None:
    """Load key-value pairs from .env into os.environ if missing."""
    for env_path in (Path(".env"), Path(__file__).resolve().parents[2] / ".env"):
        if env_path.is_file():
            try:
                for line in env_path.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, _, v = line.partition("=")
                        k = k.strip()
                        v = v.strip().strip("'\"")
                        if k and k not in os.environ:
                            os.environ[k] = v
            except Exception:
                pass


def get_anthropic_api_key() -> str:
    """Retrieve Anthropic API key from environment with .env fallback."""
    load_env_fallback()
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key:
        raise ValueError(
            "Anthropic API key missing: Please set ANTHROPIC_API_KEY environment variable (or add it to a .env file)."
        )
    return key


def get_gemini_api_key() -> str:
    """Retrieve Google Gemini API key from environment with .env fallback."""
    load_env_fallback()
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        raise ValueError(
            "Gemini API key missing: Please set GEMINI_API_KEY environment variable (or add it to a .env file)."
        )
    return key
