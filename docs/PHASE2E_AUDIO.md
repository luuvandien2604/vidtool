# Phase 2E Report: Audio Plumbing (Placeholder Provider)

**Date**: 2026-08-21  
**Status**: Complete  
**Artifacts Generated**: `artifacts/berlin_wall.mp4` (1080p@30fps H.264 + 48kHz AAC Mono, 66.21s, duration matched)  
**Test Coverage**: 406 passing tests in default suite (`make test`), 4 passing tests in render suite (`make test-render`).

---

## 1. Executive Summary & Goals

Phase 2D delivered the first working video renderer for the `videotool` pipeline, but rendered silent video clips. Phase 2E establishes the complete **audio plumbing subsystem**:
- A dedicated, decoupled audio provider seam (`NarrationAudioProvider` Protocol).
- A deterministic, pure-Python placeholder audio generator (`SyntheticSilenceAudioProvider`).
- Load-bearing provenance tracking via `NarrationAudio.is_placeholder`.
- Combined single-pass subtitle burn-in and audio muxing in `FFmpegRenderer` with pinned encoding parameters.
- Pre-mux duration matching verification with loud failure on disagreement.
- CLI integration (`--audio-provider`, `--no-audio`, `--click-track`) with visible audio provenance logging.

Audio is strictly a render-time concern: no changes were made to `STAGES` in `pipeline/runner.py` or any Phase 1–2D planning logic.

---

## 2. Architecture & Modules

```
videotool/
├── domain/
│   └── narration.py        # NarrationAudio dataclass (audio_path, duration_sec, is_placeholder)
├── providers/
│   └── audio.py            # NarrationAudioProvider Protocol, SyntheticSilenceAudioProvider, registry
├── render/
│   ├── interfaces.py       # Renderer protocol with optional audio, RenderResult audio metadata
│   ├── ffmpeg_renderer.py  # Pre-mux duration check, combined subtitle/audio pass, stream verification
│   └── __init__.py         # render_episode entry point with audio provider synthesis
└── cli.py                  # --audio-provider, --no-audio, --click-track flags and provenance output
```

### Domain Model & Provenance Discipline

`NarrationAudio` in `videotool/domain/narration.py`:
- `audio_path: Path`
- `duration_sec: float` (derived directly from canonical `NarrationTiming.duration_sec`)
- `sample_rate: int = 48000`
- `channels: int = 1`
- `provider: str = "synthetic_silence"`
- `provider_version: int = 1`
- **`is_placeholder: bool = True`**

The `is_placeholder` flag is load-bearing: downstream automated QC checks and user-facing CLI outputs inspect this flag to ensure synthetic placeholder audio is never mistaken for production voice synthesis.

### Deterministic Placeholder Provider (`videotool/providers/audio.py`)

`SyntheticSilenceAudioProvider`:
- Written in pure Python using the stdlib `wave` and `struct` modules (zero third-party dependencies, no ffmpeg/numpy).
- Generates a 48000 Hz, 16-bit PCM mono WAV file of exact duration matching `timing.duration_sec`.
- Default mode generates pure digital silence.
- Opt-in `click_track=True` mode emits a clean 880 Hz tone pulse (50ms duration, amplitude ~18% full scale) at each beat boundary extracted from the `timeline` artifact segments.

Registry pattern:
```python
AUDIO_PROVIDERS: dict[str, type] = {"silence": SyntheticSilenceAudioProvider}
```

### Pinned Audio Muxing (`videotool/render/ffmpeg_renderer.py`)

Rather than adding a separate FFmpeg pass, audio muxing is integrated directly into Step 3 (the final subtitle burn-in pass):
- **Pre-Mux Duration Assertion**: Enforces `abs(audio.duration_sec - plan.total_duration_sec) <= 0.05s`. If audio and video frame plan durations disagree, the renderer fails loudly.
- **Pinned Audio Encoding Parameters**:
  - Codec: `-c:a aac`
  - Bitrate: `-b:a 128k`
  - Sample Rate: `-ar 48000`
  - Channels: `-ac 1` (mono)
- **Silent Mode**: When `--no-audio` or `audio=None` is specified, FFmpeg explicitly applies `-an` to output a clean video-only stream.

`ffprobe` output inspection:
```json
{
  "streams": [
    {
      "index": 0,
      "codec_name": "h264",
      "profile": "High",
      "width": 1920,
      "height": 1080,
      "pix_fmt": "yuv420p"
    },
    {
      "index": 1,
      "codec_name": "aac",
      "sample_rate": "48000",
      "channels": 1,
      "duration": "66.206000"
    }
  ],
  "format": {
    "duration": "66.206000",
    "size": "5875792"
  }
}
```

---

## 3. CLI Options & Provenance Visibility

The `render` subcommand exposes:
- `--audio-provider silence` (default): Synthesizes placeholder audio and muxes it into output.
- `--no-audio`: Skips audio synthesis and outputs silent video.
- `--click-track`: Injects beat boundary audio pulses for visual cut inspection.

Example CLI outputs:
```bash
$ python -m videotool.cli render berlin_wall --out artifacts/berlin_wall.mp4
rendered berlin_wall -> /home/luuvandien/videotool/artifacts/berlin_wall.mp4 (66.21s)
  audio: silence (placeholder)

$ python -m videotool.cli render berlin_wall --out artifacts/berlin_wall_silent.mp4 --no-audio
rendered berlin_wall -> /home/luuvandien/videotool/artifacts/berlin_wall_silent.mp4 (66.20s)
  audio: none (silent)

$ python -m videotool.cli render berlin_wall --out artifacts/berlin_wall_clicks.mp4 --click-track
rendered berlin_wall -> /home/luuvandien/videotool/artifacts/berlin_wall_clicks.mp4 (66.21s)
  audio: silence (placeholder) [click_track]
```

---

## 4. Test Suite Structure

| Suite | Command | Test Count | Description |
|---|---|---|---|
| **Default Fast Suite** | `make test` | **406 passed** | Pure-Python unit tests covering all 18 planning stages, frame planning, and audio provider tests (exact duration, determinism, WAV headers, click tracks). |
| **Render Suite** | `make test-render` | **4 passed** | FFmpeg integration tests verifying prerequisite checks, registry resolution, end-to-end audio muxing, and `--no-audio` mode. |

---

## 5. Known Limitations (Explicit & Honest)

1. **Narration Speech Pacing is Unvalidated**: Phase 2E implements audio *plumbing* with placeholder audio (`SyntheticSilenceAudioProvider`). It does not synthesize real human speech or validate whether beat durations, transitions, and camera motions "feel right" against natural speech rhythms. Pacing validation remains an open question until a real TTS engine is integrated.
2. **Single-Track Audio Only**: The audio pipeline currently muxes a single mono narration track. Background music (BGM), sound effects (SFX), and audio ducking curves are deferred to later audio design phases.
3. **Synthetic Silence is Monophonic**: The placeholder provider generates single-channel audio; multi-channel spatial audio or stereo mixing is not implemented.

---

## 6. Next Recommended Step

1. **Production TTS Provider Integration**: Implement a real `NarrationAudioProvider` (e.g. ElevenLabs, Azure Neural TTS, or local Piper TTS) satisfying the protocol (`synthesize(narration, timing, out_path) -> NarrationAudio`) and register it under `AUDIO_PROVIDERS`.
2. **Pacing & Rhythm Audit**: With real speech audio available, evaluate whether beat boundary cuts, visual entrance staggering, and motion emphasis align naturally with vocal cadences and breath pauses.
3. **Multi-Track Audio Mixer**: Introduce background music bed acquisition, volume automation, and sidechain ducking under narration dialogue.
