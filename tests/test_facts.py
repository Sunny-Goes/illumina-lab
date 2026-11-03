"""Harvest tests — fabricated run artifacts become facts rows. Offline."""

import json
from pathlib import Path

import pytest

from illumina_lab import workspace
from illumina_lab.experiment import RunSpec
from illumina_lab.facts import harvest_run
from illumina_lab.orchestrator import ledger

LABEL = "exp-x-smoke-20261103-1"
RUN_ID = f"{LABEL}-cb-snap-griefing-s1"

STATE = {
    "run_id": RUN_ID,
    "findings": [
        {"id": "a@utils.sol", "location": "utils.sol", "status": "confirmed"},
        {"id": "b@Fr.sol", "location": "Fr.sol", "status": "dismissed"},
    ],
    "poc_inputs": [{"finding_id": "a@utils.sol"}],
    "poc_runs": [{"request_id": "r1", "outcome": "confirmed", "attempts": 2}],
    "coverage": [
        {"kind": "llm_scan", "files_read": ["utils.sol", "Fr.sol"], "tool_calls": {"read_file": 9}, "llm_calls": 14},
        {"kind": "probe", "invariant": "sibling-parity", "hypotheses": 1},
    ],
    "target": {"name": "honk", "commit": "c" * 40},
}


@pytest.fixture(autouse=True)
def _ws(monkeypatch, tmp_path):
    monkeypatch.setenv(workspace.ENV_VAR, str(tmp_path))
    return tmp_path


def _fabricate(root: Path, *, state: dict | None = None, failed: bool = False) -> None:
    run_dir = workspace.run_dir(LABEL, RUN_ID)
    run_dir.mkdir(parents=True)
    spec = RunSpec(run_id=RUN_ID, label=LABEL, canary_id="cb-snap", pack="honk", target="t", win="griefing", seed=1)
    (run_dir / "runspec.json").write_text(spec.model_dump_json())
    (run_dir / "provenance.json").write_text(json.dumps({"azimo_sha": "a" * 40, "training_set_sha": "b" * 40}))
    if failed:
        (run_dir / "error.json").write_text(json.dumps({"traceback": "RuntimeError: boom"}))
    if state is not None:
        (run_dir / "state.json").write_text(json.dumps(state))
    azimo_dir = workspace.illumina_cache() / "beam" / LABEL / RUN_ID
    azimo_dir.mkdir(parents=True)
    (azimo_dir / "run.json").write_text(json.dumps({"models": {"detect": "anthropic:claude-sonnet-4-6"}}))
    ledger.record("finished", spec, "0123456789ab", returncode=0 if not failed else 1, duration_s=612.3)


def test_harvest_assembles_the_row(tmp_path):
    _fabricate(tmp_path, state=STATE)
    row = harvest_run(LABEL, RUN_ID)
    assert row.run_id == RUN_ID and row.ok
    assert row.spec == "0123456789ab"
    assert (row.canary, row.win, row.seed) == ("cb-snap", "griefing", 1)
    assert row.azimo_sha == "a" * 40 and row.training_set_sha == "b" * 40
    assert row.target_commit == "c" * 40
    assert row.findings_by_status == {"confirmed": 1, "dismissed": 1}
    assert row.poc_inputs == 1 and row.poc_runs[0]["outcome"] == "confirmed"
    assert row.coverage.files_read == ["Fr.sol", "utils.sol"]
    assert row.coverage.llm_calls == 14 and row.coverage.tool_calls == {"read_file": 9}
    assert row.coverage.probes == 1 and row.coverage.hypotheses == 1
    assert row.coverage.errored == ""
    assert row.models == {"detect": "anthropic:claude-sonnet-4-6"}
    assert row.duration_s == 612.3


def test_harvest_a_failed_run(tmp_path):
    _fabricate(tmp_path, failed=True)  # no state.json at all
    row = harvest_run(LABEL, RUN_ID)
    assert not row.ok
    assert row.findings == [] and row.findings_by_status == {}
    assert row.coverage.llm_calls == 0


def test_harvest_tolerates_missing_azimo_run_json(tmp_path):
    _fabricate(tmp_path, state=STATE)
    (workspace.illumina_cache() / "beam" / LABEL / RUN_ID / "run.json").unlink()
    row = harvest_run(LABEL, RUN_ID)
    assert row.ok and row.models == {}
