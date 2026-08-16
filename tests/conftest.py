import pytest

from videotool.artifacts import ArtifactStore
from videotool.fixtures.berlin_wall import load_episode
from videotool.pipeline.runner import EpisodeInput, PipelineRunner


@pytest.fixture(scope="session")
def berlin_run(tmp_path_factory):
    """One pipeline execution of the acceptance fixture, reused by tests."""
    data = load_episode()
    store = ArtifactStore(tmp_path_factory.mktemp("artifacts"))
    runner = PipelineRunner(store, mode="final")
    result = runner.run(EpisodeInput(**data))
    assert result.ok, result.validation
    return {"data": data, "store": store, "result": result}
