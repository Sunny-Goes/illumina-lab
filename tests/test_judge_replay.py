"""replay.run's result classification — offline: every subprocess scripted, no forge."""

import subprocess

import pytest

from illumina_lab.judge import replay


@pytest.fixture
def workspace(tmp_path):
    ws = tmp_path / "workspace"
    ws.mkdir()
    (ws / "foundry.toml").write_text("")
    return ws


def _script(monkeypatch, *, test_rc=0, build_rc=0, apply_rc=0):
    """Script the three subprocesses replay drives: git apply, the test command, forge build."""
    calls = []
    monkeypatch.setattr(replay, "forge_binary", lambda: "/fake/forge")

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        if isinstance(cmd, list) and "apply" in cmd:
            rc = apply_rc
        elif isinstance(cmd, list) and "build" in cmd:
            rc = build_rc
        else:
            rc = test_rc
        return subprocess.CompletedProcess(cmd, rc, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    return calls


def test_win(workspace, monkeypatch):
    _script(monkeypatch, test_rc=0)
    out = replay.run(workspace)
    assert out["result"] == "win" and out["returncode"] == 0


def test_fail_is_a_clean_build_with_failing_tests(workspace, monkeypatch):
    _script(monkeypatch, test_rc=1, build_rc=0)
    assert replay.run(workspace)["result"] == "fail"


def test_build_error_when_the_workspace_does_not_compile(workspace, monkeypatch):
    _script(monkeypatch, test_rc=1, build_rc=1)
    assert replay.run(workspace)["result"] == "build-error"


def test_patch_failure_is_error_and_never_runs_the_tests(workspace, monkeypatch, tmp_path):
    calls = _script(monkeypatch, apply_rc=1)
    patch = tmp_path / "fix.patch"
    patch.write_text("")
    out = replay.run(workspace, patch=patch)
    assert out["result"] == "error" and "patch failed" in out["detail"]
    assert not any(isinstance(cmd, str) for cmd in calls)  # the test command never ran


def test_missing_foundry_toml_is_error(tmp_path):
    out = replay.run(tmp_path)
    assert out["result"] == "error" and "no foundry.toml" in out["detail"]
