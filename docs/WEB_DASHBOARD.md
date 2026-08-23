# VideoTool Local Web UI Dashboard

The VideoTool Studio Web UI Dashboard provides a local graphical interface for reviewing documentary episodes, streaming rendered videos with beat synchronization, inspecting shooting scripts, managing durable editorial overrides, and running pipeline stages with live terminal logs.

---

## 1. Quick Start

Start the dashboard using the CLI:

```bash
python -m videotool.cli serve [--port 8080] [--host 127.0.0.1] [--artifacts artifacts] [--open]
```

- **URL**: [http://127.0.0.1:8080/](http://127.0.0.1:8080/)
- **Zero Runtime Dependencies**: The backend uses Python's standard library `http.server.ThreadingHTTPServer` and the frontend is pure HTML5 + Vanilla CSS + Vanilla JS.

---

## 2. Key Features

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       VideoTool Local Web UI (Port 8080)                    │
├───────────────────────┬─────────────────────────────┬───────────────────────┤
│    Sidebar / Controls │   Center: Video & Scripts   │  Right: Revision & Log│
├───────────────────────┼─────────────────────────────┼───────────────────────┤
│ • Episode Selector    │ • HTML5 Video Player        │ • Feedback Studio:    │
│ • Episode Metadata    │   (Byte-Range Seeking)      │   - Free-text critique│
│ • Pipeline Runner:    │ • Beat Marker Timeline      │   - Propose Revision  │
│   - Plan (Draft/Final)│ • Shooting Script Viewer    │   - Diff preview      │
│   - Render (FFmpeg)   │   - 13-Column Table         │   - 1-Click Apply     │
│   - Generate Script   │   - Raw JSON Inspector      │ • Active Overrides    │
│ • Auto-refresh status │ • Media Asset Previews      │ • Real-time Log Term  │
└───────────────────────┴─────────────────────────────┴───────────────────────┘
```

### 2.1. Interactive Video Player & Beat Marker Synchronizer
- Embedded HTML5 video player streaming from `/api/episodes/{fixture}/video`.
- **HTTP 206 Byte-Range Streaming**: Enables smooth scrubbing and seeking to any timestamp without buffering the entire file.
- **Beat Track**: Proportionally sized horizontal bar displaying all 12 beats. Clicking any beat jumps playback directly to that beat's entrance time.
- **Active Beat Info**: Automatically updates narration text, visual family, and strategy as video plays.

### 2.2. Shooting Script Inspector (13-Column Table & JSON)
- **13-Column Markdown/HTML Table**: Displays index, element ID, visual type, display content, content source (`[raw]`, `[ai_authored]`, `[override]`), normalized bounds, entrance/exit timestamps, motion, and semantic rationale.
- **Filter & Search**: Real-time text search and beat dropdown filter.
- **Raw JSON Manifest**: Complete structured JSON inspection.

### 2.3. Feedback Revision Studio
- **Input Critique**: Enter feedback (e.g. `Beat 4: caption Hungary -> Escape route begins`).
- **Propose**: Triggers `RevisionService` with anti-hallucination validation.
- **Diff Preview**: Displays Old vs New values, target node, rationale, and grounding validation badge (`VALID` or `REJECTED`).
- **1-Click Apply**: Commits the override to `editorial_overrides.json` and updates the dashboard immediately.
- **Active Overrides Manager**: View and delete durable overrides with a single click.

### 2.4. Interactive Pipeline Execution & Live Terminal
- 1-Click execution for:
  - Planning Pipeline (`--mode draft/final`, `--editorial-ai-enabled`).
  - Render Episode Video (`--audio-provider silence/azure/none`, `--click-track`).
  - Shooting Script Generation.
- **Real-Time Log Stream**: Polling terminal console displaying colored logs (`$` commands in yellow, errors in red, successes in green).

---

## 3. REST API Reference

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | Serves dashboard SPA (`index.html`) |
| `GET` | `/api/episodes` | Lists available episodes and artifacts status |
| `GET` | `/api/episodes/{fixture}/status` | Returns duration, beat count, video and audio info |
| `GET` | `/api/episodes/{fixture}/shooting-script` | Returns `shooting_script.json` and rendered markdown |
| `GET` | `/api/episodes/{fixture}/video` | Streams MP4 video with HTTP 206 Partial Content support |
| `GET` | `/api/episodes/{fixture}/overrides` | Lists active editorial overrides |
| `POST` | `/api/episodes/{fixture}/overrides/delete` | Deletes an override by `override_id` |
| `POST` | `/api/revise/propose` | Proposes a structured revision from feedback string |
| `POST` | `/api/revise/apply` | Commits approved proposal to `editorial_overrides.json` |
| `POST` | `/api/commands/execute` | Spawns background pipeline/render task |
| `GET` | `/api/commands/jobs/{job_id}?offset={offset}` | Streams task logs incrementally |
