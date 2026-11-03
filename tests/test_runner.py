"""Runner tests — a fake driver proves the machinery: env, logs, ledger, cap, timeout. Offline."""

import sys
import time
from pathlib import Path

import pytest

from illumina_lab import workspace
from illumina_lab.experiment import RunSpec
from illumina_lab.orchestrator import ledger
from illumina_lab.orchestrator.runner import (
    DEFAULT_TIMEOUT_S,
    LocalRunner,
    timeout_from_env,
)

SPECHASH = "0123456789ab"
FAKES = Path(__file__).parent  # the fake driver lives next to the tests


def _run(run_id: str) -> RunSpec:
    return RunSpec(run_id=run_id, label="exp-x-smoke-20261103-1", canary_id="c", pack="honk", target="t", win="w", seed=1)


@pytest.fixture
def runner(tmp_path, monkeypatch):
    monkeypatch.setenv(workspace.ENV_VAR, str(tmp_path))
    return LocalRunner(timeout_s=10, python=Path(sys.executable), module="fake_driver", pythonpath=[FAKES])


def test_successful_run(runner):
    result = runner.wait(runner.submit(_run("r-ok"), SPECHASH))
    assert result.ok and result.returncode == 0
    run_dir = workspace.run_dir("exp-x-smoke-20261103-1", "r-ok")
    assert (run_dir / "state.json").is_file()
    assert (run_dir / "runspec.json").is_file()
    assert "fake driver ran r-ok" in (run_dir / "driver.log").read_text()
    assert [r["event"] for r in ledger.events()] == ["submitted", "running", "finished"]
    assert ledger.finished_cells(SPECHASH) == {("c", "w", 1)}


def test_failed_run(runner):
    result = runner.wait(runner.submit(_run("r-fail"), SPECHASH))
    assert not result.ok and result.returncode == 1
    assert ledger.latest_by_run()["r-fail"]["event"] == "failed"
    assert ledger.pending([_run("r-fail")], SPECHASH)  # failed re-queues on rerun


def test_timeout_kills_the_run(runner):
    runner.timeout_s = 0.5
    result = runner.wait(runner.submit(_run("r-slow"), SPECHASH))
    assert not result.ok and result.returncode == -9
    assert ledger.latest_by_run()["r-slow"]["event"] == "failed"


def test_timeout_disabled_waits_forever(runner):
    runner.timeout_s = None
    result = runner.wait(runner.submit(_run("r-ok"), SPECHASH))
    assert result.ok


def test_timeout_is_an_absolute_deadline_from_spawn(runner):
    runner.timeout_s = 10
    handle = runner.submit(_run("r-slow"), SPECHASH)
    handle.started -= 20  # the spawn clock already blew the budget before reaping
    t0 = time.monotonic()
    result = runner.wait(handle)
    assert not result.ok and result.returncode == -9
    assert time.monotonic() - t0 < 5  # killed on entry, not after a fresh window


def test_timeout_from_env(monkeypatch):
    monkeypatch.delenv("ILAB_RUN_TIMEOUT_S", raising=False)
    assert timeout_from_env() == DEFAULT_TIMEOUT_S
    monkeypatch.setenv("ILAB_RUN_TIMEOUT_S", "3600")
    assert timeout_from_env() == 3600
    monkeypatch.setenv("ILAB_RUN_TIMEOUT_S", "0")
    assert timeout_from_env() is None
    monkeypatch.setenv("ILAB_RUN_TIMEOUT_S", "garbage")
    assert timeout_from_env() == DEFAULT_TIMEOUT_S


def test_run_all_respects_the_cap(runner, tmp_path, monkeypatch):
    markers = tmp_path / "markers.txt"
    monkeypatch.setenv("FAKE_DRIVER_MARKERS", str(markers))
    cells = [_run(f"r-{i}") for i in range(3)]
    results = runner.run_all(cells, SPECHASH)
    assert [r.run_id for r in results] == ["r-0", "r-1", "r-2"]  # submission order
    lines = markers.read_text().splitlines()
    assert lines == [x for i in range(3) for x in (f"start r-{i}", f"end r-{i}")]  # strictly serial
