"""The canary store's data shapes — what a canary IS, as code (D14).

The data lives in the training-set repo (``vendor/illumina-training-set``), one
directory per canary: ``canary.json`` (the :class:`CanaryPointer` — the binding
to the engine's pack/target) and ``bugs.json`` (the ground truth, a list of
:class:`BugEntry`). The loader merges them into :class:`Canary`.

Two types on purpose: the stages that build and launch a run only ever handle
the pointer — which has no ground-truth fields — so D8's leak boundary is a
type boundary, not a convention. The judge is the only stage that touches a
full :class:`Canary`.

Scope stays by reference: azimo's target manifest owns repo/path/in_scope; the
pointer records ``snapshot_sha`` and the loader's cross-check asserts it equals
the manifest's ``commit`` — drift between the lab's ground truth and the
engine's pin fails loud, either way.
"""

from __future__ import annotations

import re
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator

_KEBAB = re.compile(r"[a-z0-9-]+")
_SHA = re.compile(r"[0-9a-f]{40}")

#: The Immunefi severity vocabulary, lowercase; "" means unrecorded (seeded dev canaries).
SEVERITIES = ("critical", "high", "medium", "low", "informational")


class RegistryError(Exception):
    """A canary-store entry is malformed or inconsistent — fail fast, naming the entry."""


def _kebab(v: str) -> str:
    if not _KEBAB.fullmatch(v):
        raise ValueError(f"ids must be kebab-case ([a-z0-9-]+), got {v!r}")
    return v


class BugSite(BaseModel):
    """The bug's site at the pinned snapshot: file, function, line ranges.

    ``lines`` are 1-based ``[start, end]`` ranges in the pre-fix snapshot — the
    preimage of the fix patch's hunks. ``kind`` qualifies the range (e.g.
    ``"context"`` when the fix only adds lines, so the marked region brackets
    the insertion point rather than naming removed lines).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    file: str
    lines: list[tuple[int, int]] = []
    kind: str = ""
    function: str = ""


class BugEntry(BaseModel):
    """One ground-truth bug: what exists at the snapshot that a beam should catch.

    ``files`` are the vulnerable files — the judge's caught/missed join key
    (D6). ``win`` names the reward-table row of the bound pack expected to
    catch it: an Immunefi-style impact id, cross-checked against the pack's
    win table at load time.

    ``fix``/``sites``/``reference_poc`` are the counterfactual-attribution
    ground truth (D22): the patch the classifier replays PoCs against, the
    bug's site at the snapshot, and the curation-side certification artifact.
    All judge-side only — they must never reach the execution currency
    (:class:`CanaryPointer`).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    files: list[str] = Field(min_length=1)
    severity: str = ""
    win: str = ""
    source: str = ""  # provenance: the audit link / Immunefi page, or "seeded" + fork commit
    notes: str = ""
    fix: str = ""  # repo-relative fix patch; "" = not attributable by the counterfactual judge
    reference_poc: str = ""  # certification artifact proving the bug is exploitable at the snapshot
    sites: list[BugSite] = []

    @field_validator("id")
    @classmethod
    def _id_kebab(cls, v: str) -> str:
        """Require kebab-case ids — they become ledger and report components."""
        return _kebab(v)

    @field_validator("severity")
    @classmethod
    def _known_severity(cls, v: str) -> str:
        """Restrict severity to the Immunefi vocabulary (or empty)."""
        if v and v not in SEVERITIES:
            raise ValueError(f"severity must be one of {SEVERITIES} or empty, got {v!r}")
        return v


class CanaryPointer(BaseModel):
    """``canary.json`` — the binding between a snapshot and the engine's pack/target.

    The leak-safe currency of the execution side (D8): no ground-truth fields,
    and ``extra="forbid"`` — a canary.json carrying a ``bugs`` key fails loudly
    instead of silently breaking the two-file split.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    pack: str
    target: str
    snapshot_sha: str
    links: list[str] = []
    notes: str = ""

    @field_validator("id", "pack", "target")
    @classmethod
    def _kebab_ids(cls, v: str) -> str:
        """Require kebab-case ids — they become path and ledger components."""
        return _kebab(v)

    @field_validator("snapshot_sha")
    @classmethod
    def _full_sha(cls, v: str) -> str:
        """Require a full commit SHA — pins are exact, never abbreviated."""
        if not _SHA.fullmatch(v):
            raise ValueError(f"snapshot_sha must be a full 40-hex commit SHA, got {v!r}")
        return v


class Canary(BaseModel):
    """The full canary: the pointer + the ground truth + where it lives.

    Judge-side object — the only stage that may see ``bugs``. Constructed by
    the loader, never parsed from a file.
    """

    model_config = ConfigDict(frozen=True)

    pointer: CanaryPointer
    bugs: list[BugEntry] = Field(min_length=1)
    root: Path
