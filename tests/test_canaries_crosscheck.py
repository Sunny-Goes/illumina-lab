"""Store cross-check tests — synthetic engine stores, plus the real submodules when present."""

import json
from pathlib import Path

import pytest

from illumina_lab.canaries.crosscheck import validate_binding
from illumina_lab.canaries.loader import load_canaries
from illumina_lab.canaries.models import BugEntry, Canary, CanaryPointer, RegistryError

SHA = "c" * 40


def _store(root: Path, *, commit: str = SHA, in_scope: list[str] | None = None, wins: list[str] | None = None) -> Path:
    pack = root / "packs" / "honk"
    (pack / "targets").mkdir(parents=True)
    (pack / "pack.json").write_text(json.dumps({"name": "honk"}))
    (pack / "targets" / "t.json").write_text(json.dumps({"commit": commit, "in_scope": in_scope or ["A.sol", "B.sol"]}))
    (pack / "win_conditions.json").write_text(json.dumps([{"id": w} for w in (wins or ["griefing"])]))
    return root


def _canary(*, sha: str = SHA, files: list[str] | None = None, win: str = "griefing") -> Canary:
    pointer = CanaryPointer(id="cb-snap", pack="honk", target="t", snapshot_sha=sha)
    return Canary(pointer=pointer, bugs=[BugEntry(id="b1", files=files or ["A.sol"], win=win)], root=Path("."))


def test_binding_ok(tmp_path):
    validate_binding(_canary(), _store(tmp_path))


def test_commit_drift_fails(tmp_path):
    with pytest.raises(RegistryError, match="commit drift"):
        validate_binding(_canary(), _store(tmp_path, commit="d" * 40))


def test_bug_file_out_of_scope_fails(tmp_path):
    with pytest.raises(RegistryError, match="not in t's in_scope"):
        validate_binding(_canary(files=["Elsewhere.sol"]), _store(tmp_path))


def test_unknown_win_fails(tmp_path):
    with pytest.raises(RegistryError, match="not a row of honk's win_conditions"):
        validate_binding(_canary(win="theft-of-funds"), _store(tmp_path))


def test_missing_pack_fails(tmp_path):
    (tmp_path / "packs").mkdir()
    with pytest.raises(RegistryError, match="pack 'honk' not found"):
        validate_binding(_canary(), tmp_path)


def test_missing_target_fails(tmp_path):
    store = _store(tmp_path)
    (store / "packs" / "honk" / "targets" / "t.json").unlink()
    with pytest.raises(RegistryError, match="target manifest 't' not found"):
        validate_binding(_canary(), store)


def test_real_registry_binds_to_real_store():
    lab_root = Path(__file__).resolve().parents[1]
    if not (lab_root / "vendor" / "illumina-training-set" / "canaries").is_dir():
        pytest.skip("training-set submodule not initialized")
    if not (lab_root / "vendor" / "azimo" / "store").is_dir():
        pytest.skip("azimo submodule not initialized")
    for canary in load_canaries():
        validate_binding(canary)  # raises on any drift between ground truth and the engine's pins
