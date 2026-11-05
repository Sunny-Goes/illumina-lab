"""Harvest: run artifacts become facts rows (D4).

Facts are a *view*, not the truth. The truth is the run's artifacts: the lab's
``artifacts/<label>/<run_id>/`` (state dump, runspec, provenance), azimo's
``illumina-cache/beam/<label>/<run_id>/run.json``, and the ledger. Harvest reads
them and appends one flat row per run to ``facts.jsonl`` — generously: fields
no current metric needs are kept, so a future fitness function never requires
re-running (D4). Rows are flat and join-keyed (``run_id``), DB-mappable (D15).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

from illumina_lab import workspace
from illumina_lab.orchestrator import ledger


class CoverageFacts(BaseModel):
    """The detector's provenance, aggregated: what it read, what it cost, whether it errored."""

    model_config = ConfigDict(frozen=True)

    files_read: list[str] = []
    llm_calls: int = 0
    tool_calls: dict[str, int] = {}
    probes: int = 0
    hypotheses: int = 0
    scans: int = 0  # llm_scan entries — 0 means the hunt never happened (the invalid gate)
    errored: str = ""


class FactsRow(BaseModel):
    """One run's harvested facts — one row per run in facts.jsonl."""

    model_config = ConfigDict(frozen=True)

    run_id: str
    label: str
    spec: str = ""
    canary: str = ""
    win: str = ""
    seed: int = 0
    azimo_sha: str = ""
    training_set_sha: str = ""
    target_commit: str = ""
    ok: bool = False
    returncode: int = 0
    duration_s: float = 0.0
    findings: list[dict] = []
    findings_by_status: dict[str, int] = {}
    poc_inputs: int = 0
    poc_runs: list[dict] = []
    attributions: list[dict] = []
    coverage: CoverageFacts = CoverageFacts()
    models: dict[str, str] = {}
    harvested_at: str = ""


def harvest_run(label: str, run_id: str, *, now: datetime | None = None) -> FactsRow:
    """Assemble one run's facts row from its artifacts (state dump, runspec, provenance, azimo's run.json, ledger)."""
    run_dir = workspace.run_dir(label, run_id)
    state = _read_json(run_dir / "state.json")
    runspec = _read_json(run_dir / "runspec.json")
    provenance = _read_json(run_dir / "provenance.json")
    run_json = _read_json(workspace.illumina_cache() / "beam" / label / run_id / "run.json")
    latest = ledger.latest_by_run().get(run_id, {})

    findings = state.get("findings", [])
    by_status: dict[str, int] = {}
    for f in findings:
        by_status[f.get("status", "?")] = by_status.get(f.get("status", "?"), 0) + 1
    harvested = (now or datetime.now(timezone.utc)).isoformat()
    return FactsRow(
        run_id=run_id,
        label=label,
        spec=latest.get("spec", ""),
        canary=runspec.get("canary_id", ""),
        win=runspec.get("win", ""),
        seed=runspec.get("seed", 0),
        azimo_sha=provenance.get("azimo_sha", ""),
        training_set_sha=provenance.get("training_set_sha", ""),
        target_commit=(state.get("target") or {}).get("commit", ""),
        ok=(run_dir / "state.json").is_file() and not (run_dir / "error.json").is_file(),
        returncode=latest.get("returncode", 0),
        duration_s=latest.get("duration_s", 0.0),
        findings=findings,
        findings_by_status=by_status,
        poc_inputs=len(state.get("poc_inputs", [])),
        poc_runs=state.get("poc_runs", []),
        attributions=_read_json(workspace.illumina_cache() / "beam" / label / run_id / "attribution.json").get("records", []),
        coverage=_coverage_facts(state.get("coverage", [])),
        models=run_json.get("models", {}),
        harvested_at=harvested,
    )


def _coverage_facts(entries: list[dict]) -> CoverageFacts:
    """Aggregate the coverage channel: llm_scan entries plus probe entries (azimo #155)."""
    scans = [c for c in entries if c.get("kind") == "llm_scan"]
    probes = [c for c in entries if c.get("kind") == "probe"]
    tool_calls: dict[str, int] = {}
    for c in scans:
        for tool, n in (c.get("tool_calls") or {}).items():
            tool_calls[tool] = tool_calls.get(tool, 0) + n
    return CoverageFacts(
        files_read=sorted({f for c in scans for f in c.get("files_read", [])}),
        llm_calls=sum(c.get("llm_calls", 0) for c in scans),
        tool_calls=tool_calls,
        probes=len(probes),
        hypotheses=sum(p.get("hypotheses", 0) for p in probes),
        scans=len(scans),
        errored=next((c["errored"] for c in scans if c.get("errored")), ""),
    )


def _read_json(path: Path) -> dict[str, Any]:
    """Read one JSON artifact; absent or malformed reads as empty (harvest never dies on a partial run)."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def read_facts() -> list[FactsRow]:
    """Read every facts row, in append order; empty when no facts log exists yet."""
    path = workspace.facts_path()
    if not path.is_file():
        return []
    return [FactsRow(**json.loads(line)) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def harvest_execution(label: str) -> list[FactsRow]:
    """Harvest every run of one execution into facts.jsonl — idempotent per run_id. Returns the new rows."""
    root = workspace.artifacts_dir(label)
    if not root.is_dir():
        return []
    known = {row.run_id for row in read_facts()}
    new = [harvest_run(label, d.name) for d in sorted(root.iterdir()) if d.is_dir() and d.name not in known]
    if new:
        path = workspace.facts_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            for row in new:
                f.write(row.model_dump_json() + "\n")
    return new
