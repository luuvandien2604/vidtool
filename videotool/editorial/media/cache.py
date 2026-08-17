"""Content-addressed media cache with a provider-scoped candidate index.

Blob identity and remote candidate identity are deliberately separate:
many provider candidates may point at one SHA-256 blob, while a changed
remote URL/revision for the same candidate cannot reuse a stale mapping.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

MEDIA_CACHE_VERSION = 2
_INDEX_NAME = "candidate-index-v2.json"


def checksum_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _identity(provider: str, candidate_id: str, media_url: str,
              revision: str) -> dict[str, str]:
    return {"provider": provider or "", "candidate_id": candidate_id or "",
            "media_url": media_url or "", "revision": revision or ""}


def _identity_key(identity: dict[str, str]) -> str:
    raw = json.dumps(identity, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


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

    def _index_path(self) -> Path:
        return self.root / _INDEX_NAME

    def _load_index(self) -> dict:
        try:
            payload = json.loads(self._index_path().read_text(encoding="utf-8"))
            if payload.get("version") == MEDIA_CACHE_VERSION:
                return payload
        except (FileNotFoundError, json.JSONDecodeError, OSError, AttributeError):
            pass
        return {"version": MEDIA_CACHE_VERSION, "candidates": {}}

    def _save_index(self, payload: dict) -> None:
        path = self._index_path()
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, indent=2, sort_keys=True,
                                        ensure_ascii=False), encoding="utf-8")
        temporary.replace(path)

    def put(self, data: bytes, ext: str, metadata: dict) -> tuple[str, bool]:
        """Store one blob and independently upsert its candidate mapping."""
        sha = checksum_bytes(data)
        blob = self._blob_path(sha, ext)
        newly = not blob.exists()
        if newly:
            self._dir(sha).mkdir(parents=True, exist_ok=True)
            blob.write_bytes(data)

        identity = _identity(str(metadata.get("provider", "")),
                             str(metadata.get("candidate_id", "")),
                             str(metadata.get("media_url", "")),
                             str(metadata.get("revision", "")))
        index = self._load_index()
        key = _identity_key(identity)
        if identity["candidate_id"]:
            index["candidates"][key] = {**identity, "checksum": sha}
            self._save_index(index)

        # Blob metadata is content-centric. Preserve every candidate key instead
        # of replacing candidate A when candidate B has identical bytes.
        prior = self.metadata(sha) or {}
        candidate_keys = set(prior.get("candidate_keys", []))
        if identity["candidate_id"]:
            candidate_keys.add(key)
        blob_meta = {"checksum": sha, "extension": ext,
                     "candidate_keys": sorted(candidate_keys)}
        self._meta_path(sha).write_text(
            json.dumps(blob_meta, indent=2, sort_keys=True), encoding="utf-8")
        return sha, newly

    def get(self, sha: str) -> bytes | None:
        for path in self._dir(sha).glob(f"{sha}.*"):
            if path.suffix != ".json":
                return path.read_bytes()
        return None

    def has_blob(self, sha: str) -> bool:
        return any(path.suffix != ".json"
                   for path in self._dir(sha).glob(f"{sha}.*"))

    def metadata(self, sha: str) -> dict | None:
        p = self._meta_path(sha)
        if not p.exists():
            return None
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None

    def candidate_checksum(self, candidate_id: str, provider: str = "",
                           media_url: str = "", revision: str = ""
                           ) -> str | None:
        index = self._load_index()
        candidates = index["candidates"]
        if provider or media_url or revision:
            entry = candidates.get(_identity_key(
                _identity(provider, candidate_id, media_url, revision)))
            return entry.get("checksum") if entry else None
        # Compatibility lookup for callers without normalized identity.
        matches = [entry for entry in candidates.values()
                   if entry.get("candidate_id") == candidate_id]
        if not matches:
            return None
        matches.sort(key=lambda item: (item.get("provider", ""),
                                       item.get("media_url", ""),
                                       item.get("revision", "")))
        return matches[0].get("checksum")

    def find_by_candidate(self, candidate_id: str, provider: str = "",
                          media_url: str = "", revision: str = ""
                          ) -> tuple[str, bytes] | None:
        sha = self.candidate_checksum(candidate_id, provider, media_url, revision)
        if not sha:
            return None
        data = self.get(sha)
        return (sha, data) if data is not None else None
