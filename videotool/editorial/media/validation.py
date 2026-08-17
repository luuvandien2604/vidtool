"""Downloaded-media validation (Phase 2A spec section 17, 33).

Stdlib only: content sniffing (magic bytes), minimal dimension parsers for
PNG/JPEG/GIF/BMP headers, HTML-masquerading-as-image detection, size
bounds. Downloaded content is untrusted: extensions come from the sniffed
type, never from the remote name.
"""
from __future__ import annotations

import re
import struct
import urllib.parse
from dataclasses import dataclass

MEDIA_DOWNLOAD_VERSION = 1

MAX_BYTES = 50 * 1024 * 1024
MIN_BYTES = 4 * 1024


@dataclass
class ValidatedMedia:
    ok: bool
    media_format: str = ""      # jpeg / png / gif / webp / svg
    extension: str = ""
    width: int = 0
    height: int = 0
    byte_size: int = 0
    reason: str = ""


class MediaValidationError(Exception):
    pass


def sniff_format(data: bytes) -> str:
    if data[:3] == b"\xff\xd8\xff":
        return "jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "gif"
    if data[:2] == b"BM":
        return "bmp"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    stripped = data[:512].lstrip()
    if stripped[:5] == b"<?xml" or stripped[:4] == b"<svg":
        return "svg"
    if stripped[:15].lower().startswith(b"<!doctype html") or \
            stripped[:6].lower().startswith(b"<html"):
        return "html"
    return ""


def looks_like_html(data: bytes) -> bool:
    return sniff_format(data) == "html"


def _png_dimensions(data: bytes) -> tuple[int, int]:
    # IHDR is the first chunk: bytes 16..24 are width/height (big endian)
    if len(data) < 24:
        return (0, 0)
    w, h = struct.unpack(">II", data[16:24])
    return (w, h)


def _gif_dimensions(data: bytes) -> tuple[int, int]:
    if len(data) < 10:
        return (0, 0)
    w, h = struct.unpack("<HH", data[6:10])
    return (w, h)


def _bmp_dimensions(data: bytes) -> tuple[int, int]:
    if len(data) < 26:
        return (0, 0)
    w, h = struct.unpack("<ii", data[18:26])
    return (abs(w), abs(h))


def _jpeg_dimensions(data: bytes) -> tuple[int, int]:
    """Walk JPEG markers to the first SOFn frame header."""
    i = 2
    size = len(data)
    while i + 9 < size:
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
            i += 2
            continue
        if i + 4 > size:
            break
        seg_len = struct.unpack(">H", data[i + 2:i + 4])[0]
        if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
            if i + 9 <= size:
                h, w = struct.unpack(">HH", data[i + 5:i + 9])
                return (w, h)
            break
        i += 2 + seg_len
    return (0, 0)


def dimensions(data: bytes, media_format: str) -> tuple[int, int]:
    if media_format == "png":
        return _png_dimensions(data)
    if media_format == "gif":
        return _gif_dimensions(data)
    if media_format == "bmp":
        return _bmp_dimensions(data)
    if media_format == "jpeg":
        return _jpeg_dimensions(data)
    return (0, 0)  # webp/svg: not parsed in Phase 2A; neutral downstream


# remote names are never trusted; extension derives from sniffed content
_EXTENSION = {"jpeg": "jpg", "png": "png", "gif": "gif",
              "bmp": "bmp", "webp": "webp", "svg": "svg"}


def validate_media(data: bytes, expected_media: str = "image",
                   min_bytes: int = MIN_BYTES,
                   max_bytes: int = MAX_BYTES) -> ValidatedMedia:
    """Full download validation. Raises nothing; reports ok/reason."""
    if not data:
        return ValidatedMedia(False, reason="empty download")
    if len(data) < min_bytes:
        return ValidatedMedia(False, byte_size=len(data),
                              reason=f"too small ({len(data)} bytes < {min_bytes})")
    if len(data) > max_bytes:
        return ValidatedMedia(False, byte_size=len(data),
                              reason=f"too large ({len(data)} bytes > {max_bytes})")
    fmt = sniff_format(data)
    if not fmt:
        return ValidatedMedia(False, byte_size=len(data),
                              reason="unrecognized binary content")
    if fmt == "html":
        return ValidatedMedia(False, media_format="html",
                              byte_size=len(data),
                              reason="HTML page masquerading as media")
    if expected_media == "image" and fmt == "svg":
        # allow vector images only as illustrations; caller decides policy,
        # here they pass validation with parsed size unknown
        pass
    w, h = dimensions(data, fmt)
    if fmt in ("png", "jpeg", "gif", "bmp") and (w <= 0 or h <= 0):
        return ValidatedMedia(False, media_format=fmt, byte_size=len(data),
                              reason="decodable container but invalid dimensions "
                                     "(truncated?)")
    return ValidatedMedia(True, media_format=fmt,
                          extension=_EXTENSION[fmt], width=w, height=h,
                          byte_size=len(data))


