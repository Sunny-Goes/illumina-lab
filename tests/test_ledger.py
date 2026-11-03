"""Ledger tests — append, latest-event resolution, dedupe/resume. Offline, tmp workspace."""

import json

import pytest

from illumina_lab import workspace
from illumina_lab.experiment import RunSpec
from illumina_lab.orchestrator import ledger

SPEC = "0123456789ab"
RUN = RunSpec(run_id="exp-x-smoke-20261103-1-cb-w-s1", label="exp-x-smoke-20261103-1", canary_id="cb", pack="honk", target="t", win="w", seed=1)


@pytest.fixture(autouse=True)
def _ws(monkeypatch, tmp_path):
    monkeypatch.setenv(workspace.ENV_VAR, str(tmp_path))


def test_record_appends_flat_rows():
    ledger.record("submitted", RUN, SPEC)
    ledger.record("finished", RUN, SPEC, duration_s=12)
    rows = [json.loads(line) for line in workspace.ledger_path().read_text().splitlines()]
    assert [r["event"] for r in rows] == ["submitted", "finished"]
    assert rows[0]["cell"] == {"canary": "cb", "win": "w", "seed": 1}
    assert rows[1]["duration_s"] == 12


def test_unknown_event_rejected():
    with pytest.raises(ValueError, match="unknown ledger event"):
        ledger.record("vibing", RUN, SPEC)


def test_events_empty_without_ledger():
    assert ledger.events() == []


def test_latest_event_wins():
    ledger.record("submitted", RUN, SPEC)
    ledger.record("failed", RUN, SPEC)
    assert ledger.latest_by_run()[RUN.run_id]["event"] == "failed"


def test_pending_is_the_resume_set():
    done = RUN
    todo = RUN.model_copy(update={"run_id": "exp-x-smoke-20261103-1-cb-w-s2", "seed": 2})
    ledger.record("submitted", done, SPEC)
    ledger.record("finished", done, SPEC)
    ledger.record("submitted", todo, SPEC)
    ledger.record("failed", todo, SPEC)
    assert ledger.finished_cells(SPEC) == {("cb", "w", 1)}
    assert ledger.pending([done, todo], SPEC) == [todo]  # failed re-queues, finished dedupes


def test_pending_scoped_by_spec():
    ledger.record("finished", RUN, SPEC)
    assert ledger.pending([RUN], "ffffffffffff") == [RUN]  # a different spec dedupes nothing
