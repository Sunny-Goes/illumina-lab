"""The lab's judge: replay and counterfactual attribution of PoC artifacts to ground-truth bugs.

Run-level attribution: every PoC of an archived run, judged against the canary's fixes.
Execution-level attribution (`attribute_execution`): every finished run of one execution,
appended to the lab's attributions log.

Discovery accepts either a beam run directory (``beam/<run_id>/`` holding
``poc/<hash>/attempt-*/``) or a single attempt directory (holding ``workspace/`` and
``run/run.json``). PoCs whose recorded run was not successful are never replayed —
they are ``not-a-valid-exploit`` by the pipeline's own record. A PoC recorded successful
must reproduce its win on the vulnerable replay; a mismatch is an ``error`` (the archived
evidence does not reproduce), never a quiet attribution.

Each successful PoC is then replayed against every bug that has a fix patch, and the
verdict follows the counterfactual table:

- dies on exactly one fix   → ``confirmed:<bug-id>``;
- dies on several fixes     → ``confirmed-multiple`` (shared root cause or overlapping fixes — human review);
- dies on none, but at least one fix broke the build → ``patch-incompatible`` (the PoC's build
  died under a patch — attribution impossible, curation review);
- dies on none              → ``candidate-new-bug`` (or a different mechanism — human review).

Records are written to ``attribution.json`` next to the run's ``run.json`` (or the attempt
dir), so harvest can read them back without ever re-running replays (D4), and appended to
``attributions.jsonl`` — the lab-level judgment log, latest-wins per (run_id, poc), so
re-attribution against *new* ground truth never rewrites history.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from illumina_lab import workspace
from illumina_lab.canaries.loader import load_canary
from illumina_lab.judge import replay
from illumina_lab.orchestrator import ledger


def read_attributions() -> list[dict]:
    """Read every attribution row, in append order; empty when no log exists yet."""
    path = workspace.attributions_path()
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def latest_attributions() -> dict[tuple[str, str], dict]:
    """Return the judgment view: the newest row per (run_id, poc) — re-attribution never rewrites history."""
    out: dict[tuple[str, str], dict] = {}
    for row in read_attributions():
        out[(row["run_id"], row["poc"])] = row
    return out


def attribute_execution(
    label: str, *, force: bool = False, strip: int = 3, target_dir: str = "lib/target", timeout: int = 900, now: datetime | None = None
) -> list[dict]:
    """Attribute every finished run of one execution against its canary's fixes.

    Skips failed runs (``error.json``) and already-attributed runs unless ``force``
    (re-attribution is how new ground truth reaches old runs — latest-wins in the log).
    ``strip``/``target_dir`` default to azimo's PoC workspace layout. Returns the new rows.
    """
    root = workspace.artifacts_dir(label)
    if not root.is_dir():
        return []
    attributed = set() if force else _attributed_run_ids()
    ts = (now or datetime.now(timezone.utc)).isoformat()
    new_rows: list[dict] = []
    for run_artifacts in sorted(root.iterdir()):
        if not run_artifacts.is_dir():
            continue
        run_id = run_artifacts.name
        if run_id in attributed or (run_artifacts / "error.json").is_file():
            continue
        runspec = _read_json(run_artifacts / "runspec.json")
        canary_id = runspec.get("canary_id", "")
        cache_run = workspace.illumina_cache() / "beam" / label / run_id
        if not canary_id or not cache_run.is_dir():
            continue
        canary = load_canary(canary_id)
        records = attribute_run(cache_run, canary.root, strip=strip, target_dir=target_dir, timeout=timeout)
        (cache_run / "attribution.json").write_text(json.dumps({"records": records}, indent=1) + "\n", encoding="utf-8")
        new_rows.extend({"label": label, "run_id": run_id, "attributed_at": ts, **r} for r in records)
        spec = ledger.latest_by_run().get(run_id, {}).get("spec", "")
        ledger.record_event(
            "attributed",
            run_id=run_id,
            label=label,
            spec=spec,
            cell={"canary": canary_id, "win": runspec.get("win", ""), "seed": runspec.get("seed", 0)},
            verdicts=[r["verdict"] for r in records],
        )
    if new_rows:
        path = workspace.attributions_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            for row in new_rows:
                f.write(json.dumps(row) + "\n")
    return new_rows


def _attributed_run_ids() -> set[str]:
    """Return the run ids already judged: rows in the attributions log or an `attributed` ledger event (zero-PoC runs)."""
    from_log = {row["run_id"] for row in read_attributions()}
    from_ledger = {row["run_id"] for row in ledger.events() if row["event"] == "attributed"}
    return from_log | from_ledger


def _read_json(path: Path) -> dict:
    """Read one JSON artifact; absent or malformed reads as empty (attribution never dies on a partial run)."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def discover_pocs(run_dir: Path) -> list[dict]:
    """Return the run's PoC attempt dirs with their recorded outcomes, sorted for determinism."""
    if (run_dir / "workspace").is_dir() and (run_dir / "run" / "run.json").is_file():
        attempts = [run_dir]
    else:
        attempts = sorted(run_dir.glob("poc/*/attempt-*"))
    out = []
    for attempt in attempts:
        try:
            recorded = json.loads((attempt / "run" / "run.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            recorded = {}
        out.append({
            "id": str(attempt),
            "workspace": attempt / "workspace",
            "recorded_ok": bool(recorded.get("ok")),
        })
    return out


def attribute_poc(workspace: Path, bugs: list[dict], canary_dir: Path, *, strip: int, target_dir: str, timeout: int, keep: bool) -> dict:
    """Replay one recorded-successful PoC on vulnerable + every fix and compute the verdict."""
    vulnerable = replay.run(workspace, timeout=timeout, keep=keep)
    record: dict = {"vulnerable": vulnerable["result"]}
    if vulnerable["result"] != "win":
        record["verdict"] = "error"
        record["detail"] = "recorded ok but the vulnerable replay did not win — archived evidence does not reproduce"
        return record
    fixed = {}
    for bug in bugs:
        outcome = replay.run(
            workspace, patch=canary_dir / bug["fix"], strip=strip, target_dir=target_dir, timeout=timeout, keep=keep,
        )
        fixed[bug["id"]] = outcome["result"]
    record["fixed"] = fixed
    died = [bug_id for bug_id, result in fixed.items() if result == "fail"]
    if len(died) == 1:
        record["verdict"] = f"confirmed:{died[0]}"
    elif died:
        record["verdict"] = "confirmed-multiple"
        record["bugs"] = died
    elif any(result == "build-error" for result in fixed.values()):
        record["verdict"] = "patch-incompatible"
    else:
        record["verdict"] = "candidate-new-bug"
    return record


def attribute_run(run_dir: Path, canary_dir: Path, *, strip: int = 1, target_dir: str = ".", timeout: int = 900, keep: bool = False) -> list[dict]:
    """Judge every PoC of one archived run against the canary's fix-carrying bugs."""
    bugs = [b for b in json.loads((canary_dir / "bugs.json").read_text(encoding="utf-8")) if b.get("fix")]
    records = []
    for poc in discover_pocs(run_dir):
        record: dict = {"poc": poc["id"], "workspace": str(poc["workspace"])}
        if not poc["recorded_ok"]:
            record["verdict"] = "not-a-valid-exploit"
        else:
            record.update(attribute_poc(poc["workspace"], bugs, canary_dir, strip=strip, target_dir=target_dir, timeout=timeout, keep=keep))
        records.append(record)
    return records


def main(argv: list[str] | None = None) -> int:
    """Attribute all PoCs of an archived run and write attribution.json next to its run.json."""
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("run_dir", type=Path, help="a beam run dir (with poc/) or a single attempt dir (with workspace/ and run/)")
    p.add_argument("--canary-dir", type=Path, required=True, help="canary directory holding bugs.json and fixes/")
    p.add_argument("--strip", type=int, default=1, help="git apply -p N (default 1; PoC workspaces need 3)")
    p.add_argument("--target-dir", default=".", help="where the target lives in the workspace (default .)")
    p.add_argument("--timeout", type=int, default=900, help="seconds per replay (default 900)")
    p.add_argument("--keep", action="store_true", help="keep the scratch copies for inspection")
    p.add_argument("--no-write", action="store_true", help="print the records without writing attribution.json")
    args = p.parse_args(argv)

    records = attribute_run(
        args.run_dir, args.canary_dir, strip=args.strip, target_dir=args.target_dir, timeout=args.timeout, keep=args.keep,
    )
    if not args.no_write:
        (args.run_dir / "attribution.json").write_text(json.dumps({"records": records}, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({"records": records}, indent=1))
    return 0 if any(r["verdict"].startswith("confirmed") for r in records) else 1


if __name__ == "__main__":
    import sys

    sys.exit(main())
