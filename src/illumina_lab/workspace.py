"""The workspace seam — the one module that knows where the lab persists (D15).

Everything the lab writes — the run ledger, the facts log, per-run artifacts,
azimo's run caches — lives under one workspace root and is located through
this module, never through ad-hoc paths elsewhere. Local files today: the
ledger and facts records are flat and join-keyed (``run_id`` joins
everything), mapping 1:1 onto tables when a DB backend arrives — swapping
backends means this module, never the pipeline.

Layout:

    <workspace>/
    ├── ledger.jsonl                    # one row per run event (submit/start/finish/fail)
    ├── facts.jsonl                     # one row per harvested run
    ├── artifacts/<label>/<run_id>/     # what the lab wrote about a run (spec, state dump, logs)
    └── illumina-cache/<label>/         # the driver's ILLUMINA_CACHE: azimo's evidence tree
"""

from __future__ import annotations

import os
from pathlib import Path

ENV_VAR = "ILAB_WORKSPACE"


def workspace_root() -> Path:
    """Return the workspace root: ``$ILAB_WORKSPACE`` when set, else ``<repo>/runs/``."""
    raw = os.environ.get(ENV_VAR, "").strip()
    if raw:
        return Path(raw).expanduser()
    return Path(__file__).resolve().parents[2] / "runs"


def ledger_path() -> Path:
    """Return the run ledger's path (append-only JSONL)."""
    return workspace_root() / "ledger.jsonl"


def facts_path() -> Path:
    """Return the facts log's path (append-only JSONL)."""
    return workspace_root() / "facts.jsonl"


def artifacts_dir(label: str) -> Path:
    """Return the artifacts dir of one execution of an experiment."""
    return workspace_root() / "artifacts" / label


def run_dir(label: str, run_id: str) -> Path:
    """Return one run's artifact dir within an execution."""
    return artifacts_dir(label) / run_id


def illumina_cache_dir(label: str) -> Path:
    """Return the ``ILLUMINA_CACHE`` the driver sets for one execution's beam runs."""
    return workspace_root() / "illumina-cache" / label


def ensure() -> Path:
    """Create the workspace layout if missing; return the root."""
    root = workspace_root()
    (root / "artifacts").mkdir(parents=True, exist_ok=True)
    return root
