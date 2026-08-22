# Phase 4 — AI Narration Scriptwriter + Fact Verification (Topic → Video)

## 1. Overview & Objectives

Phase 4 establishes an automated AI-driven pre-pipeline entry point (`Topic → Video`). Instead of requiring pre-written narration scripts, users can provide a high-level documentary topic (e.g. *"Bức tường Berlin"* or *"Apollo 11 Moon Landing"*), and the system autonomously:
1. Researches and writes a cinematic documentary narration script (`Narration`) calibrated to a target duration.
2. Extracts atomic verifiable claims (`FactualClaim`: dates, named entities, numbers/statistics, quotes, historical events) with character offsets calculated reliably in Python.
3. Performs live web-grounded fact checking (`FactVerificationProvider`), evaluating every claim as `VERIFIED`, `UNCERTAIN`, or `CONTRADICTED` with source citations.
4. Executes a safety verification gate (`Fact Verification Gate`) mirroring the `media_completeness` gate (draft mode warns and proceeds; final mode blocks publication on contradicted or uncertain claims).
5. Outputs a human-readable `fact_verification_report.json` artifact and cleanly hands off the `narration.json` to the existing downstream planning and rendering pipeline without modifying any downstream stage.

---

## 2. Architecture & Seams

```
               [ Topic Input & Target Duration ]
                              │
                              ▼
                [ NarrationWriterProvider ]
                ├── ClaudeNarrationWriterProvider
                └── GeminiNarrationWriterProvider
                              │
               (Narration Text + Verbatim Claims)
                              │
                              ▼
               [ Python Span Calculation Layer ]
              (finds exact character offsets safely)
                              │
                              ▼
              [ FactVerificationProvider ]
              ├── ClaudeWebSearchFactVerifier
              └── GeminiWebSearchFactVerifier (Google Search Grounding)
                              │
             (ClaimVerifications with Source URLs)
                              │
                              ▼
            [ Fact Verification Safety Gate ]
            ├── draft mode: WARN & PROCEED
            └── final mode: BLOCK on Contradicted/Uncertain
                              │
                              ▼
             [ Artifact Generation & Output ]
             ├── fact_verification_report.json
             └── narration.json ──▶ [ Downstream Pipeline ]
```

### 2.1 Domain Models (`videotool/domain/claims.py`)

- `ClaimType` (Enum): `DATE`, `ENTITY`, `NUMBER`, `QUOTE`, `EVENT`.
- `FactualClaim` (frozen dataclass):
  - `claim_id: str`
  - `text: str` (verbatim claim snippet)
  - `claim_type: ClaimType`
  - `narration_span: tuple[int, int]` (exact 0-indexed character offsets in the narration).
- `VerificationStatus` (Enum): `VERIFIED`, `UNCERTAIN`, `CONTRADICTED`.
- `ClaimVerification` (frozen dataclass):
  - `claim_id: str`
  - `status: VerificationStatus`
  - `confidence: float` (0.0 to 1.0)
  - `source_urls: list[str]` (grounding source URLs)
  - `note: str` (concise explanation of evidence found or missing).
- `FactVerificationReport` (dataclass):
  - Structured summary of topic, narration, all claims and verifications, counts (`verified_count`, `uncertain_count`, `contradicted_count`), gate status (`passed_gate`), and warnings.

### 2.2 Providers (`videotool/providers/`)

1. **`NarrationWriterProvider` Protocol**:
   - `ClaudeNarrationWriterProvider` (`"claude"`): Calls Anthropic Messages API (`https://api.anthropic.com/v1/messages`) via stdlib `urllib`.
   - `GeminiNarrationWriterProvider` (`"gemini"`): Calls Google Gemini API (`https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent`) via stdlib `urllib`.
