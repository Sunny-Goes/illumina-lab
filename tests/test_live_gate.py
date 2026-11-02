"""The live gate itself: skips without the env var, passes with it."""

import pytest
from _pytest.outcomes import Skipped
from conftest import LIVE_ENV_VAR, require_live


def test_require_live_skips_without_env(monkeypatch):
    monkeypatch.delenv(LIVE_ENV_VAR, raising=False)
    with pytest.raises(Skipped):
        require_live()


def test_require_live_passes_with_env(monkeypatch):
    monkeypatch.setenv(LIVE_ENV_VAR, "1")
    require_live()


@pytest.mark.live
def test_live_marker_wiring():
    """Always skipped offline; runs under the gate to prove marker + helper compose."""
    require_live()
