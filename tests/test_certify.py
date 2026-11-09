"""Certify verb tests — the lab drives the store's harness (offline: a stub script)."""

import json

import pytest

from illumina_lab.canaries import certify
from illumina_lab.canaries.models import RegistryError

SHA = "a" * 40


@pytest.fixture
def store(tmp_path, monkeypatch):
    root = tmp_path / "store"
    d = root / "canaries" / "cb" / "snap"
    d.mkdir(parents=True)
    (d / "canary.json").write_text(json.dumps({"id": "cb-snap", "pack": "honk", "target": "snap", "snapshot_sha": SHA}))
    (d / "bugs.json").write_text(json.dumps([{"id": "b1", "files": ["A.sol"], "fix": "fixes/b1.patch", "reference_poc": "reference/b1"}]))
    monkeypatch.setenv("ILAB_CANARY_STORE", str(root))
    return root


def test_certify_runs_the_store_harness(store, capfd):
    script = store / "ci" / "certify.sh"
    script.parent.mkdir()
    script.write_text('#!/usr/bin/env bash\necho "harness called with: $1"\necho "LAB_CMD=$LAB_CMD"\nexit 0\n')
    rc = certify.main(["cb-snap"])
    out = capfd.readouterr().out  # fd-level: the harness is a subprocess, capsys misses it
    assert rc == 0
    assert "certifying cb-snap" in out and "b1" in out
    assert "harness called with:" in out and "canaries/cb/snap" in out
    assert "LAB_CMD" in out and "illumina_lab.cli" in out  # the harness calls back into this CLI


def test_certify_fails_loud_without_harness(store):
    with pytest.raises(RegistryError, match="no certification harness"):
        certify.main(["cb-snap"])


def test_certify_unknown_canary_fails_loud(store):
    with pytest.raises(RegistryError, match="unknown canary"):
        certify.main(["nope"])
