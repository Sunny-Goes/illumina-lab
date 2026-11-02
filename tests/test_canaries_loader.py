"""Canary-store loader tests — synthetic registries in tmp_path, plus the real submodule when present."""

import json
from pathlib import Path

import pytest

from illumina_lab.canaries import loader
from illumina_lab.canaries.models import RegistryError

SHA = "b" * 40


def _write_canary(root: Path, codebase: str, snapshot: str, *, canary_id: str | None = None, bugs: list[dict] | None = None) -> None:
    d = root / "canaries" / codebase / snapshot
    d.mkdir(parents=True)
    (d / "canary.json").write_text(json.dumps({
        "id": canary_id or f"{codebase}-{snapshot}",
        "pack": "honk",
        "target": snapshot,
        "snapshot_sha": SHA,
    }))
    (d / "bugs.json").write_text(json.dumps(bugs if bugs is not None else [{"id": "b1", "files": ["A.sol"]}]))


def test_load_canaries_sorted(tmp_path):
    _write_canary(tmp_path, "zeta", "s1")
    _write_canary(tmp_path, "alpha", "s2")
    entries = loader.load_canaries(tmp_path)
    assert [e.pointer.id for e in entries] == ["alpha-s2", "zeta-s1"]
    assert entries[0].bugs[0].id == "b1"
    assert entries[0].root.name == "s2"


def test_load_canary_unknown_lists_known(tmp_path):
    _write_canary(tmp_path, "alpha", "s2")
    with pytest.raises(RegistryError, match=r"unknown canary.*alpha-s2"):
        loader.load_canary("nope", tmp_path)


def test_id_must_match_path(tmp_path):
    _write_canary(tmp_path, "alpha", "s2", canary_id="something-else")
    with pytest.raises(RegistryError, match="disagrees with its path"):
        loader.load_canaries(tmp_path)


def test_duplicate_bug_ids_fail(tmp_path):
    _write_canary(tmp_path, "alpha", "s2", bugs=[{"id": "b1", "files": ["A.sol"]}, {"id": "b1", "files": ["B.sol"]}])
    with pytest.raises(RegistryError, match="duplicate bug ids: b1"):
        loader.load_canaries(tmp_path)


def test_missing_bugs_file_fails(tmp_path):
    d = tmp_path / "canaries" / "alpha" / "s2"
    d.mkdir(parents=True)
    (d / "canary.json").write_text(json.dumps({"id": "alpha-s2", "pack": "honk", "target": "s2", "snapshot_sha": SHA}))
    with pytest.raises(RegistryError, match="missing bugs.json"):
        loader.load_canaries(tmp_path)


def test_malformed_json_named_as_registry_error(tmp_path):
    d = tmp_path / "canaries" / "alpha" / "s2"
    d.mkdir(parents=True)
    (d / "canary.json").write_text("{ not json")
    with pytest.raises(RegistryError, match="malformed JSON"):
        loader.load_canaries(tmp_path)


def test_store_root_env_override(monkeypatch, tmp_path):
    _write_canary(tmp_path, "alpha", "s2")
    monkeypatch.setenv(loader.ENV_VAR, str(tmp_path))
    assert loader.store_root() == tmp_path
    assert [e.pointer.id for e in loader.load_canaries()] == ["alpha-s2"]


def test_store_root_missing_hints_submodule(monkeypatch, tmp_path):
    monkeypatch.setenv(loader.ENV_VAR, str(tmp_path / "nope"))
    with pytest.raises(RegistryError, match="git submodule update --init"):
        loader.store_root()


def test_real_training_set_loads():
    root = Path(loader.__file__).resolve().parents[3] / "vendor" / "illumina-training-set"
    if not (root / "canaries").is_dir():
        pytest.skip("training-set submodule not initialized")
    entries = loader.load_canaries()
    ids = [e.pointer.id for e in entries]
    assert ids == [
        "honk-all-canaries",
        "honk-canonical-no-field-check",
        "honk-msm-loop-past-bounds",
        "honk-precompile-success-unchecked",
    ]
    assert len(entries[0].bugs) == 3  # all-canaries carries all three seeded bugs
