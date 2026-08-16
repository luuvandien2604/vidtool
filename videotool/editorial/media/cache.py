"""Content-addressed media cache (Phase 2A spec section 16).

Canonical identity is the SHA-256 of the bytes, never a page title.
Identical bytes are stored exactly once. A candidate-id index allows
re-downloads to be skipped without knowing the checksum upfront.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


def checksum_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class MediaCache:
    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _dir(self, sha: str) -> Path:
        return self.root / sha[:2]

    def _blob_path(self, sha: str, ext: str) -> Path:
        return self._dir(sha) / f"{sha}.{ext}"

    def _meta_path(self, sha: str) -> Path:
        return self._dir(sha) / f"{sha}.metadata.json"

    def put(self, data: bytes, ext: str, metadata: dict) -> tuple[str, bool]:
        """Store bytes; returns (checksum, newly_written)."""
        sha = checksum_bytes(data)
        blob = self._blob_path(sha, ext)
        newly = not blob.exists()
        if newly:
            self._dir(sha).mkdir(parents=True, exist_ok=True)
            blob.write_bytes(data)
        meta = dict(metadata)
        meta["checksum"] = sha  # self-referencing index for candidate lookups
        self._meta_path(sha).write_text(
            json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
        return sha, newly

    def get(self, sha: str) -> bytes | None:
        for path in self._dir(sha).glob(f"{sha}.*"):
            if path.suffix != ".json":
                return path.read_bytes()
        return None

    def metadata(self, sha: str) -> dict | None:
        p = self._meta_path(sha)
        if not p.exists():
            return None
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None

    def find_by_candidate(self, candidate_id: str) -> tuple[str, bytes] | None:
        """Cache hit by provider candidate id (avoids re-download)."""
        for meta_path in self.root.glob("*/*.metadata.json"):
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            if meta.get("candidate_id") == candidate_id:
                sha = meta.get("checksum")
                if sha:
                    data = self.get(sha)
                    if data is not None:
                        return sha, data
        return None
