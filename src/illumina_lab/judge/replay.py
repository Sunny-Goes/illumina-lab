#!/usr/bin/env python3
"""Replay a persisted illumina PoC workspace, optionally against a patched target.

One command, two uses:

- counterfactual judge / canary certification: replay the SAME PoC on the
  vulnerable snapshot (no patch) and on the fixed variant (--patch), comparing
  the two outcomes;
- consistency checks: replaying an archived PoC must reproduce its recorded
  outcome (run/run.json).

The ORIGINAL workspace is never modified: every replay runs on a scratch copy
(forge writes out/, and --patch must not touch archived evidence). No docker,
no third-party deps — host forge (ILLUMINA_FORGE, else forge on PATH, else
~/.foundry/bin/forge), python 3.11+.

Examples:
    tools/replay.py .cache/beam/<run>/poc/<hash>/attempt-1/workspace
    tools/replay.py <workspace> --patch fixes/ecmul-success-unchecked.patch \
        --strip 3 --target-dir lib/target

The patch paths are repo-relative (a/barretenberg/sol/src/honk/utils.sol).
In a PoC workspace the target is materialized at lib/target with the
barretenberg/sol subtree as its root, so --strip 3 --target-dir lib/target
maps a/barretenberg/sol/src/honk/utils.sol -> lib/target/src/honk/utils.sol.
For a full target clone (certification), use --strip 1 --target-dir . .

Output: one JSON object {result, returncode, command, workdir, log} on stdout;
result is "win" (exit 0), "fail" (test failures), or "error" (timeout, missing
forge, patch failure). The full forge log is preserved next to the scratch copy.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

DEFAULT_COMMAND = "forge test --match-contract PocTest -vvv"


def forge_binary() -> str | None:
    env = os.environ.get("ILLUMINA_FORGE")
    if env:
        return env
    found = shutil.which("forge")
    if found:
        return found
    default = Path.home() / ".foundry" / "bin" / "forge"
    return str(default) if default.exists() else None


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("workspace", type=Path, help="the persisted PoC workspace (a Foundry project)")
    p.add_argument("--patch", type=Path, help="repo-relative fix patch to apply before running")
    p.add_argument("--strip", type=int, default=1, help="git apply -p N (default 1; PoC workspaces need 3)")
    p.add_argument("--target-dir", default=".", help="where the target lives in the workspace (default .)")
    p.add_argument("--command", help="test command (default: run/run.json's command, else forge test --match-contract PocTest -vvv)")
    p.add_argument("--timeout", type=int, default=900, help="seconds before the run counts as error (default 900)")
    p.add_argument("--keep", action="store_true", help="keep the scratch copy for inspection")
    args = p.parse_args(argv)

    workspace = args.workspace.resolve()
    if not (workspace / "foundry.toml").is_file():
        print(json.dumps({"result": "error", "detail": f"no foundry.toml in {workspace}"}))
        return 2
    forge = forge_binary()
    if forge is None:
        print(json.dumps({"result": "error", "detail": "no forge found (set ILLUMINA_FORGE)"}))
        return 2

    command = args.command
    if command is None:
        recorded = workspace.parent / "run" / "run.json"
        try:
            command = json.loads(recorded.read_text()).get("command") or DEFAULT_COMMAND
        except (OSError, json.JSONDecodeError):
            command = DEFAULT_COMMAND
    command = command.replace("forge ", f"{forge} ", 1) if command.startswith("forge ") else command

    scratch = Path(tempfile.mkdtemp(prefix="poc-replay-"))
    workdir = scratch / "workspace"
    shutil.copytree(workspace, workdir, ignore=shutil.ignore_patterns(".git"))

    result, returncode, detail = "win", 0, ""
    log_path = scratch / "replay.log"
    try:
        if args.patch:
            applied = subprocess.run(
                ["git", "apply", "-p", str(args.strip), "--directory", args.target_dir, str(args.patch.resolve())],
                cwd=workdir, capture_output=True, text=True, check=False,
            )
            if applied.returncode != 0:
                result, detail = "error", f"patch failed: {applied.stderr.strip()}"
        if result == "win":
            with log_path.open("w") as log:
                proc = subprocess.run(
                    command, cwd=workdir, shell=True, stdout=log, stderr=subprocess.STDOUT, timeout=args.timeout, check=False,
                )
            returncode = proc.returncode
            result = "win" if returncode == 0 else "fail"
    except subprocess.TimeoutExpired:
        result, detail = "error", f"timeout after {args.timeout}s"
    except OSError as e:
        result, detail = "error", str(e)

    out = {"result": result, "returncode": returncode, "command": command,
           "workdir": str(workdir), "log": str(log_path)}
    if detail:
        out["detail"] = detail
    print(json.dumps(out, indent=1))
    if not args.keep:
        shutil.rmtree(scratch, ignore_errors=True)
    return 0 if result == "win" else 1


if __name__ == "__main__":
    sys.exit(main())
