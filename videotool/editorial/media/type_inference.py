"""Deterministic media-type inference (Phase 2A spec section 13).

Providers rarely tag PORTRAIT/DOCUMENT/MAP explicitly; we infer from
categories, title, description, MIME, keywords and aspect ratio. Rules are
centralized here and unit-tested; editorial logic never re-derives types.
"""
from __future__ import annotations

from videotool.editorial.media.models import MediaType
from videotool.editorial.media.ranking import fold

MEDIA_TYPE_INFERENCE_VERSION = 1

_MAP_KEYWORDS = ("map", "karte", "plan of", "topographic", "atlas",
                 "diagram of", "outline map", "city plan", "border map")
_DOCUMENT_KEYWORDS = ("document", "passport", "memorandum", "protocol",
                      "certificate", "urkunde", "reisepass", "newspaper page",
                      "front page", "transcript", "letter of", "regulation",
                      "gesetz", "draft law", "application form", "ausweis")
_ILLUSTRATION_KEYWORDS = ("drawing of", "engraving", "lithograph",
                          "painting of", "sketch of", "illustration of",
                          "poster of", "woodcut")
_PORTRAIT_KEYWORDS = ("portrait of", "bust of", "photograph of",
                      "mugshot", "likeness of")


def infer_media_type(title: str, description: str = "", mime: str = "",
                     width: int = 0, height: int = 0,
                     categories: list[str] | None = None,
                     entities: list[str] | None = None) -> MediaType:
    text = fold(" ".join([title, description, " ".join(categories or [])]))
    has = lambda *words: any(w in text for w in words)

    if mime == "image/svg+xml":
        # vector graphics on archives are overwhelmingly maps/diagrams
        if has(*_MAP_KEYWORDS) or "svg" in text:
            return MediaType.MAP
        return MediaType.ILLUSTRATION
    if has(*_MAP_KEYWORDS):
        return MediaType.MAP
    if has(*_DOCUMENT_KEYWORDS):
        return MediaType.DOCUMENT
    if has(*_ILLUSTRATION_KEYWORDS):
        return MediaType.ILLUSTRATION

    person_named = bool(entities) or has(*_PORTRAIT_KEYWORDS)
    portrait_shape = bool(width and height and height / max(1, width) >= 1.05)
    if person_named and (has(*_PORTRAIT_KEYWORDS) or portrait_shape):
        return MediaType.PORTRAIT
    return MediaType.PHOTO
