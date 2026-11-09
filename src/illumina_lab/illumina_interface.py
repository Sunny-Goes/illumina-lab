"""The lab's interface to illumina, the engine under test — where it lives, nothing more.

The engine's repo is azimo, its package is illumina; this module resolves both
into the lab's vocabulary. The pin mechanics are git's (the submodule gitlink
at ``vendor/azimo``); this module is path resolution and pin reading: the
checkout, its pack store, its venv python (the driver's interpreter, PR 4), and
``pin_sha`` for the SHAs that ride every experiment's identity (D10). No lab
code imports illumina in-process — the engine runs in its own locked venv
(D9); this module only knows where the files are.

Call sites alias it short: ``from illumina_lab import illumina_interface as illumina``.
"""

from __future__ import annotations

import subprocess
from pathlib import Path


def root() -> Path:
    """Return the engine's checkout: ``<repo>/vendor/azimo``."""
    return Path(__file__).resolve().parents[2] / "vendor" / "azimo"


def store() -> Path:
    """Return the engine's pack store — what the driver's ``ILLUMINA_STORE`` points at."""
    return root() / "store"


def python() -> Path:
    """Return the engine venv's interpreter — the driver's python (PR 4)."""
    return root() / ".venv" / "bin" / "python"


def pin_sha(path: Path) -> str:
    """Return a vendor checkout's pinned commit (its git HEAD) — the SHAs ride every experiment's identity (D10)."""
    proc = subprocess.run(["git", "-C", str(path), "rev-parse", "HEAD"], capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"could not read the pin of {path}: {proc.stderr.strip()}")
    return proc.stdout.strip()
