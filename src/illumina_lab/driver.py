"""The beam driver — one RunSpec in, one beam run, the state on disk.

Runs as ``<azimo venv python> -m illumina_lab.driver <runspec.json>`` — the
LocalRunner spawns exactly that: azimo's interpreter, the lab's code via
PYTHONPATH (D9). The driver stamps the run's env *before* importing illumina
(the engine reads env at import time), drives azimo's own entry point —
``illumina.cli.run_graph`` with our run_id (azimo PR #174) — and dumps the
final state to ``artifacts/<label>/<run_id>/state.json``. A failure writes
``error.json`` (traceback included) and exits 1; the ledger's failed/finished
comes from the exit code. API keys arrive via the inherited environment — the
driver never touches a key file.
"""

from __future__ import annotations

import json
import os
import sys
import traceback
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict


class RunProvenance(BaseModel):
    """What the driver records at spawn — the pins that produced this run (D10)."""

    model_config = ConfigDict(frozen=True)

    run_id: str
    label: str
    azimo_sha: str
    training_set_sha: str
    started_at: str


def _provenance(spec: Any) -> RunProvenance:
    """Stamp the run's provenance: both pins plus when it started."""
    from illumina_lab import illumina_interface
    from illumina_lab.canaries.loader import store_root

    return RunProvenance(
        run_id=spec.run_id,
        label=spec.label,
        azimo_sha=illumina_interface.pin_sha(illumina_interface.root()),
        training_set_sha=illumina_interface.pin_sha(store_root()),
        started_at=datetime.now(timezone.utc).isoformat(),
    )


def stamp_env(spec: Any) -> dict[str, str]:
    """Return the env mapping for one run — applied before illumina is imported.

    The store and the cache point into the workspace/engine checkout the lab
    controls; the label nests azimo's evidence under ``beam/<label>/``; the
    pack's target and the per-role models are the RunSpec's binding (D12).
    """
    from illumina_lab import illumina_interface, workspace

    env = {
        "ILLUMINA_STORE": str(illumina_interface.store()),
        "ILLUMINA_CACHE": str(workspace.illumina_cache()),
        "ILLUMINA_RUN_LABEL": spec.label,
        f"ILLUMINA_{spec.pack.upper()}_TARGET": spec.target,
        "LANGSMITH_PROJECT": spec.label,
    }
    if spec.models.default:
        env["ILLUMINA_MODEL"] = spec.models.default
    for role, model in spec.models.roles.items():
        env[f"ILLUMINA_MODEL_{role.upper()}"] = model
    return env


def _default(o: Any) -> Any:
    """Serialize the final state's leaves: pydantic models, dataclasses, Paths, sets; else str."""
    from pydantic import BaseModel

    if isinstance(o, BaseModel):
        return o.model_dump(mode="json")
    if is_dataclass(o) and not isinstance(o, type):
        return asdict(o)
    if isinstance(o, Path):
        return str(o)
    if isinstance(o, (set, frozenset)):
        return sorted(str(x) for x in o)
    return str(o)


def main(argv: list[str]) -> int:
    """Run one RunSpec's beam; 0 with state.json written, 1 with error.json."""
    from illumina_lab import workspace
    from illumina_lab.experiment import RunSpec

    spec_path = Path(argv[0])
    spec = RunSpec(**json.loads(spec_path.read_text(encoding="utf-8")))

    os.environ.update(stamp_env(spec))  # before any illumina import — the engine reads env at import time

    run = workspace.run_dir(spec.label, spec.run_id)
    run.mkdir(parents=True, exist_ok=True)
    (run / "runspec.json").write_text(spec_path.read_text(encoding="utf-8"))  # the exact bytes received
    (run / "provenance.json").write_text(_provenance(spec).model_dump_json(indent=1) + "\n", encoding="utf-8")
    print(f"driver: {spec.run_id} — beam {spec.pack}:{spec.win} target {spec.target}", flush=True)
    try:
        from illumina.cli import run_graph

        _, state = run_graph(spec.pack, thread_id=spec.run_id, win=spec.win, run_id=spec.run_id)
        (run / "state.json").write_text(json.dumps(state, default=_default, indent=1) + "\n", encoding="utf-8")
    except Exception:
        (run / "error.json").write_text(json.dumps({"traceback": traceback.format_exc()}, indent=1) + "\n", encoding="utf-8")
        print(f"driver: {spec.run_id} failed — see error.json", flush=True)
        return 1
    print(f"driver: {spec.run_id} finished — {len(state.get('findings', []))} findings", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
