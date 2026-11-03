"""Naming tests — spec-hash stability and semantics, label and run-id minting. Offline."""

from datetime import datetime, timezone

import pytest

from illumina_lab import workspace
from illumina_lab.experiment import ExperimentSpec
from illumina_lab.illumina_interface import pin_sha
from illumina_lab.naming import execution_label, run_id, spec_hash

SPEC = ExperimentSpec(name="smoke", canaries=["honk-all-canaries"], wins=["griefing"])
AZ = "a" * 40
TS = "b" * 40


def test_spec_hash_stable_across_field_noise():
    # same content, differently-ordered source dict → same hash (canonical dump)
    reordered = ExperimentSpec(**{"wins": ["griefing"], "seeds": 1, "models": {"default": "", "roles": {}},
                                  "canaries": ["honk-all-canaries"], "name": "smoke"})
    assert spec_hash(SPEC, AZ, TS) == spec_hash(reordered, AZ, TS)
    assert len(spec_hash(SPEC, AZ, TS)) == 12


def test_spec_hash_moves_with_spec_and_pins():
    base = spec_hash(SPEC, AZ, TS)
    assert spec_hash(SPEC.model_copy(update={"seeds": 2}), AZ, TS) != base  # the spec changed
    assert spec_hash(SPEC, "c" * 40, TS) != base  # the engine moved
    assert spec_hash(SPEC, AZ, "d" * 40) != base  # the ground truth moved


def test_label_shape_and_increment():
    now = datetime(2026, 11, 3, 12, 0, tzinfo=timezone.utc)
    label = execution_label(SPEC, AZ, TS, now=now)
    stem = f"exp-{spec_hash(SPEC, AZ, TS)[:8]}-smoke-20261103"
    assert label == f"{stem}-1"
    assert execution_label(SPEC, AZ, TS, now=now, existing=[label]) == f"{stem}-2"


def test_run_id_shape():
    rid = run_id("exp-12345678-smoke-20261103-1", "honk-all-canaries", "griefing", 3)
    assert rid == "exp-12345678-smoke-20261103-1-honk-all-canaries-griefing-s3"


def test_pin_sha_reads_a_repo_head(tmp_path):
    from pathlib import Path

    lab_repo = Path(__file__).resolve().parents[1]
    assert len(pin_sha(lab_repo)) == 40
    with pytest.raises(RuntimeError, match="could not read the pin"):
        pin_sha(tmp_path)  # never a git repo


def test_execution_labels_lists_artifact_dirs(monkeypatch, tmp_path):
    monkeypatch.setenv(workspace.ENV_VAR, str(tmp_path))
    assert workspace.execution_labels() == []
    (tmp_path / "artifacts" / "exp-1").mkdir(parents=True)
    (tmp_path / "artifacts" / "exp-2").mkdir()
    assert workspace.execution_labels() == ["exp-1", "exp-2"]
