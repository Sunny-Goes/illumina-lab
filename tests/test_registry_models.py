"""Registry model tests — the canary/bug contract, offline over synthetic data."""

import pytest
from pydantic import ValidationError

from illumina_lab.registry import BugEntry, Canary

SHA = "a" * 40


def test_canary_parses_minimal():
    c = Canary(id="honk-precompile-success-unchecked", pack="honk", target="precompile-success-unchecked", snapshot_sha=SHA)
    assert c.links == [] and c.notes == ""


def test_canary_requires_kebab_ids():
    with pytest.raises(ValidationError, match="kebab"):
        Canary(id="Honk_Canary", pack="honk", target="t", snapshot_sha=SHA)


def test_canary_requires_full_sha():
    with pytest.raises(ValidationError, match="40-hex"):
        Canary(id="c", pack="honk", target="t", snapshot_sha="abc123")


def test_canary_forbids_a_bugs_field():
    # the ground truth lives in the sibling bugs.json — a merged file must fail loud
    with pytest.raises(ValidationError):
        Canary(id="c", pack="honk", target="t", snapshot_sha=SHA, bugs=[])


def test_bug_requires_a_file():
    with pytest.raises(ValidationError):
        BugEntry(id="b", files=[])


def test_bug_severity_vocabulary():
    BugEntry(id="b", files=["utils.sol"], severity="critical")
    with pytest.raises(ValidationError, match="severity"):
        BugEntry(id="b", files=["utils.sol"], severity="severe")
