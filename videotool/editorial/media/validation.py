"""Downloaded-media validation (Phase 2A spec section 17, 33).

Stdlib only: content sniffing (magic bytes), minimal dimension parsers for
PNG/JPEG/GIF/BMP headers, HTML-masquerading-as-image detection, size
bounds. Downloaded content is untrusted: extensions come from the sniffed
type, never from the remote name.
"""
from __future__ import annotations

import struct
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
