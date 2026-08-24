"""Tests for VideoTool Web UI local server and REST endpoints."""
from __future__ import annotations

import json
import threading
import time
import urllib.request
from pathlib import Path
import pytest

from videotool.artifacts import ArtifactStore
from videotool.fixtures import berlin_wall
from videotool.pipeline.runner import EpisodeInput, PipelineRunner
from videotool.web.server import create_web_server


@pytest.fixture(scope="module")
def running_server(tmp_path_factory):
    """Run Web UI server in a background thread for tests."""
    tmp_path = tmp_path_factory.mktemp("web_artifacts")
    store = ArtifactStore(str(tmp_path / "artifacts"))
    runner = PipelineRunner(store=store, mode="draft")
    ep_data = berlin_wall.load_episode()
    runner.run(EpisodeInput(**ep_data))

    port = 18099
    server = create_web_server(host="127.0.0.1", port=port, artifacts_dir=tmp_path / "artifacts")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.3)

    base_url = f"http://127.0.0.1:{port}"
    yield base_url, store, ep_data["episode_id"]

    server.shutdown()
    server.server_close()


def _get(url: str) -> tuple[int, dict | str, dict]:
    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, timeout=5.0) as resp:
            status = resp.status
            headers = dict(resp.headers)
            body_bytes = resp.read()
            try:
                data = json.loads(body_bytes.decode("utf-8"))
            except Exception:
                data = body_bytes.decode("utf-8")
            return status, data, headers
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        try:
            data = json.loads(body)
        except Exception:
            data = body
        return e.code, data, dict(e.headers)


def _post(url: str, payload: dict) -> tuple[int, dict]:
    data_bytes = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data_bytes,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=5.0) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8"))


def test_static_assets_served(running_server):
    base_url, _, _ = running_server

    # Index HTML
    status, body, headers = _get(f"{base_url}/")
    assert status == 200
    assert "VideoTool Studio" in body
    assert "text/html" in headers.get("Content-Type", "")

    # Style CSS
    status, body, headers = _get(f"{base_url}/style.css")
    assert status == 200
    assert "text/css" in headers.get("Content-Type", "")
    assert "--vox-gold" in body

    # App JS
    status, body, headers = _get(f"{base_url}/app.js")
    assert status == 200
    assert "application/javascript" in headers.get("Content-Type", "")


def test_episodes_and_status_api(running_server):
    base_url, _, _ = running_server

    # Episodes list
    status, data, _ = _get(f"{base_url}/api/episodes")
    assert status == 200
    assert "episodes" in data
    assert any(ep["fixture_name"] == "berlin_wall" for ep in data["episodes"])

    # Episode status
    status, data, _ = _get(f"{base_url}/api/episodes/berlin_wall/status")
    assert status == 200
    assert data["fixture_name"] == "berlin_wall"
    assert data["beat_count"] == 12
    assert data["total_duration_sec"] > 0


def test_shooting_script_api(running_server):
    base_url, _, _ = running_server

    status, data, _ = _get(f"{base_url}/api/episodes/berlin_wall/shooting-script")
    assert status == 200
    assert "script" in data
    assert len(data["script"]["beats"]) == 12
    assert "markdown" in data


def test_revision_and_overrides_api(running_server):
    base_url, _, _ = running_server

    # 1. Propose valid structured revision
    status, prop = _post(f"{base_url}/api/revise/propose", {
        "fixture": "berlin_wall",
        "feedback_text": "Beat 4: caption Hungary -> Escape route begins",
        "provider": "mock",
    })
    assert status == 200
    assert prop["is_valid"] is True
    assert prop["new_value"] == "Escape route begins"
    prop_id = prop["proposal_id"]

    # 2. Propose ungrounded revision
    status, ungrounded = _post(f"{base_url}/api/revise/propose", {
        "fixture": "berlin_wall",
        "feedback_text": "Beat 4: caption Hungary -> Escape to London",
        "provider": "mock",
    })
    assert status == 200
    assert ungrounded["is_valid"] is False
    assert "London" in ungrounded["rejection_reason"]

    # 3. Apply proposal
    status, apply_res = _post(f"{base_url}/api/revise/apply", {
        "fixture": "berlin_wall",
        "proposal_id": prop_id,
    })
    assert status == 200
    assert apply_res["success"] is True
    assert len(apply_res["overrides"]) >= 1

    # 4. Check overrides list
    status, ovr_data, _ = _get(f"{base_url}/api/episodes/berlin_wall/overrides")
    assert status == 200
    assert len(ovr_data["overrides"]) >= 1
    ovr_id = ovr_data["overrides"][0]["override_id"]

    # 5. Delete override
    status, del_res = _post(f"{base_url}/api/episodes/berlin_wall/overrides/delete", {
        "override_id": ovr_id,
    })
    assert status == 200
    assert del_res["success"] is True


def test_command_execution_api(running_server):
    base_url, _, _ = running_server

    # Execute shooting-script generation job
    status, res = _post(f"{base_url}/api/commands/execute", {
        "command": "shooting-script",
        "fixture": "berlin_wall",
    })
    assert status == 200
    assert "job_id" in res
    job_id = res["job_id"]

    # Poll job status
    time.sleep(1.0)
    status, job_data, _ = _get(f"{base_url}/api/commands/jobs/{job_id}?offset=0")
    assert status == 200
    assert "status" in job_data
    assert "lines" in job_data


def test_create_custom_topic_episode_api(running_server):
    base_url, artifacts_dir, _ = running_server

    # Create new custom episode
    status, res = _post(f"{base_url}/api/episodes/create", {
        "topic": "The Sinking of the Titanic 1912",
        "episode_id": "test_titanic",
        "script_text": "In 1912 the Titanic collided with an iceberg and sank into the freezing Atlantic ocean.",
        "media_provider": "fixture",
        "audio_provider": "silence",
        "ai_provider": "mock",
        "auto_render": False,
    })
    assert status == 200
    assert res["success"] is True
    assert res["episode_id"] == "test_titanic"
    assert "job_id" in res

    # Wait for background job to finish
    time.sleep(1.5)

    # Check that custom episode appears in /api/episodes
    status, ep_data, _ = _get(f"{base_url}/api/episodes")
    assert status == 200
    ep_ids = [ep["episode_id"] for ep in ep_data["episodes"]]
    assert "test_titanic" in ep_ids

    # Delete episode
    status, del_res = _post(f"{base_url}/api/episodes/test_titanic/delete", {})
    assert status == 200
    assert del_res["success"] is True
    assert del_res["episode_id"] == "test_titanic"

    # Verify no longer in list
    status, ep_data2, _ = _get(f"{base_url}/api/episodes")
    assert status == 200
    ep_ids2 = [ep["episode_id"] for ep in ep_data2["episodes"]]
    assert "test_titanic" not in ep_ids2

