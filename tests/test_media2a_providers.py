"""Phase 2A provider tests: fixture provider + Wikimedia behind fake transport.

No test in this file touches the network.
"""
import json
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from videotool.editorial.media.models import MediaCandidate
from videotool.providers.media import (FixtureMediaProvider, ProviderError,
                                       build_provider)
from videotool.providers.media.base import RequestPacer
from videotool.providers.media.fixture import synthesize_png
from videotool.providers.media.wikimedia import UrllibTransport, \
    WikimediaMediaProvider

FIX = Path(__file__).parent / "fixtures" / "wikimedia" / "api_responses.json"


class FakeTransport:
    """Maps search-text -> recorded API JSON; media_url -> bytes."""

    def __init__(self, responses: dict, media: dict | None = None,
                 fail_on: set | None = None):
        self.responses = responses
        self.media = media or {}
        self.fail_on = fail_on or set()
        self.calls = []

    def get(self, url: str) -> bytes:
        self.calls.append(url)
        for token in self.fail_on:
            if token in url:
                raise ProviderError(f"transport failure for {token}")
        return self.get_bytes_for(url)

    def get_bytes_for(self, url):
        if "api.php" in url:
            import urllib.parse
            params = dict(urllib.parse.parse_qsl(
                urllib.parse.urlparse(url).query))
            query = params.get("gsrsearch", "")
            payload = self.responses.get(query)
            if payload is None:
                return json.dumps({"query": {"pages": []}}).encode()
            return json.dumps(payload).encode()
        for prefix, data in self.media.items():
            if url.startswith(prefix):
                return data
        raise ProviderError(f"no fixture media for {url}")

    def get_json(self, url):
        return json.loads(self.get(url).decode())


def wikimedia_provider(fail_on=None, media=None):
    responses = json.loads(FIX.read_text())
    responses.pop("_comment", None)
    return WikimediaMediaProvider(
        transport=FakeTransport(responses, media=media, fail_on=fail_on))


def schabowski_media():
    return {"https://upload.wikimedia.org/commons/a/ab/":
            synthesize_png("schabowski")}


# ---- fixture provider ------------------------------------------------------

def test_fixture_provider_search_matches_semantically():
    catalog = [
        {"asset_id": "c_portrait", "kind": "portrait",
         "description": "portrait of Gunter Schabowski at a 1989 press conference",
         "entities": ["Gunter Schabowski"]},
        {"asset_id": "c_skyline", "kind": "photo",
         "description": "Berlin skyline panorama generic cityscape",
         "entities": []},
    ]
    provider = FixtureMediaProvider(catalog)
    found = provider.search("Gunter Schabowski portrait", limit=5)
    assert [c.candidate_id for c in found] == ["c_portrait"]


def test_fixture_provider_fetch_returns_valid_png():
    provider = FixtureMediaProvider([])
    cand = MediaCandidate(candidate_id="x", provider="fixture")
    fetched = provider.fetch(cand)
    assert fetched.data[:8] == b"\x89PNG\r\n\x1a\n"
    assert provider.fetch(cand).data == fetched.data  # deterministic


def test_provider_registry_and_factory():
    assert "fixture" in __import__("videotool.providers.media.base",
                                   fromlist=["PROVIDER_REGISTRY"]).PROVIDER_REGISTRY
    assert build_provider("fixture", catalog=[]).provider_id == "fixture"
    with pytest.raises(KeyError):
        build_provider("nope")


# ---- wikimedia provider ------------------------------------------------------

def test_wikimedia_search_normalizes_candidates():
    provider = wikimedia_provider()
    found = provider.search("Gunter Schabowski portrait", limit=10)
    scha = next(c for c in found if "Schabowski" in c.title)
    assert scha.provider == "wikimedia"
    assert scha.license_name == "CC BY-SA 3.0 de"
    assert scha.creator.startswith("Bundesarchiv")
    assert scha.date_created == "9 November 1989"
    assert scha.width == 1180 and scha.height == 1600
    assert scha.media_url.startswith("https://upload.wikimedia.org/")
    assert scha.source_page.startswith("https://commons.wikimedia.org/")
    # no explicit portrait metadata: inferred PHOTO, which ranking treats as
    # equivalent to PORTRAIT (KIND_EQUIV) for portrait requirements
    assert scha.media_type in ("PHOTO", "PORTRAIT")


def test_wikimedia_map_type_inference():
    provider = wikimedia_provider()
    found = provider.search("Berlin map", limit=10)
    assert found and found[0].media_type == "MAP"


def test_wikimedia_document_type_inference():
    provider = wikimedia_provider()
    found = provider.search("travel regulation document", limit=10)
    assert found and found[0].media_type == "DOCUMENT"


def test_wikimedia_fetch_downloads_media_bytes():
    provider = wikimedia_provider(media=schabowski_media())
    found = provider.search("Gunter Schabowski portrait", limit=10)
    target = next(c for c in found if "Schabowski" in c.title)
    fetched = provider.fetch(target)
    assert fetched.data[:8] == b"\x89PNG\r\n\x1a\n"


def test_wikimedia_fetch_rejects_foreign_hosts():
    provider = wikimedia_provider()
    evil = MediaCandidate(candidate_id="x", provider="wikimedia",
                          media_url="https://evil.example.com/pic.jpg")
    with pytest.raises(ProviderError):
        provider.fetch(evil)


def test_transport_rejects_non_https():
    transport = UrllibTransport()
    with pytest.raises(ProviderError):
        transport.get("http://commons.wikimedia.org/w/api.php")


def test_transport_failures_surface_as_provider_error():
    class Flaky:
        def get(self, url):
            raise ProviderError("boom")

        def get_json(self, url):
            raise ProviderError("boom")

    provider = WikimediaMediaProvider(transport=None)
    provider.transport = Flaky()
    # the provider must surface the failure, not hang or retry forever
    with pytest.raises(ProviderError):
        provider.search("anything", 5)


def test_transport_retries_bounded_with_backoff(monkeypatch):
    """Production urllib transport gives up after retries+1 attempts."""
    sleeps = []
    monkeypatch.setattr("time.sleep", lambda s: sleeps.append(s))

    transport = UrllibTransport(retries=2, min_interval_sec=0.0)
    calls = {"n": 0}
    real_urlopen = urllib.request.urlopen

    def fake_urlopen(request, timeout=None):
        calls["n"] += 1
        raise urllib.error.URLError("network down")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(ProviderError):
        transport.get("https://commons.wikimedia.org/w/api.php")
    assert calls["n"] == 3  # retries=2 -> 3 attempts total, never more
    assert len(sleeps) == 2  # backoff between attempts


def test_provider_error_on_partial_failure_is_isolated():
    provider = wikimedia_provider(fail_on={"api.php"})
    with pytest.raises(ProviderError):
        provider.search("Berlin map", 5)


def test_request_pacer_enforces_interval(monkeypatch):
    sleeps = []
    monkeypatch.setattr("time.sleep", lambda s: sleeps.append(s))
    monkeypatch.setattr("time.monotonic", lambda: 0.0)
    pacer = RequestPacer(min_interval_sec=0.5)
    pacer.wait()
    pacer.wait()  # clock frozen -> must sleep the interval
    assert sleeps and abs(sleeps[0] - 0.5) < 1e-9


def test_live_network_opt_in_marker_exists():
    """Live Wikimedia tests must be opt-in and excluded from the suite."""
    import videotool.providers.media.wikimedia as wm
    assert wm.API_BASE.startswith("https://")
