"""Driver tests — env stamping, state dump, error path — with a fake illumina.cli (offline, D9)."""

import dataclasses
import json
import os
import sys
import types
from pathlib import Path

import pytest
from pydantic import BaseModel

from illumina_lab import driver, workspace
from illumina_lab.experiment import ModelConfig, RunSpec

SPEC = RunSpec(
    run_id="exp-deadbeef-smoke-20261103-1-honk-precompile-success-unchecked-griefing-s1",
    label="exp-deadbeef-smoke-20261103-1",
    canary_id="honk-precompile-success-unchecked",
    pack="honk",
    target="precompile-success-unchecked",
    win="griefing",
    seed=1,
    models=ModelConfig(default="anthropic:claude-sonnet-4-6", roles={"build": "openai:mimo-v2-flash"}),
)

_TOUCHED = ("ILLUMINA_", "LANGSMITH_", "ILAB_")


@pytest.fixture(autouse=True)
def _clean_env_and_modules(monkeypatch, tmp_path):
    monkeypatch.setenv(workspace.ENV_VAR, str(tmp_path))
    snapshot = {k: v for k, v in os.environ.items() if k.startswith(_TOUCHED)}
    yield
    for k in [k for k in os.environ if k.startswith(_TOUCHED)]:
        os.environ.pop(k)
    os.environ.update(snapshot)
    sys.modules.pop("illumina", None)
    sys.modules.pop("illumina.cli", None)


def _fake_illumina(state=None, error=None):
    cli = types.ModuleType("illumina.cli")
    if error:

        def run_graph(pack, thread_id, win, run_id):
            raise RuntimeError(error)
    else:

        def run_graph(pack, thread_id, win, run_id):
            return None, (state if state is not None else {"findings": [], "run_id": run_id})

    cli.run_graph = run_graph
    sys.modules["illumina"] = types.ModuleType("illumina")
    sys.modules["illumina.cli"] = cli


def test_stamp_env_maps_the_runspec():
    env = driver.stamp_env(SPEC)
    assert env["ILLUMINA_RUN_LABEL"] == SPEC.label
    assert env["ILLUMINA_HONK_TARGET"] == "precompile-success-unchecked"
    assert env["ILLUMINA_MODEL"] == "anthropic:claude-sonnet-4-6"
    assert env["ILLUMINA_MODEL_BUILD"] == "openai:mimo-v2-flash"
    assert env["LANGSMITH_PROJECT"] == SPEC.label
    assert env["ILLUMINA_STORE"].endswith("vendor/azimo/store")
    assert env["ILLUMINA_CACHE"].endswith("illumina-cache")


def test_stamp_env_omits_an_unset_default_model():
    env = driver.stamp_env(SPEC.model_copy(update={"models": ModelConfig()}))
    assert "ILLUMINA_MODEL" not in env
    assert "ILLUMINA_MODEL_BUILD" not in env


def test_main_dumps_state(tmp_path):
    _fake_illumina(state={"findings": [{"status": "confirmed"}], "poc": Path("x")})
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(SPEC.model_dump_json())
    assert driver.main([str(spec_path)]) == 0
    run = workspace.run_dir(SPEC.label, SPEC.run_id)
    state = json.loads((run / "state.json").read_text())
    assert state["findings"] == [{"status": "confirmed"}]
    assert state["poc"] == "x"  # a Path serialized to str
    assert json.loads((run / "runspec.json").read_text())["run_id"] == SPEC.run_id
    provenance = json.loads((run / "provenance.json").read_text())
    assert len(provenance["azimo_sha"]) == 40 and provenance["run_id"] == SPEC.run_id
    assert os.environ["ILLUMINA_HONK_TARGET"] == "precompile-success-unchecked"


def test_main_error_path(tmp_path):
    _fake_illumina(error="boom")
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(SPEC.model_dump_json())
    assert driver.main([str(spec_path)]) == 1
    err = json.loads((workspace.run_dir(SPEC.label, SPEC.run_id) / "error.json").read_text())
    assert "RuntimeError: boom" in err["traceback"]


def test_default_serializes_the_state_leaves():
    class M(BaseModel):
        x: int = 1

    @dataclasses.dataclass
    class D:
        y: str = "z"

    back = json.loads(json.dumps({"m": M(), "d": D(), "p": Path("/a"), "s": {"b", "a"}, "o": object()}, default=driver._default))
    assert back["m"] == {"x": 1}
    assert back["d"] == {"y": "z"}
    assert back["p"] == "/a"
    assert back["s"] == ["a", "b"]
    assert isinstance(back["o"], str)
