"""Deterministic offline media provider over the local catalog.

Wraps the Phase 1 CatalogAcquirer matching rules and synthesizes REAL,
decodable PNG bytes (stdlib zlib/struct) seeded from the candidate id, so
download validation, caching and content dedup run on genuine media.
"""
from __future__ import annotations

import hashlib
import random
import struct
import zlib

from videotool.editorial.media.models import (KIND_TO_MEDIA_TYPE, MediaCandidate,
                                              MediaSearchPlan)
from videotool.editorial.media.ranking import tokens
from videotool.providers.media.base import FetchedMedia, register_provider


def synthesize_png(seed: str, width: int = 1024, height: int = 768) -> bytes:
    """Valid RGB PNG, deterministic in `seed`, filled with seeded noise so
    the compressed size stays realistic (validation rejects tiny blobs)."""
    rng = random.Random(int.from_bytes(
        hashlib.sha256(seed.encode()).digest()[:8], "big"))
    noise = rng.randbytes(width * height * 3)
    stride = width * 3
    raw = b"".join(b"\x00" + noise[i:i + stride]
                   for i in range(0, len(noise), stride))

    def chunk(tag: bytes, payload: bytes) -> bytes:
        return (struct.pack(">I", len(payload)) + tag + payload +
                struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF))

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) +
            chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))


@register_provider
class FixtureMediaProvider:
    provider_id = "fixture"
    provider_version = 1

    def __init__(self, catalog: list[dict] | None = None):
        self.catalog = catalog or []

    def search(self, query_text: str, limit: int) -> list[MediaCandidate]:
        """Match catalog rows against the query's folded tokens (the same
        semantic matching CatalogAcquirer uses, normalized to candidates)."""
        want = tokens(query_text)
        scored: list[tuple[float, dict]] = []
        for row in self.catalog:
            row_tokens = (tokens(row["description"]) |
                          {t for e in row.get("entities", []) for t in tokens(e)})
            if not want:
                continue
            overlap = len(want & row_tokens) / max(1, len(want))
            if overlap <= 0:
                continue
            scored.append((overlap, row))
        scored.sort(key=lambda pair: (-pair[0], pair[1]["asset_id"]))
        out = []
        for _, row in scored[:limit]:
            out.append(self._to_candidate(row))
        return out

    def _to_candidate(self, row: dict) -> MediaCandidate:
        kind = row.get("kind", "photo")
        return MediaCandidate(
            candidate_id=row["asset_id"],
            provider=self.provider_id,
            title=row.get("description", ""),
            description=row.get("description", ""),
            media_type=KIND_TO_MEDIA_TYPE.get(kind,
                                              KIND_TO_MEDIA_TYPE["photo"]).value,
            width=row.get("width", 1400),
            height=row.get("height", 1000),
            creator=row.get("creator", "Fixture Archive"),
            date_created=row.get("date", ""),
            license_name=row.get("license", "CC0 1.0"),
            license_url=row.get("license_url",
                                "https://creativecommons.org/publicdomain/zero/1.0/"),
            source_page=row.get("source_page", ""),
            source_url=row.get("source_page", ""),
            media_url=f"fixture://{row['asset_id']}",
            entities=list(row.get("entities", [])),
            categories=["fixture archive"],
        )

    def fetch(self, candidate: MediaCandidate) -> FetchedMedia:
        data = synthesize_png(candidate.candidate_id)
        return FetchedMedia(data, content_type="image/png",
                            media_url=candidate.media_url)
