"""The registry's data shapes — what a canary IS, as code (D14).

The data lives in the training-set repo (``vendor/illumina-training-set``), one
directory per canary: ``canary.json`` (the binding to the engine's pack/target)
and ``bugs.json`` (the ground truth). These models are the contract both files
validate against; the loader merges them. Scope stays by reference: azimo's
target manifest owns repo/path/in_scope, the entry records ``snapshot_sha`` and
the loader's cross-check asserts it equals the manifest's ``commit`` — drift
between the lab's ground truth and the engine's pin fails loud, either way.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict, Field, field_validator

_KEBAB = re.compile(r"[a-z0-9-]+")
_SHA = re.compile(r"[0-9a-f]{40}")

#: The Immunefi severity vocabulary, lowercase; "" means unrecorded (seeded dev canaries).
SEVERITIES = ("critical", "high", "medium", "low", "informational")


class RegistryError(Exception):
    """A registry entry is malformed or inconsistent — fail fast, naming the entry."""


class BugEntry(BaseModel):
    """One ground-truth bug: what exists at the snapshot that a beam should catch.

    ``files`` are the vulnerable files — the judge's caught/missed join key
    (D6). ``win`` names the reward-table row of the bound pack expected to
    catch it: an Immunefi-style impact id, cross-checked against the pack's
    win table at load time.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    files: list[str] = Field(min_length=1)
    severity: str = ""
    win: str = ""
    source: str = ""  # provenance: the audit link / Immunefi page, or "seeded" + fork commit
    notes: str = ""

    @field_validator("id")
    @classmethod
    def kebab(cls, v: str) -> str:
        """Require kebab-case ids — they become path and ledger components."""
        if not _KEBAB.fullmatch(v):
            raise ValueError(f"bug id must be kebab-case ([a-z0-9-]+), got {v!r}")
        return v

    @field_validator("severity")
    @classmethod
    def known_severity(cls, v: str) -> str:
        """Restrict severity to the Immunefi vocabulary (or empty)."""
        if v and v not in SEVERITIES:
            raise ValueError(f"severity must be one of {SEVERITIES} or empty, got {v!r}")
        return v


class Canary(BaseModel):
    """One canary — the binding between ground truth and the engine's pack/target.

    ``canary.json``'s shape. The bugs live in the sibling ``bugs.json`` (a list
    of :class:`BugEntry`); this model deliberately has no ``bugs`` field, so a
    merged file fails loudly instead of silently winning the split.
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
    def kebab(cls, v: str) -> str:
        """Require kebab-case ids — they become path and ledger components."""
        if not _KEBAB.fullmatch(v):
            raise ValueError(f"ids must be kebab-case ([a-z0-9-]+), got {v!r}")
        return v

    @field_validator("snapshot_sha")
    @classmethod
    def full_sha(cls, v: str) -> str:
        """Require a full commit SHA — pins are exact, never abbreviated."""
        if not _SHA.fullmatch(v):
            raise ValueError(f"snapshot_sha must be a full 40-hex commit SHA, got {v!r}")
        return v
