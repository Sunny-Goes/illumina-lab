"""Matrix tests — expansion and spec validation over synthetic stores, plus the real submodules."""

import json
from pathlib import Path

import pytest

from illumina_lab.experiment import ExperimentError, ExperimentSpec
from illumina_lab.orchestrator.matrix import expand, validate_experiment

SHA = "e" * 40


def _canary_store(root: Path, codebase: str = "cb", snapshot: str = "snap") -> Path:
    d = root / "canaries" / codebase / snapshot
    d.mkdir(parents=True)
    (d / "canary.json").write_text(json.dumps({"id": f"{codebase}-{snapshot}", "pack": "honk", "target": "t", "snapshot_sha": SHA}))
    (d / "bugs.json").write_text(json.dumps([{"id": "b1", "files": ["A.sol"], "win": "griefing"}]))
    return root


def _engine_store(root: Path, *, commit: str = SHA, wins: list[str] | None = None) -> Path:
    pack = root / "packs" / "honk"
    (pack / "targets").mkdir(parents=True)
    (pack / "pack.json").write_text(json.dumps({"name": "honk"}))
    (pack / "targets" / "t.json").write_text(json.dumps({"commit": commit, "in_scope": ["A.sol"]}))
    (pack / "win_conditions.json").write_text(json.dumps([{"id": w} for w in (wins or ["griefing", "theft-of-gas"])]))
    return root


def test_expand_counts_and_order(tmp_path):
    _canary_store(tmp_path / "reg")
    _canary_store(tmp_path / "reg", "db", "x")  # a second canary: db-x
    spec = ExperimentSpec(name="e", canaries=["db-x", "cb-snap"], wins=["theft-of-gas", "griefing"], seeds=2)
    cells = expand(spec, "exp-deadbeef-e-20261103-1", store_root=tmp_path / "reg")
    assert len(cells) == 2 * 2 * 2
    keys = [(c.canary_id, c.win, c.seed) for c in cells]
    assert keys == sorted(keys)
    assert cells[0].run_id == "exp-deadbeef-e-20261103-1-cb-snap-griefing-s1"
    assert {c.pack for c in cells} == {"honk"}
    assert all(c.target == "t" for c in cells)
    assert len({c.run_id for c in cells}) == 8


def test_validate_ok(tmp_path):
    spec = ExperimentSpec(name="e", canaries=["cb-snap"], wins=["griefing"])
    validate_experiment(spec, store_root=_canary_store(tmp_path / "reg"), engine_store=_engine_store(tmp_path / "eng"))


def test_validate_unknown_canary(tmp_path):
    spec = ExperimentSpec(name="e", canaries=["nope-nope"], wins=["griefing"])
    with pytest.raises(ExperimentError, match="unknown canary"):
        validate_experiment(spec, store_root=_canary_store(tmp_path / "reg"), engine_store=_engine_store(tmp_path / "eng"))


def test_validate_unknown_win(tmp_path):
    spec = ExperimentSpec(name="e", canaries=["cb-snap"], wins=["governance-voting-manipulation"])
    with pytest.raises(ExperimentError, match="not a row of honk's win table"):
        validate_experiment(spec, store_root=_canary_store(tmp_path / "reg"), engine_store=_engine_store(tmp_path / "eng"))


def test_validate_commit_drift(tmp_path):
    spec = ExperimentSpec(name="e", canaries=["cb-snap"], wins=["griefing"])
    with pytest.raises(ExperimentError, match="commit drift"):
        validate_experiment(spec, store_root=_canary_store(tmp_path / "reg"), engine_store=_engine_store(tmp_path / "eng", commit="f" * 40))


def test_real_stores_validate_and_expand():
    lab = Path(__file__).resolve().parents[1]
    if not (lab / "vendor" / "illumina-training-set" / "canaries").is_dir() or not (lab / "vendor" / "azimo" / "store").is_dir():
        pytest.skip("submodules not initialized")
    spec = ExperimentSpec(name="honk-smoke", canaries=["honk-precompile-success-unchecked"], wins=["direct-unconstrained-exploitability"])
    validate_experiment(spec)
    cells = expand(spec, "exp-00000000-honk-smoke-20261103-1")
    assert len(cells) == 1
    assert cells[0].pack == "honk" and cells[0].target == "precompile-success-unchecked"
