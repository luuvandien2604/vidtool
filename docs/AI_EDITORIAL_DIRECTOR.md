# AI Editorial Director Architecture (Phase 3A)

## 1. Overview & Core Invariants

The **AI Editorial Director** acts as an advisory intelligence layer for the `vidtool` documentary engine. It assists in determining visual goals, candidate visual strategies, and emotional/informational priorities without weakening or replacing the deterministic editorial and rendering pipeline.

The architecture strictly adheres to the core principle:

```text
AI proposes.
Domain defines invariants.
Editorial engine decides.
Pipeline orchestrates.
Renderer executes.
```

### Safety & Execution Boundaries

The AI Director is **strictly advisory** and **untrusted**:
- **NEVER** constructs or issues FFmpeg commands.
- **NEVER** computes pixel coordinates, bounding boxes, or typography layout parameters.
- **NEVER** writes subtitles or manipulates ASS tags.
- **NEVER** invents strategy IDs, visual family IDs, or asset filenames outside the registered catalog.
- **NEVER** overrides deterministic hard constraints (such as visual family streak limits).

---

## 2. Architecture & Data Flow

```text
SemanticBeat
      │
      ▼
ArtDirection
      │
      ▼
EpisodeVisualMemory
      │
      ▼
StrategyCatalog
      │
      ▼
EditorialContextProjector (projector.py)
      │
      ▼
EditorialDirectorRequest
      │
      ▼
┌─────────────────────────────────┐
│ AI EditorialDirector (director) │ (Mock / Gemini)
└────────────────┬────────────────┘
                 │
                 ▼
           EditorialIntent
                 │
                 ▼
     Strict Validator (validator.py)
                 │
           ┌─────┴──────┐
           │            │
     is_valid=True  is_valid=False / Error
           │            │
           ▼            ▼
     AI Signals      Fallback Intent
           │            │
           └─────┬──────┘
                 ▼
         Deterministic
         StrategyPlanner (Bounded Hybrid Ranking)
                 │
                 ▼
          SelectedStrategy
                 │
                 ▼
          Existing Pipeline Stages (Unchanged)
```

---

## 3. Component Specification

The package is isolated under `videotool/editorial/director/`:

```text
videotool/editorial/director/
├── __init__.py
├── models.py       # Domain models: EditorialIntent, EditorialDirectorRequest, StrategyDescriptor, ValidationResult
├── projector.py    # Context Projector: transforms domain states into clean, compact request DTOs
├── prompt.py       # Deterministic prompt formatting (EDITORIAL_DIRECTOR_PROMPT_VERSION = 1)
├── validator.py    # Strict semantic & catalog validation layer
├── fallback.py     # Deterministic fallback intent generation
├── director.py     # EditorialDirector advisory coordinator
└── providers/
    ├── __init__.py
    ├── base.py     # EditorialDirectorProvider protocol
    ├── mock.py     # MockEditorialDirectorProvider (offline deterministic mock)
    └── gemini.py   # GeminiEditorialDirectorProvider (stdlib urllib, Google Gemini REST API)
```

### 3.1 `EditorialDirectorRequest` (Input Projection)
`EditorialContextProjector.project_beat()` isolates the AI from internal engine state. The request receives:
- Beat semantics (`beat_id`, `semantic_function`, `narration_text`, `entities`, `locations`, `dates`, `information_density`).
- Art direction summary (`art_direction_motifs`, `accent_color`).
- Visual history projection (`recent_families`, `recent_strategies`, `family_streak`).
- Sanitized `StrategyDescriptor` items (ID, compatible functions, visual family, storytelling note).
- Request fingerprint via deterministic `stable_hash()`.

### 3.2 `EditorialIntent` (AI Output Schema)
```json
{
  "schema_version": 1,
  "beat_id": "beat_001",
  "story_role": "TURNING_POINT",
  "visual_goal": "Show historic crowd surge at the border",
  "information_priority": ["Gunter Schabowski", "press conference note"],
  "information_density": 0.75,
  "emotional_goal": "dramatic_tension",
  "candidate_strategies": ["archival_portrait", "silhouette_to_archive_reveal"],
  "preferred_visual_families": ["archival_subject"],
  "avoid_visual_families": ["geographic_map"],
  "must_show": ["Schabowski"],
  "must_not_show": [],
  "emphasis": "The accidental announcement",
  "reason": "Close focus on speaker underscores historical turning point.",
  "confidence": 0.95,
  "is_fallback": false
}
```

### 3.3 Strict Validator (`validator.py`)
Proposals are checked against `STRATEGY_CATALOG` and `FAMILIES`:
1. Every candidate strategy ID must exist in the catalog.
2. Every candidate's visual family must exist.
3. Strategies whose family is at the consecutive streak limit (`streak_len >= 2`) are filtered out.
4. **Viability Rule**: `ValidationResult.is_valid` is `True` if and only if `len(accepted_strategies) > 0`. If all candidates are rejected, `is_valid = False` and the director falls back to catalog defaults.

### 3.4 Bounded Hybrid Strategy Ranking (`strategies.py`)
The deterministic `StrategyPlanner` remains the final authority:
- Bounded delta: `MAX_AI_DELTA = 0.10`
- If candidate strategy is in `intent.candidate_strategies`:
  `ai_delta += MAX_AI_DELTA * ai_weight`
- If candidate family is in `intent.avoid_visual_families`:
  `ai_delta -= MAX_AI_DELTA * ai_weight`
- If candidate family is in `intent.preferred_visual_families`:
  `ai_delta += (MAX_AI_DELTA * 0.5) * ai_weight`
- `total = clamp(deterministic_score + ai_delta, 0.0, 1.0)`
- **Legacy Parity**: When AI is disabled (`editorial_ai_enabled=False` or `intents=None`), scoring and selection remain 100% byte-for-byte identical to legacy deterministic output.

---

## 4. Enabling and Disabling AI

By default, AI is **disabled** (`editorial_ai_enabled=False` in `ExecutionPolicy`).

To enable AI assistance:

```python
from videotool.pipeline.policy import ExecutionPolicy
from videotool.pipeline.runner import PipelineRunner

policy = ExecutionPolicy(
    mode="final",
    editorial_ai_enabled=True,
    editorial_ai_provider="mock",  # or "gemini"
)
runner = PipelineRunner(store=store, policy=policy)
```

When enabled, the pipeline automatically persists the `editorial_intents.json` artifact for full observability and auditing.
