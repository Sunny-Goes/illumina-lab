"""Experiment identity and naming (D10).

The spec hash IS the experiment's identity: the canonical spec content plus
the pinned azimo SHA and the pinned training-set SHA — the same spec file on a
moved engine or moved ground truth is a *different* experiment. The hash has
12 hex chars; the execution label carries 8 for human browsing (the full hash
rides the ledger and facts rows).

    spec hash   exp identity: <sha12>                   dedupe key, stored everywhere
    label       exp-<sha8>-<name>-<yyyymmdd>-<n>        one execution of the spec
    run_id      <label>-<canary>-<win>-s<k>             one matrix cell's run

Labels and run ids become directory names (the workspace's, azimo's evidence
folder, the LangSmith project) — they stay kebab-safe because canary and win
ids are already kebab (``canaries/models.py``).
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Iterable

from illumina_lab.experiment import ExperimentSpec


def spec_hash(spec: ExperimentSpec, azimo_sha: str, training_set_sha: str) -> str:
    """Return the experiment's identity: sha256 of {canonical spec, azimo pin, store pin}, 12 hex chars."""
    blob = json.dumps(
        {"spec": spec.model_dump(), "azimo": azimo_sha, "training_set": training_set_sha},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(blob.encode()).hexdigest()[:12]


def execution_label(spec: ExperimentSpec, azimo_sha: str, training_set_sha: str, *, now: datetime | None = None, existing: Iterable[str] = ()) -> str:
    """Mint one execution's label: ``exp-<sha8>-<name>-<yyyymmdd>-<n>`` — n is the next free index that day."""
    digest = spec_hash(spec, azimo_sha, training_set_sha)
    now = now or datetime.now(timezone.utc)
    stem = f"exp-{digest[:8]}-{spec.name}-{now:%Y%m%d}"
    taken = set(existing)
    n = 1
    while f"{stem}-{n}" in taken:
        n += 1
    return f"{stem}-{n}"


def run_id(label: str, canary_id: str, win: str, seed: int) -> str:
    """Mint one matrix cell's run id: ``<label>-<canary>-<win>-s<seed>``."""
    return f"{label}-{canary_id}-{win}-s{seed}"
