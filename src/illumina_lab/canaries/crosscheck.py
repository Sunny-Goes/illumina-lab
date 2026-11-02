"""The azimo-store cross-check — the lab's ground truth and the engine's pins must agree.

A canary binds by reference: azimo's target manifest owns repo/path/in_scope,
and the lab's ``snapshot_sha`` is only a record of what that manifest should
pin. This module verifies the binding so drift between the training-set and
the azimo submodule fails loud at validation time, never mid-run:

- the pack exists in the engine's store, and its win table covers every
  ``bug.win``;
- the target manifest exists, and its ``commit`` equals the pointer's
  ``snapshot_sha``;
- every bug file is in the manifest's ``in_scope`` — a beam can only flag
  what it can read.
"""

from __future__ import annotations

import json
from pathlib import Path

from illumina_lab import illumina_interface
from illumina_lab.canaries.models import Canary, RegistryError


def validate_binding(canary: Canary, store: Path | None = None) -> None:
    """Check one canary against the engine's store; raise RegistryError listing every violation."""
    store = store or illumina_interface.store()
    p = canary.pointer
    problems: list[str] = []
    pack_dir = store / "packs" / p.pack

    if not (pack_dir / "pack.json").is_file():
        problems.append(f"pack {p.pack!r} not found in {store}/packs")
    else:
        wins_path = pack_dir / "win_conditions.json"
        if wins_path.is_file():
            win_ids = {r.get("id") for r in _read_rows(wins_path, p.id)}
            for bug in canary.bugs:
                if bug.win and bug.win not in win_ids:
                    problems.append(f"bug {bug.id!r}: win {bug.win!r} is not a row of {p.pack}'s win_conditions.json")

    manifest_path = pack_dir / "targets" / f"{p.target}.json"
    if pack_dir.is_dir() and not manifest_path.is_file():
        problems.append(f"target manifest {p.target!r} not found at {manifest_path}")
    elif manifest_path.is_file():
        manifest = _read_json(manifest_path, p.id)
        commit = manifest.get("commit", "")
        if commit != p.snapshot_sha:
            problems.append(f"commit drift: the manifest pins {commit[:12] or '?'}, the canary records {p.snapshot_sha[:12]}")
        in_scope = set(manifest.get("in_scope", []))
        for bug in canary.bugs:
            for f in bug.files:
                if f not in in_scope:
                    problems.append(f"bug {bug.id!r}: file {f!r} is not in {p.target}'s in_scope")

    if problems:
        raise RegistryError(f"canary {p.id!r} disagrees with the engine store:\n- " + "\n- ".join(problems))


def _read_json(path: Path, canary_id: str) -> dict:
    """Read one manifest, RegistryError naming the canary on malformed JSON."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise RegistryError(f"canary {canary_id!r}: malformed JSON in the engine store at {path}: {e}") from e


def _read_rows(path: Path, canary_id: str) -> list[dict]:
    """Read one win table, RegistryError naming the canary on malformed JSON or shape."""
    rows = _read_json(path, canary_id)
    if not isinstance(rows, list):
        raise RegistryError(f"canary {canary_id!r}: {path} must be a JSON list")
    return rows
