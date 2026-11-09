"""The run ledger — append-only run events on the workspace seam (D15).

One JSONL row per event, keyed by ``run_id``; a run's state is its latest
event. The ledger is the resume oracle: a rerun of the same spec skips cells
whose latest event is ``finished`` (dedupe), so a crashed execution completes
rather than redoes — deliberate repeats come from ``seeds``, never from
rerunning (D5). Rows are flat and join-keyed so a DB backend maps 1:1 later
(D15): ``run_id`` joins runs, ``spec`` joins experiments, ``cell`` is the
dedupe identity — run ids embed the execution label, so cross-execution dedupe
keys on (spec, canary, win, seed), not run_id.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from illumina_lab import workspace
from illumina_lab.experiment import RunSpec

#: The ledger's event vocabulary.
EVENTS = ("submitted", "running", "finished", "failed", "attributed")


def record(event: str, run: RunSpec, spec: str, **extra: Any) -> None:
    """Append one event row for a run. ``spec`` is the experiment's 12-char hash (D10)."""
    record_event(
        event,
        run_id=run.run_id,
        label=run.label,
        spec=spec,
        cell={"canary": run.canary_id, "win": run.win, "seed": run.seed},
        **extra,
    )


def record_event(event: str, *, run_id: str, label: str, spec: str, cell: dict, **extra: Any) -> None:
    """Append one event row by fields — for stages (like the judge) that don't hold a RunSpec."""
    if event not in EVENTS:
        raise ValueError(f"unknown ledger event {event!r}; known: {', '.join(EVENTS)}")
    row = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "event": event,
        "run_id": run_id,
        "label": label,
        "spec": spec,
        "cell": cell,
        **extra,
    }
    path = workspace.ledger_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")


def events() -> list[dict]:
    """Read every ledger row in append order; empty when no ledger exists yet."""
    path = workspace.ledger_path()
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def latest_by_run() -> dict[str, dict]:
    """Return each run's latest event row, keyed by run_id."""
    latest: dict[str, dict] = {}
    for row in events():
        latest[row["run_id"]] = row
    return latest


def finished_cells(spec: str) -> set[tuple[str, str, int]]:
    """Return the spec's cells whose latest event is ``finished`` — the dedupe set."""
    out = set()
    for row in latest_by_run().values():
        if row["spec"] == spec and row["event"] == "finished":
            cell = row["cell"]
            out.add((cell["canary"], cell["win"], cell["seed"]))
    return out


def pending(cells: list[RunSpec], spec: str) -> list[RunSpec]:
    """Return the cells without a finished event under this spec — the resume set."""
    done = finished_cells(spec)
    return [c for c in cells if (c.canary_id, c.win, c.seed) not in done]
