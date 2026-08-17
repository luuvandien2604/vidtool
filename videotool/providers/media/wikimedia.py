"""Wikimedia Commons provider over the official MediaWiki API.

Uses action=query with generator=search + prop=imageinfo (urls, size, mime,
extmetadata for license/artist). No HTML scraping. All network access goes
through an injectable transport so tests run on recorded fixtures; the
production transport uses urllib with timeout, bounded retries, backoff,
user agent, HTTPS and a max response size.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request

from videotool.editorial.media.models import MediaCandidate
from videotool.editorial.media.type_inference import infer_media_type
from videotool.providers.media.base import (FetchedMedia, ProviderError,
                                            RequestPacer, register_provider)

API_BASE = "https://commons.wikimedia.org/w/api.php"
PROVIDER_SOURCE_NAME = "Wikimedia Commons"
ALLOWED_HOSTS = {"commons.wikimedia.org", "upload.wikimedia.org"}


class UrllibTransport:
    """Production transport: urllib, HTTPS-only, bounded, paced."""

    def __init__(self, timeout_sec: float = 15.0, retries: int = 2,
                 user_agent: str = "vidtool", max_bytes: int = 50 * 1024 * 1024,
                 min_interval_sec: float = 0.5):
        self.timeout_sec = timeout_sec
        self.retries = retries
        self.user_agent = user_agent
        self.max_bytes = max_bytes
        self.pacer = RequestPacer(min_interval_sec)

    def get(self, url: str) -> bytes:
        self._assert_https(url)
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            if attempt:
                time.sleep(0.5 * attempt)  # linear backoff, bounded
            self.pacer.wait()
            try:
                request = urllib.request.Request(
                    url, headers={"User-Agent": self.user_agent})
                with urllib.request.urlopen(request, timeout=self.timeout_sec) as r:
                    return self._read_bounded(r)
            except (urllib.error.URLError, urllib.error.HTTPError,
                    TimeoutError, OSError) as exc:
                last_error = exc
                continue
        raise ProviderError(f"wikimedia transport failed after "
                            f"{self.retries + 1} attempts: {last_error}")

    def get_json(self, url: str) -> dict:
        return json.loads(self.get(url).decode("utf-8"))

    def _read_bounded(self, response) -> bytes:
        chunks, total = [], 0
        while True:
            chunk = response.read(64 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > self.max_bytes:
                raise ProviderError("response exceeds max size")
            chunks.append(chunk)
        return b"".join(chunks)

    @staticmethod
    def _assert_https(url: str) -> None:
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme != "https":
            raise ProviderError(f"non-HTTPS provider URL rejected: {url}")


@register_provider
class WikimediaMediaProvider:
    provider_id = "wikimedia"
    provider_version = 2  # 2: expose remote media revision identity

    def __init__(self, transport=None, timeout_sec: float = 15.0,
                 retries: int = 2, user_agent: str = "vidtool"):
        self.transport = transport or UrllibTransport(
            timeout_sec=timeout_sec, retries=retries, user_agent=user_agent)

    # ---- API ----
    def search(self, query_text: str, limit: int) -> list[MediaCandidate]:
        params = {
            "action": "query",
            "format": "json",
            "formatversion": "2",
            "generator": "search",
            "gsrsearch": query_text,
            "gsrnamespace": "6",  # File:
            "gsrlimit": str(max(1, limit)),
            "prop": "imageinfo",
            "iiprop": "url|size|mime|sha1|timestamp|extmetadata",
            "iiurlwidth": "320",
        }
        url = f"{API_BASE}?{urllib.parse.urlencode(params)}"
        try:
            payload = self.transport.get_json(url)
        except ProviderError:
            raise
        except (ValueError, json.JSONDecodeError) as exc:
            raise ProviderError(f"wikimedia returned malformed JSON: {exc}")
        pages = (payload.get("query", {}) or {}).get("pages", []) or []
        return [self._to_candidate(p) for p in pages if self._usable(p)]

    def fetch(self, candidate: MediaCandidate) -> FetchedMedia:
        if not candidate.media_url:
            raise ProviderError("candidate has no media url")
        self._assert_allowed_host(candidate.media_url)
        data = self.transport.get(candidate.media_url)
        return FetchedMedia(data,
                            content_type=candidate.provider_metadata.get("mime", ""),
                            media_url=candidate.media_url)

    # ---- normalization ----
    def _usable(self, page: dict) -> bool:
        info = (page.get("imageinfo") or [{}])[0]
        return bool(info.get("url"))

    def _to_candidate(self, page: dict) -> MediaCandidate:
        info = (page.get("imageinfo") or [{}])[0]
        ext = info.get("extmetadata", {}) or {}
        title = (page.get("title") or "").replace("File:", "")
        mime = info.get("mime", "")
        categories = [title.rsplit(".", 1)[0]]  # filename as weak category
        media_type = infer_media_type(title=title,
                                      description=_ext(ext, "ImageDescription"),
                                      mime=mime,
                                      width=info.get("width", 0),
                                      height=info.get("height", 0),
                                      categories=categories).value
        return MediaCandidate(
            candidate_id=f"wikimedia:{page.get('pageid', title)}",
            provider=self.provider_id,
            title=title,
            description=_ext(ext, "ImageDescription"),
            media_type=media_type,
            width=int(info.get("width", 0) or 0),
            height=int(info.get("height", 0) or 0),
            creator=_ext(ext, "Artist"),
            date_created=_ext(ext, "DateTimeOriginal"),
            date_published=_ext(ext, "DateTime"),
            license_name=_ext(ext, "LicenseShortName"),
            license_url=_ext(ext, "LicenseUrl"),
            source_page=(page.get("imageinfo") or [{}])[0].get(
                "descriptionurl", ""),
            source_url=(page.get("imageinfo") or [{}])[0].get(
                "descriptionurl", ""),
            media_url=info.get("url", ""),
            thumbnail_url=info.get("thumburl", ""),
            categories=categories,
            provider_metadata={"mime": mime, "pageid": page.get("pageid"),
                               "sha1": info.get("sha1", ""),
                               "timestamp": info.get("timestamp", "")},
        )

    @staticmethod
    def _assert_allowed_host(url: str) -> None:
        host = urllib.parse.urlparse(url).netloc.lower()
        if host not in ALLOWED_HOSTS:
            raise ProviderError(f"wikimedia host not allowed: {host}")


def _ext(ext: dict, key: str) -> str:
    value = ext.get(key, {})
    return (value.get("value", "") if isinstance(value, dict) else str(value or "")).strip()
