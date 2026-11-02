"""The canary-store loader — read and validate canary entries from the training-set.

The canary store's home is the ``vendor/illumina-training-set`` submodule — the
ground-truth store, version-pinned by the lab so every experiment records which
ground truth judged it. ``ILAB_CANARY_STORE`` overrides the location (synthetic
stores in tests, a curated checkout elsewhere). Layout:
``canaries/<codebase>/<snapshot>/{canary.json,bugs.json}`` — one canary is one
codebase at one commit, snapshots group under their codebase, and the id
convention is ``<codebase>-<snapshot>``, enforced here.

The loader merges ``canary.json`` (:class:`~illumina_lab.canaries.models.CanaryPointer`)
and ``bugs.json`` into a :class:`~illumina_lab.canaries.models.Canary`. The
pointer is the leak-safe part — execution stages see only it (D8).

Validation at this layer is *structural* — shape, id conventions, uniqueness.
The deep validators (hunk-presence, SHA-reachability, leak check) are v1; the
azimo-store cross-check is the sibling concern (the pack/target/commit the
entry binds to exists and agrees).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from pydantic import ValidationError

from illumina_lab.canaries.models import BugEntry, Canary, CanaryPointer, RegistryError

ENV_VAR = "ILAB_CANARY_STORE"


def store_root() -> Path:
    """Return the canary store's root: ``$ILAB_CANARY_STORE`` when set, else the training-set submodule."""
    raw = os.environ.get(ENV_VAR, "").strip()
    root = Path(raw).expanduser() if raw else Path(__file__).resolve().parents[3] / "vendor" / "illumina-training-set"
    if not (root / "canaries").is_dir():
        raise RegistryError(f"no canary store at {root} — set {ENV_VAR} or init the submodule: git submodule update --init")
    return root


def load_canaries(root: Path | None = None) -> list[Canary]:
    """Load every canary in the store, sorted by id."""
    root = root or store_root()
    entries = [_load_one(d) for d in sorted((root / "canaries").glob("*/*")) if d.is_dir()]
    return sorted(entries, key=lambda e: e.pointer.id)


def load_canary(canary_id: str, root: Path | None = None) -> Canary:
    """Load one canary by id — fails loud naming the known ids on a miss."""
    entries = load_canaries(root)
    for e in entries:
        if e.pointer.id == canary_id:
            return e
    known = ", ".join(e.pointer.id for e in entries) or "(none)"
    raise RegistryError(f"unknown canary {canary_id!r}; known: {known}")


def _load_one(d: Path) -> Canary:
    """Load one canary directory: ``canary.json`` + ``bugs.json``, structurally validated."""
    expected_id = f"{d.parent.name}-{d.name}"
    pointer = _parse_pointer(d / "canary.json", d)
    bugs = _parse_bugs(d / "bugs.json", d)
    if pointer.id != expected_id:
        raise RegistryError(f"{d}: id {pointer.id!r} disagrees with its path — must be {expected_id!r} (<codebase>-<snapshot>)")
    ids = [b.id for b in bugs]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    if dupes:
        raise RegistryError(f"{d}: duplicate bug ids: {', '.join(dupes)}")
    return Canary(pointer=pointer, bugs=bugs, root=d)


def _parse_pointer(path: Path, d: Path) -> CanaryPointer:
    """Parse one canary.json into a CanaryPointer, RegistryError naming the entry on any failure."""
    if not path.is_file():
        raise RegistryError(f"{d}: missing {path.name}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise RegistryError(f"{d}: malformed JSON in {path.name}: {e}") from e
    try:
        return CanaryPointer(**data)
    except ValidationError as e:
        raise RegistryError(f"{d}: invalid {path.name}: {e}") from e


def _parse_bugs(path: Path, d: Path) -> list[BugEntry]:
    """Parse one bugs.json into BugEntry rows, RegistryError naming the entry on any failure."""
    if not path.is_file():
        raise RegistryError(f"{d}: missing {path.name}")
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise RegistryError(f"{d}: malformed JSON in {path.name}: {e}") from e
    if not isinstance(rows, list) or any(not isinstance(r, dict) for r in rows):
        raise RegistryError(f"{d}: {path.name} must be a JSON list of objects")
    try:
        return [BugEntry(**r) for r in rows]
    except ValidationError as e:
        raise RegistryError(f"{d}: invalid {path.name}: {e}") from e
