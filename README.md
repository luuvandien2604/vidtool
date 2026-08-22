# videotool — AI Editorial Director (Phases 1, 2A, 2C, 2D, 2E, 2F Hardened, Phase 3A AI Editorial Director)

Automated documentary video production system. The pipeline transforms
narration + word timing into validated semantic artifacts (beats, art direction,
visual strategy, media acquisition, generative composition, semantic geometry,
motion keyframes, and timeline), and renders broadcast-quality 1080p@30fps video
via FFmpeg with positioned typography, vector connectors, burned-in narration subtitles,
and synchronized audio track plumbing.

> Style should be predictable. Composition should not.

## Quick start

```bash
# Set up virtual environment and run pure-Python test suite (448+ tests)
python3 -m venv .venv && .venv/bin/pip install pytest
make test

# Generate planning artifacts for the Berlin Wall fixture
python -m videotool.cli berlin_wall --artifacts artifacts

# Render the episode to MP4 (requires FFmpeg with libass + librsvg)
make test-render    # Run FFmpeg integration & end-to-end render tests (4 tests)
make render         # Render artifacts/berlin_wall.mp4
```

CLI render syntax:
```bash
# Render with default placeholder audio
python -m videotool.cli render berlin_wall --artifacts artifacts --out artifacts/berlin_wall.mp4

# Render silent video (no audio stream)
python -m videotool.cli render berlin_wall --artifacts artifacts --out artifacts/berlin_wall_silent.mp4 --no-audio

# Render with audible beat-boundary clicks
python -m videotool.cli render berlin_wall --artifacts artifacts --out artifacts/berlin_wall_clicks.mp4 --click-track
```

### System Prerequisites for Rendering

To render video clips, the following system tools must be installed:
- **FFmpeg 6+** with `libass` (subtitle rasterization) and `librsvg` (vector graphics decoding).

Verify system capabilities with:
```bash
ffmpeg -codecs | grep -i svg
```

## Pipeline

```
Narration + word timing
→ SemanticBeat segmentation (20 semantic functions, 3-8s beats)
→ EpisodeArtDirection (per-topic identity; Chernobyl ≠ Berlin ≠ Titanic)
→ Visual strategy planning (23 strategies, weighted scoring, anti-repetition)
→ Semantic asset requirements → media acquisition (relevance-scored, cached)
→ Strategy feasibility pass (plan-of-record vs actually available assets)
→ Generative composition (6 families, structural signatures)
→ Semantic geometry solver (coordinate mapping, safe zones, collision avoidance)
→ Motion planning (semantic keyframes, Ken Burns focus trajectories)
→ Timeline (renderer-agnostic; subtitles in bottom safe zone)
→ Frame planning engine (compiles visual elements, typography, and vector overlays)
→ Render SceneGraph Adapter (hierarchical scene graph representation)
→ Audio synthesis engine (deterministic placeholder / TTS provider seam)
→ FFmpeg renderer (per-beat isolated encode + lossless concat + subtitle burn-in + audio mux)
```

Domain invariants enforced by tests:

* identical composition signature reuse is forbidden; swapping photos does
  not defeat repetition detection
* one visual family runs at most 2 consecutive beats
* every strategy selection persists a human-readable reason
* every beat's timing comes from narration timing
* valid-JSON corruption of artifacts cannot silently resume (output hash +
  per-stage semantic validator)
* every beat has exactly one composition; final mode fails with unresolved
  REQUIRED media for the plan-of-record (Media Completeness Gate)
* connectors and route vectors render crisp SVG lines with directed arrowheads
* audio track duration matches video duration with pre-mux verification
* placeholder audio carries explicit, load-bearing provenance (`is_placeholder=True`)
* all beat clips share identical encoding parameters (H.264 High 4.1 yuv420p) for lossless concatenation

## Layout

```
videotool/domain/      typed models (narration, audio, geometry, timeline, EpisodeVisualMemory, etc.)
videotool/ai/          BeatAnalyzer / ArtDirectionGenerator interfaces + heuristics
videotool/editorial/   strategy planner, feasibility pass, composition families,
                       motion, timeline, media acquisition (query planning,
                       ranking, licensing, cache, validation), registries
videotool/providers/   media (fixture + Wikimedia), audio providers, and AI topic providers
videotool/render/      frame planning, SceneGraph adapter, ASS subtitles, SVG vectors, FFmpeg renderer
videotool/pipeline/    decoupled orchestration (PipelineContext, StageExecutor,
                       StageRegistry, ArtifactStore, ExecutionPolicy, stages/)
videotool/fixtures/    acceptance fixture (The Fall of the Berlin Wall)
tests/                 unit, integration, parity, benchmark suites (430+ pure-Python tests, 4 render tests)
docs/                  ARCHITECTURE_REVIEW.md, AUDIT.md, PHASE1_REPORT.md, PHASE2A_REPORT.md, ...
```

Runtime has zero third-party Python dependencies; development dependencies are `pytest`.
See `docs/ARCHITECTURE_REVIEW.md` for technical report on the Phase 2F architecture hardening.
