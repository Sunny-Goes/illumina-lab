"""The counterfactual pair: replay one PoC on the vulnerable and the fixed target, read the verdict.

Attribution is an experiment, not an inference: a PoC is ABOUT bug X when it wins on the
vulnerable snapshot and dies on the same snapshot with X's fix applied. Validity comes first —
a PoC that does not win on the buggy code is not an exploit at all, whatever its intent.

Verdicts:
- ``confirmed``            — vulnerable: win, fixed: fail. The exploit requires this bug.
- ``not-specific``         — vulnerable: win, fixed: win. It wins without the bug too: a
                             different mechanism, another bug, or a self-contained simulation.
- ``not-a-valid-exploit``  — vulnerable: fail/error. Includes the inverted case (fails on buggy,
                             passes on fixed): on-target intent, no valid win on the buggy code.
- ``error``                — the harness itself could not produce a verdict (timeout, patch
                             failure, missing forge).

Example:
    illumina-lab counterfactual .cache/poc/<run>/<hash>/attempt-1/workspace \
        --canary-dir canaries/honk/precompile-success-unchecked --bug ecmul-success-unchecked \
        --strip 3 --target-dir lib/target
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from illumina_lab.judge import replay


def verdict(vulnerable: str, fixed: str) -> str:
    """Map the two replay outcomes to the attribution verdict (validity first)."""
    if vulnerable != "win":
        return "not-a-valid-exploit"
    if fixed == "fail":
        return "confirmed"
    if fixed == "win":
        return "not-specific"
    return "error"


def resolve_patch(canary_dir: Path, bug_id: str) -> Path:
    """Return the fix patch for one bug of a canary directory; fail loud on unknown/unfixed bugs."""
    bugs = json.loads((canary_dir / "bugs.json").read_text(encoding="utf-8"))
    for bug in bugs:
        if bug.get("id") == bug_id:
            fix = bug.get("fix")
            if not fix:
                raise ValueError(f"bug {bug_id!r} has no fix patch recorded")
            return canary_dir / fix
    raise ValueError(f"bug {bug_id!r} not found in {canary_dir}/bugs.json")


def main(argv: list[str] | None = None) -> int:
    """Run the vulnerable and the fixed replay and print the attribution verdict as JSON."""
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("workspace", type=Path, help="the persisted PoC workspace (a Foundry project)")
    p.add_argument("--patch", type=Path, help="repo-relative fix patch (or use --canary-dir + --bug)")
    p.add_argument("--canary-dir", type=Path, help="canary directory holding bugs.json")
    p.add_argument("--bug", help="bug id in the canary's bugs.json — its fix patch is used")
    p.add_argument("--strip", type=int, default=1, help="git apply -p N (default 1; PoC workspaces need 3)")
    p.add_argument("--target-dir", default=".", help="where the target lives in the workspace (default .)")
    p.add_argument("--command", help="test command override (default: the workspace's recorded command)")
    p.add_argument("--timeout", type=int, default=900, help="seconds per replay (default 900)")
    p.add_argument("--keep", action="store_true", help="keep the scratch copies for inspection")
    args = p.parse_args(argv)

    patch = args.patch
    if patch is None and args.bug:
        if args.canary_dir is None:
            p.error("--bug requires --canary-dir")
        patch = resolve_patch(args.canary_dir, args.bug)
    if patch is None:
        p.error("a fix patch is required: --patch or --canary-dir + --bug")

    vulnerable = replay.run(args.workspace, command=args.command, timeout=args.timeout, keep=args.keep)
    fixed = replay.run(
        args.workspace, patch=patch, strip=args.strip, target_dir=args.target_dir,
        command=args.command, timeout=args.timeout, keep=args.keep,
    )
    out = {
        "verdict": verdict(vulnerable["result"], fixed["result"]),
        "vulnerable": vulnerable,
        "fixed": fixed,
        "patch": str(patch),
    }
    print(json.dumps(out, indent=1))
    return 0 if out["verdict"] == "confirmed" else 1


if __name__ == "__main__":
    import sys

    sys.exit(main())
