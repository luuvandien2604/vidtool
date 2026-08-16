# Phase 2A — Production Media Acquisition Report

Date: 2026-08-17 · Baseline `e68fecf` → this phase. Suite: **267 tests
passed** (185 Phase 1 + 82 Phase 2A). No renderer, no Phase 1 guarantee
regressed (all Phase 1 tests untouched and green).

## Implemented

The catalog-only media layer is replaced by a production acquisition
subsystem:

```
AssetRequirement -> semantic search plan (deterministic queries)
  -> provider search (fixture | Wikimedia Commons, the only network stage)
  -> normalized MediaCandidates
  -> semantic ranking (explainable, weighted, penalized)
  -> license gate (PD/CC0/CC BY/CC BY-SA only)
  -> score threshold (missing asset beats wrong asset)
  -> fetch -> download validation (magic/dims/size/HTML-fake)
  -> content-addressed cache (SHA-256 identity, dedupe, candidate index)
  -> MediaAsset + provenance + attribution
  -> strategy feasibility (unchanged all_of/any_of policies)
  -> media completeness gate (unchanged REQUIRED/PREFERRED/OPTIONAL)
```

## New modules

```
videotool/editorial/media/
  models.py          MediaType, MediaCandidate, MediaSearchPlan, ScoredCandidate,
                     AcquisitionTrace, MediaAttribution, MediaAcquisitionConfig
  query_planner.py   deterministic semantic queries (MEDIA_QUERY_VERSION); never
                     generic scene terms; surname alternates; narration fallback
  ranking.py         fold/token entity matching (unicode + aliases), decade-aware
                     dates, type equivalence, generic-image & reuse penalties,
                     explainability (MEDIA_RANKING_VERSION)
  type_inference.py  MAP/DOCUMENT/PORTRAIT/ILLUSTRATION rules (§13)
  licensing.py       allow/deny policy + quality (LICENSE_POLICY_VERSION)
  cache.py           content-addressed store + candidate-id index
  validation.py      magic sniffing, PNG/JPEG/GIF/BMP dimension parsers, HTML-
                     masquerade detection, size bounds (MEDIA_DOWNLOAD_VERSION)
  acquisition.py     orchestration: threshold, license, type policy, failure
                     isolation, trace (ACQUISITION_SERVICE_VERSION)
  catalog.py         Phase 1 CatalogAcquirer (kept; backs the fixture provider)

videotool/providers/media/
  base.py            MediaProvider protocol, registry, ProviderError, RequestPacer
  fixture.py         deterministic provider: catalog search + REAL synthesized
                     PNGs (stdlib zlib/struct, seeded noise)
  wikimedia.py       Commons MediaWiki API (generator=search + imageinfo +
                     extmetadata), injectable transport, HTTPS-only, host
                     allowlist, bounded retries with backoff, user agent
```

## Runner changes

`media_assets` became five fingerprinted stages: `media_search_plan`,
`media_candidates` (the only network stage — skipped on resume),
`media_assets`, `media_acquisition_trace`, `media_attribution`.
Fingerprints include version constants (`MEDIA_QUERY_VERSION`,
`MEDIA_RANKING_VERSION`, `LICENSE_POLICY_VERSION`, `MEDIA_DOWNLOAD_VERSION`,
`ACQUISITION_SERVICE_VERSION`), provider id/version, and the full
`MediaAcquisitionConfig`. Changing ranking semantics invalidates ranked
results; changing provider config invalidates search; changing unrelated
planner settings does not touch media (tested). CLI gained
`--media-provider {fixture,wikimedia}` (fixture default).

Domain: `MediaAsset` gained provenance (provider, source_page, media_url,
checksum, width/height, license_name, retrieval_ts, attribution,
score_components, score_penalties, selection_reason, candidate_id) — all
optional, `from_dict` tolerant to Phase 1 artifacts.

## Key behaviours (all regression-tested)

* specific beats generic: Schabowski portrait wins over a 4000px Berlin
  skyline (generic_image penalty); type mismatch REJECTS (a document never
  satisfies a portrait requirement even with an entity hit)
* license enforced: NC/ND/missing licenses rejected with reason; final mode
  never binds placeholder/unlicensed/corrupt media
* threshold: `minimum_candidate_score`; no force-select; feasibility + gate
  decide the outcome (REQUIRED unresolved -> final fails; draft labels
  placeholders)
* dedupe/reuse: identical bytes stored once (checksum identity); immediate
  reuse strongly penalized, repeats increasingly; cache hit by candidate id
  skips the network
* failure isolation: exploding fetch marks ONE requirement unresolved, the
  episode continues; bounded retries (retries+1 attempts, linear backoff)
* ids stay opaque: end-to-end test with `ACQ::beat_0003::portrait/2026`
  style ids flows through plan/search/assets/binding via mappings only
* acceptance (mocked Wikimedia, recorded fixtures): portrait/map/document
  requirements select the right candidates; generic Berlin imagery loses;
  generalization: Chernobyl (Pripyat/reactor) and Titanic (telegram/route)
  plan + rank correctly with zero Berlin-specific rules

## Network determinism

Normal tests never touch the network: the fixture provider is fully local,
and Wikimedia runs against `tests/fixtures/wikimedia/api_responses.json`
(recorded-style API shapes) through an injectable transport. A
`live_media` pytest marker is registered and excluded by default
(`addopts = "-m 'not live_media'"`).

## Packaging

`make test` → 267 passed. `make dist` → source-only zip (no venv, caches,
artifacts, media_cache).

## Known limitations

* Wikimedia provider is exercised via fixtures only in CI; live behaviour
  (real API drift, pagination, continuation) unverified until an opt-in
  `live_media` run against production
* No perceptual hashing yet (dedupe is checksum/id/url based, per spec §19)
* webp/svg dimension parsing not implemented (they validate, dimensions
  neutral); videos out of scope by design
* Single provider per run; no multi-provider fallback chain yet (spec §5
  defers it)
* Query planner is deterministic-only; the AI expansion interface is a
  later phase

## Next recommended step

Phase 2B — Word-Aligned Visual Timing (per the roadmap), with an opt-in
`live_media` smoke run against real Commons first.

## Commit

See `git log` — this report ships with the phase commit.
