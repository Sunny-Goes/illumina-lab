"""Shared pytest helpers for the lab suite — the live gate.

Tests marked ``@pytest.mark.live`` run real beams through azimo: real LLM
calls, real tokens, real minutes. They are opt-in, so a bare ``pytest`` (or
CI) never spends money by accident: without ``ILAB_LIVE_TESTS=1`` they skip.
The provider-key check lives one layer down — azimo's driver fails loudly on
a missing key when a live run actually launches (D16).
"""

from __future__ import annotations

import os

import pytest

LIVE_ENV_VAR = "ILAB_LIVE_TESTS"


def require_live() -> None:
    """Skip the calling test unless live runs are explicitly enabled."""
    if os.environ.get(LIVE_ENV_VAR) != "1":
        pytest.skip(f"live test — set {LIVE_ENV_VAR}=1 (spends tokens via azimo)")