def safe_extension(data: bytes) -> str:
    """Extension from content only; used to build cache filenames."""
    fmt = sniff_format(data)
    return _EXTENSION.get(fmt, "bin")


def sanitize_stem(name: str) -> str:
    """Path-traversal-proof stem for any display filename."""
    keep = [c if (c.isalnum() or c in "-_") else "_" for c in name]
    return "".join(keep).strip("_")[:80] or "media"


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def validate_media_assets(assets, requirements, mode: str,
                          candidates_by_req: dict | None = None,
                          cache=None) -> list[str]:
    """Cheap semantic integrity checks for persisted MediaAsset artifacts.

    This validates bindings/provenance and cache references without reopening
    and decoding every blob. Full byte validation remains a download concern.
    """
    from videotool.editorial.media.licensing import license_allowed

    errors: list[str] = []
    req_by_id = {r.requirement_id: r for r in requirements}
    candidate_maps = {
        rid: {c.candidate_id: c for c in candidates}
        for rid, candidates in (candidates_by_req or {}).items()}
    for index, asset in enumerate(assets):
        label = asset.asset_id or f"asset[{index}]"
        if not asset.asset_id:
            errors.append(f"{label}: missing asset_id")
        req = req_by_id.get(asset.requirement_id)
        if req is None:
            errors.append(f"{label}: unknown requirement_id")
            continue
        if asset.kind != req.kind:
            errors.append(f"{label}: kind does not match requirement")
        if asset.is_placeholder:
            if mode == "final":
                errors.append(f"{label}: placeholder forbidden in final mode")
            continue
        if not asset.provider or not asset.candidate_id:
            errors.append(f"{label}: missing provider/candidate provenance")
        candidate = candidate_maps.get(req.requirement_id, {}).get(
            asset.candidate_id)
        if candidates_by_req is not None and candidate is None:
            errors.append(f"{label}: candidate not present in current search results")
        if candidate is not None:
            if asset.provider != candidate.provider:
                errors.append(f"{label}: provider differs from candidate")
            if asset.media_url != candidate.media_url:
                errors.append(f"{label}: media URL differs from candidate")
            if asset.source_page != candidate.source_page:
                errors.append(f"{label}: source page differs from candidate")
            if asset.license_name != candidate.license_name:
                errors.append(f"{label}: license differs from candidate")
        if mode == "final" and not license_allowed(asset.license_name):
            errors.append(f"{label}: license is not allowed")
        if not _SHA256_RE.fullmatch(asset.checksum or ""):
            errors.append(f"{label}: invalid SHA-256 checksum")
        if asset.width <= 0 or asset.height <= 0:
            errors.append(f"{label}: invalid dimensions")
        parsed = urllib.parse.urlparse(asset.media_url)
        allowed_scheme = "fixture" if asset.provider == "fixture" else "https"
        if parsed.scheme != allowed_scheme or not parsed.netloc:
            errors.append(f"{label}: invalid media URL")
        if asset.provider != "fixture":
            source = urllib.parse.urlparse(asset.source_page)
            if source.scheme != "https" or not source.netloc:
                errors.append(f"{label}: missing/invalid source page")
        if not asset.attribution.get("license_name"):
            errors.append(f"{label}: attribution license missing")
        if cache is not None and _SHA256_RE.fullmatch(asset.checksum or ""):
            if not cache.has_blob(asset.checksum):
                errors.append(f"{label}: cached blob is missing")
            if candidate is not None:
                revision = (candidate.provider_metadata.get("revision")
                            or candidate.provider_metadata.get("sha1")
                            or candidate.provider_metadata.get("timestamp") or "")
                indexed = cache.candidate_checksum(
                    candidate.candidate_id, candidate.provider,
                    candidate.media_url, str(revision))
                if indexed != asset.checksum:
                    errors.append(f"{label}: candidate cache mapping mismatch")
    return errors
