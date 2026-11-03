"""Live end-to-end: one real beam through the LocalRunner + driver (ILAB_LIVE_TESTS=1).

Costs real tokens and minutes: a full honk beam runs against the pinned canary
snapshot inside azimo's own venv. Asserts *validity*, never caught/missed
(D16): the run produced a state dump under our run_id and the detector left a
coverage record — the hunt happened. Judgment is the judge's (PR 6), read off
the scoreboard, not asserted here.

Requires: a provider key in the environment (e.g. ANTHROPIC_API_KEY), network
(the target's sparse clone fetches on first run), and the azimo venv
(``cd vendor/azimo && uv sync``).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from conftest import require_live

from illumina_lab import illumina_interface, workspace
from illumina_lab.experiment import RunSpec
from illumina_lab.orchestrator.runner import LocalRunner, timeout_from_env

pytestmark = pytest.mark.live


def test_real_beam_end_to_end(tmp_path, monkeypatch):
    require_live()
    if not illumina_interface.python().is_file():
        pytest.skip("azimo venv missing — cd vendor/azimo && uv sync")
    monkeypatch.setenv(workspace.ENV_VAR, str(tmp_path))
    run = RunSpec(
        run_id="exp-live-smoke-20261103-1-honk-precompile-success-unchecked-direct-unconstrained-exploitability-s1",
        label="exp-live-smoke-20261103-1",
        canary_id="honk-precompile-success-unchecked",
        pack="honk",
        target="precompile-success-unchecked",
        win="direct-unconstrained-exploitability",
        seed=1,
    )
    runner = LocalRunner(timeout_s=timeout_from_env())
    result = runner.wait(runner.submit(run, "live"))
    assert result.ok, f"beam failed — see {result.dir}/driver.log and error.json"
    state = json.loads((Path(result.dir) / "state.json").read_text())
    assert state.get("run_id") == run.run_id  # azimo#174: the engine carried our id end to end
    scans = [c for c in state.get("coverage", []) if c.get("kind") == "llm_scan"]
    assert scans, "no coverage record — the hunt never happened"
