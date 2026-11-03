"""A fake driver for runner tests — reads the runspec, writes state.json, fails/sleeps on demand.

Spawned as ``python -m fake_driver <runspec.json>`` by LocalRunner under test: no lab
imports, stdlib only — it proves the runner's machinery (env, logs, exit codes) without
touching azimo. "fail"/"slow" in the run_id trigger the failure/timeout paths; when
FAKE_DRIVER_MARKERS names a file, start/end lines append there (the concurrency-cap test).
"""

import json
import os
import sys
import time
from pathlib import Path


def main() -> int:
    spec = json.loads(Path(sys.argv[1]).read_text())
    run = Path(os.environ["ILAB_WORKSPACE"]) / "artifacts" / spec["label"] / spec["run_id"]
    run.mkdir(parents=True, exist_ok=True)
    markers = os.environ.get("FAKE_DRIVER_MARKERS")
    if markers:
        with open(markers, "a") as f:
            f.write(f"start {spec['run_id']}\n")
    if "fail" in spec["run_id"]:
        (run / "error.json").write_text("{}")
        return 1
    if "slow" in spec["run_id"]:
        time.sleep(30)
    time.sleep(0.05)
    (run / "state.json").write_text(json.dumps({"findings": []}))
    sys.stdout.write(f"fake driver ran {spec['run_id']}\n")
    if markers:
        with open(markers, "a") as f:
            f.write(f"end {spec['run_id']}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
