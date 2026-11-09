"""The Runner protocol and the local pool — one subprocess per run (D9/D12).

A Runner takes a RunSpec and returns a handle; ``wait`` resolves it to a
RunResult. LocalRunner spawns the driver under azimo's interpreter
(``illumina_interface.python()``) with the lab's ``src`` on PYTHONPATH — the
D9 bridge — tees stdout/stderr to ``driver.log``, and records the ledger
events (submitted → running → finished/failed). ``max_parallel`` caps
concurrency (default 1: serial, rate-limit-friendly); reaping is FIFO, so a
slow head blocks the cap — v0 accepts this; fair scheduling is the
RemoteRunner's problem (D12).
"""

from __future__ import annotations

import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict

from illumina_lab import illumina_interface, workspace
from illumina_lab.experiment import RunSpec
from illumina_lab.orchestrator import ledger

#: Per-run wall-clock budget, seconds. ``ILAB_RUN_TIMEOUT_S`` overrides; 0 disables.
DEFAULT_TIMEOUT_S = 7200
TIMEOUT_ENV_VAR = "ILAB_RUN_TIMEOUT_S"


def timeout_from_env() -> float | None:
    """Parse ``ILAB_RUN_TIMEOUT_S``: unset/invalid → the default; 0 (or negative) → no timeout."""
    raw = os.environ.get(TIMEOUT_ENV_VAR, "").strip()
    if not raw:
        return DEFAULT_TIMEOUT_S
    try:
        value = int(raw)
    except ValueError:
        return DEFAULT_TIMEOUT_S
    return value if value > 0 else None


class RunResult(BaseModel):
    """One finished run, runner-side: exit status, duration, and where its artifacts live."""

    model_config = ConfigDict(frozen=True)

    run_id: str
    ok: bool
    returncode: int
    duration_s: float
    dir: str


@dataclass
class RunHandle:
    """One in-flight run: the spec, its experiment hash, the process, its log handle, its start time."""

    run: RunSpec
    spec: str
    proc: subprocess.Popen[Any]
    log: Any
    started: float


class Runner(Protocol):
    """One executor backend: local subprocesses today, a provider's jobs tomorrow (D12)."""

    def submit(self, run: RunSpec, spec: str) -> RunHandle:
        """Launch one run (non-blocking); the handle resolves it."""
        ...
    def wait(self, handle: RunHandle) -> RunResult:
        """Block on one handle; returns the finished result."""
        ...


class LocalRunner:
    """The local pool: driver subprocesses under azimo's interpreter, FIFO reaping."""

    def __init__(
        self,
        max_parallel: int = 1,
        timeout_s: float | None = DEFAULT_TIMEOUT_S,
        *,
        python: Path | None = None,
        module: str = "illumina_lab.driver",
        pythonpath: list[Path] | None = None,
    ) -> None:
        """Configure the pool; the python/module/pythonpath overrides exist for tests (a fake driver).

        ``timeout_s`` is a per-run wall-clock deadline counted from *spawn*
        (not from reaping — a queued run's clock is already ticking); ``None``
        disables the timeout entirely.
        """
        self.max_parallel = max_parallel
        self.timeout_s = timeout_s
        self.python = python or illumina_interface.python()
        self.module = module
        self.pythonpath = pythonpath or [Path(__file__).resolve().parents[2]]  # the lab's src/

    def submit(self, run: RunSpec, spec: str) -> RunHandle:
        """Write the runspec, spawn the driver subprocess, record submitted+running."""
        ledger.record("submitted", run, spec)
        run_dir = workspace.run_dir(run.label, run.run_id)
        run_dir.mkdir(parents=True, exist_ok=True)
        spec_path = run_dir / "runspec.json"
        spec_path.write_text(run.model_dump_json(indent=1) + "\n", encoding="utf-8")
        env = {
            **os.environ,
            "PYTHONPATH": os.pathsep.join(str(p) for p in self.pythonpath),
            workspace.ENV_VAR: str(workspace.workspace_root()),
        }
        log = open(run_dir / "driver.log", "w", encoding="utf-8")  # noqa: SIM115 — closed by wait()
        proc = subprocess.Popen(
            [str(self.python), "-m", self.module, str(spec_path)],
            stdout=log,
            stderr=subprocess.STDOUT,
            env=env,
        )
        ledger.record("running", run, spec, pid=proc.pid)
        return RunHandle(run=run, spec=spec, proc=proc, log=log, started=time.monotonic())

    def wait(self, handle: RunHandle) -> RunResult:
        """Block on one run; record finished/failed with duration and returncode."""
        run = handle.run
        remaining = None if self.timeout_s is None else max(0.0, handle.started + self.timeout_s - time.monotonic())
        try:
            returncode = handle.proc.wait(timeout=remaining)  # None: wait forever
        except subprocess.TimeoutExpired:
            handle.proc.kill()
            handle.proc.wait()
            returncode = -9
        duration = time.monotonic() - handle.started
        handle.log.close()
        run_dir = workspace.run_dir(run.label, run.run_id)
        ok = returncode == 0 and (run_dir / "state.json").is_file()
        ledger.record("finished" if ok else "failed", run, handle.spec, returncode=returncode, duration_s=round(duration, 1))
        return RunResult(run_id=run.run_id, ok=ok, returncode=returncode, duration_s=round(duration, 1), dir=str(run_dir))

    def run_all(self, runs: list[RunSpec], spec: str) -> list[RunResult]:
        """Run every cell under the concurrency cap; results in submission order."""
        results: dict[str, RunResult] = {}
        active: list[RunHandle] = []
        for run in runs:
            while len(active) >= self.max_parallel:
                done = self.wait(active.pop(0))  # FIFO reap — a slow head blocks the cap (v0)
                results[done.run_id] = done
            active.append(self.submit(run, spec))
        for handle in active:
            result = self.wait(handle)
            results[result.run_id] = result
        return [results[r.run_id] for r in runs]
