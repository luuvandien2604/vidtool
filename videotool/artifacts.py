"""Deterministic intermediate artifacts (spec section 20).

Every planning stage persists JSON under artifacts/<episode_id>/. A failed
late stage must never force research/narration to run again: the runner
resumes from whatever valid artifacts already exist.
"""
from __future__ import annotations

import json
from pathlib import Path


class ArtifactStore:
    def __init__(self, root: str | Path):
        self.root = Path(root)

    def episode_dir(self, episode_id: str) -> Path:
        d = self.root / episode_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    def path_for(self, episode_id: str, name: str) -> Path:
        return self.episode_dir(episode_id) / f"{name}.json"

    def save(self, episode_id: str, name: str, payload: dict | list) -> Path:
        p = self.path_for(episode_id, name)
        p.write_text(json.dumps(payload, indent=2, ensure_ascii=False),
                     encoding="utf-8")
        return p

    def load(self, episode_id: str, name: str) -> dict | list | None:
        p = self.path_for(episode_id, name)
        if not p.exists():
            return None
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None

    def delete(self, episode_id: str, name: str) -> None:
        p = self.path_for(episode_id, name)
        if p.exists():
            p.unlink()

    def existing(self, episode_id: str) -> list[str]:
        d = self.root / episode_id
        if not d.exists():
            return []
        return sorted(p.stem for p in d.glob("*.json"))
