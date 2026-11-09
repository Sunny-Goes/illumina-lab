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
    (attempt / "run" / "run.json").write_text(json.dumps({"ok": poc_ok, "command": "forge test --match-contract PocTest -vvv"}))


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
    results = attribute.attribute_execution("exp-x-20261109-1")
    assert len(results) == 1 and results[0]["canary"] == "cb-snap"
    rows = results[0]["rows"]
    assert len(rows) == 1
    assert rows[0]["verdict"] == "confirmed:b1"
    assert rows[0]["run_id"] == "run-1" and rows[0]["label"] == "exp-x-20261109-1"
    assert workspace.attributions_path().is_file()
    written = json.loads((ws / "illumina-cache" / "beam" / "exp-x-20261109-1" / "run-1" / "attribution.json").read_text())
    assert written["records"][0]["verdict"] == "confirmed:b1"


def test_attribute_execution_skips_attributed_runs(ws, store, monkeypatch):
    _make_run(ws, "exp-x-20261109-1", "run-1")
    calls = _script_replay(monkeypatch)
    assert len(attribute.attribute_execution("exp-x-20261109-1")[0]["rows"]) == 1
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


def test_attributed_event_lands_in_the_ledger(ws, store, monkeypatch):
    _make_run(ws, "exp-x-20261109-1", "run-1")
    _script_replay(monkeypatch)
    attribute.attribute_execution("exp-x-20261109-1")
    events = [json.loads(line) for line in workspace.ledger_path().read_text().splitlines()]
    assert events[0]["event"] == "attributed"
    assert events[0]["run_id"] == "run-1" and events[0]["verdicts"] == ["confirmed:b1"]
    assert events[0]["cell"] == {"canary": "cb-snap", "win": "", "seed": 0}


def test_zero_poc_run_is_marked_and_skipped(ws, store, monkeypatch):
    # a finished run with no PoC evidence: no rows, but marked attributed — not retried forever
    arts = ws / "artifacts" / "exp-x-20261109-1" / "run-1"
    arts.mkdir(parents=True)
    (arts / "runspec.json").write_text(json.dumps({"run_id": "run-1", "canary_id": "cb-snap"}))
    (ws / "illumina-cache" / "beam" / "exp-x-20261109-1" / "run-1").mkdir(parents=True)
    calls = _script_replay(monkeypatch)
    assert attribute.attribute_execution("exp-x-20261109-1")[0]["rows"] == []
    assert attribute.attribute_execution("exp-x-20261109-1") == []
    assert calls == []
    events = [json.loads(line) for line in workspace.ledger_path().read_text().splitlines()]
    assert [e["event"] for e in events] == ["attributed"] and events[0]["verdicts"] == []


def test_unknown_canary_fails_loud(ws, store, monkeypatch):
    _make_run(ws, "exp-x-20261109-1", "run-1")
    runspec = ws / "artifacts" / "exp-x-20261109-1" / "run-1" / "runspec.json"
    runspec.write_text(json.dumps({"run_id": "run-1", "canary_id": "nope"}))
    _script_replay(monkeypatch)
    with pytest.raises(RegistryError, match="unknown canary"):
        attribute.attribute_execution("exp-x-20261109-1")


def test_cli_attribute_label_prints_verdicts(ws, store, monkeypatch, capsys):
    _make_run(ws, "exp-x-20261109-1", "run-1")
    _script_replay(monkeypatch)
    rc = attribute.main(["--label", "exp-x-20261109-1"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "run-1 [cb-snap]:" in out
    assert "abc123/attempt-1: confirmed:b1" in out
    assert "1 runs judged, 1 PoCs, confirmed: 1" in out


def test_cli_attribute_single_run_prints_readable_table(ws, store, monkeypatch, capsys):
    _make_run(ws, "exp-x-20261109-1", "run-1")
    _script_replay(monkeypatch)
    run_dir = ws / "illumina-cache" / "beam" / "exp-x-20261109-1" / "run-1"
    rc = attribute.main([str(run_dir), "--canary-dir", str(store / "canaries" / "cb" / "snap"), "--no-write"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "command:    forge test" in out
    assert "verdict:    confirmed:b1" in out
    assert "fixed[b1]: fail" in out


def test_cli_attribute_dry_run_replays_nothing(ws, store, monkeypatch, capsys):
    _make_run(ws, "exp-x-20261109-1", "run-1")
    calls = _script_replay(monkeypatch)
    rc = attribute.main(["--label", "exp-x-20261109-1", "--dry-run"])
    out = capsys.readouterr().out
    assert rc == 0 and calls == []
    assert "run-1 [cb-snap]: to judge against 1 fix-carrying bug" in out