2. **`FactVerificationProvider` Protocol**:
   - `ClaudeWebSearchFactVerifier` (`"claude"`): Uses web search to corroborate claims against independent web sources.
   - `GeminiWebSearchFactVerifier` (`"gemini"`): Uses Gemini REST API with native Google Search Grounding (`"tools": [{"googleSearch": {}}]`), parsing `groundingMetadata.groundingChunks` and `groundingSupports`.

---

## 3. Key Implementation Safeguards

1. **Zero External SDK Dependencies**:
   - All network calls use Python standard library `urllib.request`. No `anthropic` or `google-genai` package dependencies.
2. **CamelCase REST API Syntax**:
   - Gemini tool syntax strictly uses `{"googleSearch": {}}` matching Google's raw REST API schema.
3. **Python Span Calculation (Preventing LLM Token/Char Hallucinations)**:
   - LLMs only return the exact verbatim snippet in `text`.
   - Python computes `narration_span` using substring matching in the raw narration text (`narration_text.find(claim_text)`).
4. **Batch Verification Anti-Laziness Guard**:
   - System prompts strictly enforce returning 1:1 verifications for all input claims.
   - The Python layer validates `len(verifications) == len(claims)` and verifies every `claim_id` is accounted for.
5. **Absence of Proof is UNCERTAIN, Never VERIFIED**:
   - If web search or grounding fails to find direct corroborating evidence, the claim defaults to `UNCERTAIN`.

---

## 4. Fact Verification Safety Gate

| Gate Mode | CONTRADICTED Claims | UNCERTAIN Claims | Action |
| :--- | :--- | :--- | :--- |
| **`draft`** | Any | Any | **PROCEED** with explicit warnings; write findings to report artifact. |
| **`final`** (default) | $\ge 1$ | Any | **BLOCK & FAIL** (`FactVerificationGateError`). |
| **`final`** (default) | $0$ | $\ge 1$ (no override) | **BLOCK & FAIL** (`FactVerificationGateError`). |
| **`final`** (`--allow-uncertain-claims`) | $0$ | $\ge 1$ | **PROCEED** with warnings; write findings to report artifact. |
| **`final`** | $0$ | $0$ | **PASS** cleanly (100% verified). |

---

## 5. CLI Usage

Generate narration script and verify facts directly:
```bash
# Draft mode (fast iteration, logs warnings)
python -m videotool.cli write-narration "Bức tường Berlin" \
    --duration 90 \
    --language vi \
    --mode draft \
    --writer-provider gemini \
    --verifier-provider gemini \
    --out artifacts/ai_narration/narration.json \
    --report-out artifacts/ai_narration/fact_verification_report.json

# Final mode (strict gate enforcement)
python -m videotool.cli write-narration "The Fall of the Berlin Wall" \
    --duration 60 \
    --language en \
    --mode final \
    --writer-provider claude \
    --verifier-provider gemini \
    --allow-uncertain-claims
```

---

## 6. Test Suite & Validation

- **Offline Test Suite** (`make test`):
  - **420 passed**, 7 deselected in 174s.
  - Zero network calls, zero external API costs during regular CI/development.
  - Covers serialization, Python span calculations, gate logic matrix, mock Claude/Gemini responses, and intake orchestration.
- **Opt-in Live Test Suite** (`make test-live-llm` / `pytest -m live_llm`):
  - Tests live API calls to Claude and Gemini with Google Search Grounding when `ANTHROPIC_API_KEY` or `GEMINI_API_KEY` are provided in `.env`.

---

## 7. Known Limitations

1. **Web Search Grounding Coverage**:
   - Grounding reliability depends on web index availability for the specific topic. Very niche, highly localized, or obscure historical topics may yield fewer direct web search results, resulting in `UNCERTAIN` verdicts rather than `CONTRADICTED` or `VERIFIED`.
2. **LLM Verification vs Human Review**:
   - Automated fact verification significantly reduces hallucination risk and catches obvious factual errors. However, for broadcast documentary publication, editorial staff should review `fact_verification_report.json` and spot-check citations.
