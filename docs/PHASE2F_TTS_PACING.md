# Phase 2F Report: Production Azure Speech TTS & Speech Pacing Auditor

**Date**: 2026-08-21  
**Status**: Complete  
**Artifacts Generated**: `artifacts/tts_cache/`, `videotool/providers/azure_speech.py`, `videotool/editorial/pacing.py`  
**Test Coverage**: 412 passing tests in default suite (`make test`), 4 passing tests in render suite (`make test-render`).

---

## 1. Executive Summary & Goals

Phase 2E established audio track plumbing using deterministic placeholder silence. Phase 2F brings **production voice synthesis** and **speech pacing validation** to `videotool`:
1. **Azure Speech TTS Provider**: Integrated Microsoft Azure Cognitive Services Speech SDK for natural voice synthesis with word/syllable boundary timestamp extraction.
2. **Deterministic TTS Caching**: Content-addressed audio and timing cache (`artifacts/tts_cache/`) keyed by `stable_hash("azure_speech_v1", voice, text, lang)` to avoid redundant API billing and speed up debug re-renders.
3. **Speech Pacing & Rhythm Auditor**: Evaluates speech density, subtitle readability, and visual cut alignment across beats.
4. **Offline Test Safety**: 100% of the default test suite (`make test`) runs completely offline without network calls or API keys, while live Azure calls are gated behind `@pytest.mark.live_tts`.

---

## 2. Architecture & Modules

```
videotool/
├── domain/
│   └── timing.py            # BeatPacingMetric, PacingReport domain models
├── editorial/
│   └── pacing.py            # audit_speech_pacing (WPS/SPS density, CPS reading speed, cut alignment)
├── providers/
│   ├── azure_speech.py      # AzureSpeechAudioProvider, AzureSpeechTimingProvider, tts_cache
│   ├── audio.py             # Registered "azure" & "silence" in AUDIO_PROVIDERS
│   └── timing.py            # Registered "azure" & "deterministic" in TIMING_PROVIDERS
└── cli.py                   # --audio-provider azure|silence, --voice, pacing summary output
```

### Credentials & Security Discipline

Credentials are read strictly from environment variables:
- `AZURE_SPEECH_KEY`
- `AZURE_SPEECH_REGION`

If missing, the provider raises a clear `ValueError("Azure Speech credentials missing: Please set AZURE_SPEECH_KEY and AZURE_SPEECH_REGION environment variables.")`. Credentials are never hardcoded, prompted interactively, or printed to terminal logs.

---

## 3. Vietnamese vs English Speech Density (WPS vs SPS)

### Choice of Measurement Unit for Vietnamese

In Azure Cognitive Services Speech, `SpeechSynthesisWordBoundaryEventArgs` emits word-boundary events per spoken token. In Vietnamese, these tokens correspond to **syllables (tiếng)** rather than compound semantic words (e.g. *"thành phố"* emits two boundary events: *"thành"* and *"phố"*).

Rather than attempting lossy linguistic heuristics to glue syllables into compound words, `videotool` explicitly uses **SPS (Syllables Per Second)** for Vietnamese and **WPS (Words Per Second)** for English, documenting the thresholds clearly:

| Language | Metric Unit | Optimal Range | Rushed Threshold | Dragging Threshold | Max Subtitle Speed (CPS) |
|---|---|---|---|---|---|
| **Vietnamese (`vi`)** | **SPS** (Syllables/sec) | **2.4 – 4.8 SPS** (~1.4–2.6 words/s) | > **5.2 SPS** | < **1.8 SPS** | ≤ **22.0 CPS** |
| **English (`en`)** | **WPS** (Words/sec) | **2.0 – 3.4 WPS** | > **3.8 WPS** | < **1.4 WPS** | ≤ **17.0 CPS** |

### Visual Beat Cut Alignment

The pacing auditor validates that visual beat transitions land cleanly on natural spoken pauses (sentence/clause breaks) and flags cuts that slice mid-word (`w.start_sec < beat.end_sec < w.end_sec`).

---

## 4. Recommended Vietnamese Voices

The following Azure Neural voices were tested and are available for selection via `--voice`:

1. **`vi-VN-HoaiMyNeural`** (Default):
   - Female, warm, articulate, highly natural documentary tone.
   - Recommended for general history and educational documentaries.
2. **`vi-VN-NamMinhNeural`**:
   - Male, deep, authoritative broadcast tone.
   - Recommended for investigative, political, or dramatic subjects.

---

## 5. CLI Usage & Provenance Output

```bash
# Render with Azure Speech TTS (live synthesis with caching)
python -m videotool.cli render berlin_wall --audio-provider azure --voice vi-VN-HoaiMyNeural --out artifacts/berlin_wall_vi.mp4

# Sample output:
# rendered berlin_wall -> /home/luuvandien/videotool/artifacts/berlin_wall_vi.mp4 (66.21s)
#   audio: azure (production, 48000Hz, voice=vi-VN-HoaiMyNeural)
#   pacing: 3.8 SPS (score: 0.95), 18.2 CPS | cut alignment: 100%
```

---

## 6. Test Suite Structure

| Suite | Command | Test Count | Description |
|---|---|---|---|
| **Default Fast Suite** | `make test` | **412 passed** | Pure-Python unit tests covering all planning stages, pacing calculations, offline silence provider, and Azure error handling. Zero network calls. |
| **Render Suite** | `make test-render` | **4 passed** | FFmpeg integration tests verifying end-to-end audio muxing and silent video modes. |
| **Live TTS Suite** | `pytest -m live_tts` | Opt-in | Hits Azure Speech API to test live synthesis and cache round-trips. Skipped automatically when credentials are unset. |

---

## 7. Known Limitations

1. **Network Requirement for Live TTS**: Real voice synthesis requires network access to Azure Cognitive Services and active `AZURE_SPEECH_KEY` / `AZURE_SPEECH_REGION` credentials.
2. **Syllable-Level Tokens in Vietnamese**: Word boundary timestamps reflect single syllables (tiếng). Downstream phrase matching groups them by phrase timing intervals.
