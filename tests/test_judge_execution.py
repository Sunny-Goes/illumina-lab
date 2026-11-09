"""Execution-level attribution tests — fabricated runs and store, scripted replays (offline)."""

import json
from datetime import datetime, timezone

import pytest

from illumina_lab import workspace
from illumina_lab.canaries.models import RegistryError
from illumina_lab.judge import attribute

SHA = "a" * 40


@pytest.fixture
def ws(tmp_path, monkeypatch):
    monkeypatch.setenv("ILAB_WORKSPACE", str(tmp_path))
    return tmp_path


@pytest.fixture
def store(ws, monkeypatch):
    root = ws / "store"
    d = root / "canaries" / "cb" / "snap"
    d.mkdir(parents=True)
    (d / "canary.json").write_text(json.dumps({"id": "cb-snap", "pack": "honk", "target": "snap", "snapshot_sha": SHA}))
    (d / "fixes").mkdir()
    (d / "fixes" / "b1.patch").write_text("")
    (d / "bugs.json").write_text(json.dumps([{"id": "b1", "files": ["A.sol"], "fix": "fixes/b1.patch"}]))
    monkeypatch.setenv("ILAB_CANARY_STORE", str(root))
    return root


def _make_run(ws, label, run_id, *, poc_ok=True, failed=False):
    arts = ws / "artifacts" / label / run_id
    arts.mkdir(parents=True)
    (arts / "runspec.json").write_text(json.dumps({"run_id": run_id, "canary_id": "cb-snap"}))
    if failed:
        (arts / "error.json").write_text("{}")
        return
    attempt = ws / "illumina-cache" / "beam" / label / run_id / "poc" / "abc123" / "attempt-1"
    (attempt / "workspace").mkdir(parents=True)
    (attempt / "workspace" / "foundry.toml").write_text("")
    (attempt / "run").mkdir()
    (attempt / "run" / "run.json").write_text(json.dumps({"ok": poc_ok}))


def _script_replay(monkeypatch, fixed_result="fail"):
    calls = []

    def fake_run(workspace, **kwargs):
        calls.append(kwargs.get("patch"))
        return {"result": "win" if kwargs.get("patch") is None else fixed_result}

    monkeypatch.setattr(attribute.replay, "run", fake_run)
    return calls


def test_attribute_execution_writes_rows_and_run_json(ws, store, monkeypatch):
    _make_run(ws, "exp-x-20261109-1", "run-1")
    _script_replay(monkeypatch)
    rows = attribute.attribute_execution("exp-x-20261109-1")
    assert len(rows) == 1
    assert rows[0]["verdict"] == "confirmed:b1"
    assert rows[0]["run_id"] == "run-1" and rows[0]["label"] == "exp-x-20261109-1"
    assert workspace.attributions_path().is_file()
    written = json.loads((ws / "illumina-cache" / "beam" / "exp-x-20261109-1" / "run-1" / "attribution.json").read_text())
    assert written["records"][0]["verdict"] == "confirmed:b1"


def test_attribute_execution_skips_attributed_runs(ws, store, monkeypatch):
    _make_run(ws, "exp-x-20261109-1", "run-1")
    calls = _script_replay(monkeypatch)
    assert len(attribute.attribute_execution("exp-x-20261109-1")) == 1
    n = len(calls)
    assert attribute.attribute_execution("exp-x-20261109-1") == []
    assert len(calls) == n  # no replays on the second pass


def test_attribute_execution_force_reattributes_latest_wins(ws, store, monkeypatch):
    _make_run(ws, "exp-x-20261109-1", "run-1")
    _script_replay(monkeypatch)
    t1 = datetime(2026, 11, 9, 12, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 11, 9, 13, 0, tzinfo=timezone.utc)
    attribute.attribute_execution("exp-x-20261109-1", now=t1)
    attribute.attribute_execution("exp-x-20261109-1", force=True, now=t2)
    rows = attribute.read_attributions()
    assert len(rows) == 2  # history kept
    latest = attribute.latest_attributions()
    assert latest[("run-1", rows[1]["poc"])]["attributed_at"] == t2.isoformat()


def test_failed_run_is_never_attributed(ws, store, monkeypatch):
    _make_run(ws, "exp-x-20261109-1", "run-1", failed=True)
    calls = _script_replay(monkeypatch)
    assert attribute.attribute_execution("exp-x-20261109-1") == []
    assert calls == []


def test_unknown_canary_fails_loud(ws, store, monkeypatch):
    _make_run(ws, "exp-x-20261109-1", "run-1")
    runspec = ws / "artifacts" / "exp-x-20261109-1" / "run-1" / "runspec.json"
    runspec.write_text(json.dumps({"run_id": "run-1", "canary_id": "nope"}))
    _script_replay(monkeypatch)
    with pytest.raises(RegistryError, match="unknown canary"):
        attribute.attribute_execution("exp-x-20261109-1")
