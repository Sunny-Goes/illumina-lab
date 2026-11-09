"""Pre-beam canary certification: the store's own harness as a lab verb (D22).

Before an execution spends tokens on beams, prove the ground truth is still sound: every
fix+reference bug's reference PoC must win on the vulnerable snapshot and die on the fixed
one. Curation owns reconstruction — the lab shells to the store's ``ci/certify.sh`` with
``LAB_CMD`` pointed back at this CLI.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys

from illumina_lab.canaries.loader import load_canary, store_root
from illumina_lab.canaries.models import RegistryError


def certify(canary_id: str) -> int:
    """Certify one canary via the store's certification harness; return its exit code."""
    canary = load_canary(canary_id)  # fails loud naming the known ids
    script = store_root() / "ci" / "certify.sh"
    if not script.is_file():
        raise RegistryError(f"no certification harness at {script} — this store does not certify")
    bugs = [b.id for b in canary.bugs if b.fix and b.reference_poc]
    print(f"certifying {canary_id} (snapshot {canary.pointer.snapshot_sha[:12]}): {len(bugs)} bugs on the certified track: {', '.join(bugs)}")
    env = {**os.environ, "LAB_CMD": f"{sys.executable} -m illumina_lab.cli"}
    return subprocess.run(["bash", str(script), str(canary.root)], env=env, check=False).returncode


def main(argv: list[str] | None = None) -> int:
    """Certify one canary from CLI arguments; stream the harness's output through."""
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("canary_id", help="the canary to certify")
    args = p.parse_args(argv)
    return certify(args.canary_id)


if __name__ == "__main__":
    sys.exit(main())
