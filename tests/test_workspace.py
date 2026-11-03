"""Workspace seam tests — path resolution and layout creation, all offline."""

from pathlib import Path

from illumina_lab import workspace


def test_root_honors_env_override(monkeypatch, tmp_path):
    monkeypatch.setenv(workspace.ENV_VAR, str(tmp_path / "ws"))
    assert workspace.workspace_root() == tmp_path / "ws"


def test_root_defaults_to_repo_runs(monkeypatch):
    monkeypatch.delenv(workspace.ENV_VAR, raising=False)
    root = workspace.workspace_root()
    assert root.name == "runs"
    assert root.parent == Path(__file__).resolve().parents[1]


def test_records_live_under_root(monkeypatch, tmp_path):
    monkeypatch.setenv(workspace.ENV_VAR, str(tmp_path))
    label = "exp-0123456789ab-20261102-1"
    assert workspace.ledger_path() == tmp_path / "ledger.jsonl"
    assert workspace.facts_path() == tmp_path / "facts.jsonl"
    assert workspace.run_dir(label, "run-abc") == tmp_path / "artifacts" / label / "run-abc"
    assert workspace.illumina_cache() == tmp_path / "illumina-cache"


def test_ensure_creates_layout(monkeypatch, tmp_path):
    monkeypatch.setenv(workspace.ENV_VAR, str(tmp_path / "fresh"))
    root = workspace.ensure()
    assert (root / "artifacts").is_dir()
