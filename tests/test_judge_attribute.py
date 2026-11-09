"""Run-level attribution: discovery and the verdict table — offline, replay outcomes scripted."""

import json

from illumina_lab.judge import attribute


def _attempt(root, name="attempt-1", ok=True):
    attempt = root / name
    (attempt / "workspace").mkdir(parents=True)
    (attempt / "workspace" / "foundry.toml").write_text("")
    (attempt / "run").mkdir()
    (attempt / "run" / "run.json").write_text(json.dumps({"ok": ok}))
    return attempt


def _canary(root):
    (root / "fixes").mkdir(parents=True)
    (root / "bugs.json").write_text(json.dumps([
        {"id": "bug-a", "fix": "fixes/bug-a.patch"},
        {"id": "bug-b", "fix": "fixes/bug-b.patch"},
        {"id": "bug-c"},
    ]))
    return root


def test_discover_single_attempt(tmp_path):
    attempt = _attempt(tmp_path)
    pocs = attribute.discover_pocs(attempt)
    assert len(pocs) == 1 and pocs[0]["recorded_ok"] is True


def test_discover_beam_dir(tmp_path):
    _attempt(tmp_path / "poc" / "abc123")
    _attempt(tmp_path / "poc" / "def456", ok=False)
    pocs = attribute.discover_pocs(tmp_path)
    assert len(pocs) == 2
    assert [p["recorded_ok"] for p in pocs] == [True, False]


def _script_replay(monkeypatch, vulnerable="win", fixed=None):
    calls = []

    def fake_run(workspace, **kwargs):
        calls.append(kwargs.get("patch"))
        if kwargs.get("patch") is None:
            return {"result": vulnerable}
        return {"result": (fixed or {}).get(kwargs["patch"].name, "win")}

    monkeypatch.setattr(attribute.replay, "run", fake_run)
    return calls


def test_recorded_failure_is_never_replayed(tmp_path, monkeypatch):
    canary = _canary(tmp_path)
    attempt = _attempt(tmp_path, ok=False)
    calls = _script_replay(monkeypatch)
    records = attribute.attribute_run(attempt, canary)
    assert records[0]["verdict"] == "not-a-valid-exploit"
    assert calls == []


def test_confirmed_single_bug(tmp_path, monkeypatch):
    canary = _canary(tmp_path)
    attempt = _attempt(tmp_path)
    _script_replay(monkeypatch, fixed={"bug-a.patch": "fail", "bug-b.patch": "win"})
    records = attribute.attribute_run(attempt, canary)
    assert records[0]["verdict"] == "confirmed:bug-a"
    assert records[0]["fixed"] == {"bug-a": "fail", "bug-b": "win"}


def test_confirmed_multiple_and_candidate(tmp_path, monkeypatch):
    canary = _canary(tmp_path)
    attempt = _attempt(tmp_path)
    _script_replay(monkeypatch, fixed={"bug-a.patch": "fail", "bug-b.patch": "fail"})
    assert attribute.attribute_run(attempt, canary)[0]["verdict"] == "confirmed-multiple"
    _script_replay(monkeypatch, fixed={"bug-a.patch": "win", "bug-b.patch": "win"})
    assert attribute.attribute_run(attempt, canary)[0]["verdict"] == "candidate-new-bug"


def test_build_error_never_counts_as_died(tmp_path, monkeypatch):
    canary = _canary(tmp_path)
    attempt = _attempt(tmp_path)
    # a patch that breaks the PoC's build kills nothing — attribution is impossible
    _script_replay(monkeypatch, fixed={"bug-a.patch": "build-error", "bug-b.patch": "win"})
    assert attribute.attribute_run(attempt, canary)[0]["verdict"] == "patch-incompatible"
    # but a genuine die on one fix stands even when another patch is incompatible
    _script_replay(monkeypatch, fixed={"bug-a.patch": "fail", "bug-b.patch": "build-error"})
    assert attribute.attribute_run(attempt, canary)[0]["verdict"] == "confirmed:bug-a"


def test_recorded_ok_but_replay_loses_is_error(tmp_path, monkeypatch):
    canary = _canary(tmp_path)
    attempt = _attempt(tmp_path)
    _script_replay(monkeypatch, vulnerable="fail")
    record = attribute.attribute_run(attempt, canary)[0]
    assert record["verdict"] == "error"
    assert "does not reproduce" in record["detail"]
