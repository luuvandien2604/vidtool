# videotool — AI Editorial Director (Phase 1 + 1.1 + 1.2)

Automated documentary video production system. Phase 1 delivers the
**planning architecture**: narration in, fully validated editorial plan out.
Phase 1.1 hardens resume (fingerprinted invalidation), stage-level
validation/repair/fallback and asset feasibility. Phase 1.2 adds artifact
integrity (output hashes — valid-JSON corruption cannot silently resume),
composition completeness, the plan-of-record Media Completeness Gate, and
motion/timeline validators. No rendering yet.

> Style should be predictable. Composition should not.

## Quick start

```bash
python3 -m venv .venv && .venv/bin/pip install pytest   # dev-only dep
make test                                              # 172 tests
make run                                               # fixture -> artifacts/
make dist        # source-only zip (no .venv / caches / artifacts)
```

The CLI writes the intermediate artifacts under `artifacts/berlin_wall_phase1/`
and prints per-stage statuses (`computed` / `resumed` / `invalidated` with
input fingerprints), plus any repairs and feasibility adjustments. Re-running
resumes from valid artifacts; changed inputs (narration, subject, catalog,
mode, planner config) invalidate exactly the dependent stages. `--mode draft`
allows placeholder assets; `--force` recomputes everything.

## Pipeline

```
Narration + word timing
→ SemanticBeat segmentation (20 semantic functions, 3-8s beats)
→ EpisodeArtDirection (per-topic identity; Chernobyl ≠ Berlin ≠ Titanic)
→ Visual strategy planning (23 strategies, weighted scoring, anti-repetition)
→ Semantic asset requirements → media acquisition (relevance-scored)
→ Strategy feasibility pass (plan-of-record vs actually available assets)
→ Generative composition (6 families, structural signatures)
→ Motion planning (every event has a semantic reason; camera stays stable)
→ Timeline (renderer-agnostic; subtitles independent in a safe zone)
→ Per-stage validation + deterministic fallbacks → final editorial QC
```

Domain invariants enforced by tests:

* identical composition signature reuse is forbidden; swapping photos does
  not defeat repetition detection
* one visual family runs at most 2 consecutive beats
* every strategy selection persists a human-readable reason
* every beat's timing comes from narration timing
* placeholder assets are impossible in final mode
* valid-JSON corruption of artifacts cannot silently resume (output hash +
  per-stage semantic validator)
* every beat has exactly one composition; final mode fails with unresolved
  REQUIRED media for the plan-of-record (Media Completeness Gate)
* Berlin vocabulary exists only in `videotool/fixtures/berlin_wall.py`

## Layout

```
videotool/domain/      typed models (stdlib only)
videotool/ai/          BeatAnalyzer / ArtDirectionGenerator interfaces + heuristics
videotool/editorial/   strategy planner, feasibility pass, composition families,
                       motion, timeline, media acquisition, validation
videotool/pipeline/    stage runner with fingerprinted resume
videotool/fixtures/    acceptance fixture (The Fall of the Berlin Wall)
tests/                 unit + acceptance suite (122 tests)
docs/                  AUDIT.md, PHASE1_REPORT.md, PHASE11_HARDENING.md, example_trace.md
docs/references/       golden reference video (motion language only)
```

Runtime has zero third-party dependencies. Phase 1 has no renderer; see
`docs/PHASE1_REPORT.md` for scope/limitations and
`docs/PHASE11_HARDENING.md` for the hardening pass.
