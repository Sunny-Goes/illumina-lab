"""Canary model tests — the pointer/bug/canary contract, offline over synthetic data."""

import pytest
from pydantic import ValidationError

from illumina_lab.canaries import BugEntry, BugSite, Canary, CanaryPointer

SHA = "a" * 40


def test_pointer_parses_minimal():
    p = CanaryPointer(id="honk-all-canaries", pack="honk", target="all-canaries", snapshot_sha=SHA)
    assert p.links == [] and p.notes == ""


def test_pointer_requires_kebab_ids():
    with pytest.raises(ValidationError, match="kebab"):
        CanaryPointer(id="Honk_Canary", pack="honk", target="t", snapshot_sha=SHA)


def test_pointer_requires_full_sha():
    with pytest.raises(ValidationError, match="40-hex"):
        CanaryPointer(id="c", pack="honk", target="t", snapshot_sha="abc123")


def test_pointer_forbids_a_bugs_field():
    # the leak tripwire: ground truth lives in the sibling bugs.json — a merged file must fail loud
    with pytest.raises(ValidationError):
        CanaryPointer(id="c", pack="honk", target="t", snapshot_sha=SHA, bugs=[])


def test_canary_merges_pointer_and_bugs(tmp_path):
    p = CanaryPointer(id="c", pack="honk", target="t", snapshot_sha=SHA)
    c = Canary(pointer=p, bugs=[BugEntry(id="b1", files=["A.sol"])], root=tmp_path)
    assert c.pointer.pack == "honk"
    assert c.bugs[0].id == "b1"
    assert c.root == tmp_path


def test_bug_requires_a_file():
    with pytest.raises(ValidationError):
        BugEntry(id="b", files=[])


def test_bug_severity_vocabulary():
    BugEntry(id="b", files=["utils.sol"], severity="critical")
    with pytest.raises(ValidationError, match="severity"):
        BugEntry(id="b", files=["utils.sol"], severity="severe")


def test_bug_counterfactual_ground_truth():
    b = BugEntry(
        id="b",
        files=["utils.sol"],
        fix="fixes/b.patch",
        reference_poc="reference/b",
        sites=[{"file": "utils.sol", "lines": [[166, 178]], "kind": "context", "function": "ecMul"}],
    )
    assert b.fix == "fixes/b.patch"
    assert b.reference_poc == "reference/b"
    assert b.sites == [BugSite(file="utils.sol", lines=[(166, 178)], kind="context", function="ecMul")]


def test_bug_counterfactual_fields_default_to_absent():
    b = BugEntry(id="b", files=["A.sol"])
    assert b.fix == "" and b.reference_poc == "" and b.sites == []


def test_bug_forbids_unknown_fields():
    with pytest.raises(ValidationError):
        BugEntry(id="b", files=["A.sol"], bogus=1)


def test_site_forbids_unknown_fields():
    with pytest.raises(ValidationError):
        BugSite(file="A.sol", bogus=1)


def test_pointer_serialization_never_carries_ground_truth():
    # tripwire: if ground-truth fields are ever added to the execution currency, this fails
    dumped = CanaryPointer(id="c", pack="honk", target="t", snapshot_sha=SHA).model_dump()
    for key in ("bugs", "files", "severity", "fix", "sites", "reference_poc"):
        assert key not in dumped


def test_pointer_target_subdir_is_safe_relative_path():
    p = CanaryPointer(id="c", pack="honk", target="t", snapshot_sha=SHA, target_subdir="packages/contracts")
    assert p.target_subdir == "packages/contracts"
    assert CanaryPointer(id="c", pack="honk", target="t", snapshot_sha=SHA).target_subdir == ""
    for bad in ("/abs/path", "packages/../secrets"):
        with pytest.raises(ValidationError, match="target_subdir"):
            CanaryPointer(id="c", pack="honk", target="t", snapshot_sha=SHA, target_subdir=bad)
