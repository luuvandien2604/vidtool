"""License policy (Phase 2A spec section 14).

Unknown / missing / restricted licenses are unusable by default. Every
allowed asset carries full attribution for the future attribution manifest.
"""
from __future__ import annotations

import re

LICENSE_POLICY_VERSION = 1

# substrings (lowercase) that mark a clearly reusable license
_ALLOWED_PATTERNS = (
    "public domain", "publicdomain", "pd-old", "pd us", "no restrictions",
    "cc0", "creative commons zero", "cc by-sa", "cc by",
    "attribution", "sharealike",
)

# explicitly restricted markers
_DENIED_PATTERNS = (
    "non-commercial", "noncommercial", "nc)", "by-nc", "nc-sa", "nc-nd",
    "nd)", "by-nd", "no derivative", "noderivatives",
    "fair use", "all rights reserved", "copyrighted",
)


def normalize_license(name: str) -> str:
    return re.sub(r"\s+", " ", (name or "").strip().lower())


def license_allowed(name: str) -> bool:
    """True only for clearly reusable licenses; unknown is NOT allowed."""
    norm = normalize_license(name)
    if not norm:
        return False
    for denied in _DENIED_PATTERNS:
        if denied in norm:
            return False
    return any(pattern in norm for pattern in _ALLOWED_PATTERNS)


def license_quality(name: str) -> float:
    """Small ranking component: PD/CC0 marginally preferred over BY-SA."""
    norm = normalize_license(name)
    if not license_allowed(norm):
        return 0.0
    if "cc0" in norm or "zero" in norm or "public domain" in norm or "pd" in norm:
        return 1.0
    return 0.9
