"""Live: the pinned store's canary certification passes against THIS lab's judge.

The training set's ``ci/certify.sh`` is the known-answer control for the
classifier: every fix+reference-carrying bug must certify — the reference PoC
wins on the vulnerable snapshot and dies on the fixed one (verdict
``confirmed``). Run this before trusting beam results over a new pin:
store/schema/forge drift surfaces here, not in a misjudged run.

Requires ILAB_LIVE_TESTS=1, forge, and network (sparse, blob-filtered fetch of
the snapshot + forge-std at the pinned rev). No model calls — this spends no
tokens.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from conftest import require_live

from illumina_lab.judge import replay

pytestmark = pytest.mark.live


def test_pinned_canary_certifies():
    require_live()
    store = Path(__file__).resolve().parents[1] / "vendor" / "illumina-training-set"
    script = store / "ci" / "certify.sh"
    canary = store / "canaries" / "honk" / "precompile-success-unchecked"
    if not (script.is_file() and canary.is_dir()):
        pytest.skip("training-set submodule not initialized")
    if replay.forge_binary() is None:
        pytest.skip("forge not available")
    env = {**os.environ, "LAB_CMD": f"{sys.executable} -m illumina_lab.cli"}
    proc = subprocess.run(
        ["bash", str(script), str(canary)],
        env=env, capture_output=True, text=True, timeout=2400, check=False,
    )
    assert proc.returncode == 0, f"certification failed:\n{proc.stdout}\n{proc.stderr}"
