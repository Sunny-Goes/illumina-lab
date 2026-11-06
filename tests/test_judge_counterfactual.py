"""The counterfactual verdict table and patch resolution — offline, no forge."""

import json

import pytest

from illumina_lab.judge.counterfactual import resolve_patch, verdict


@pytest.mark.parametrize(
    ("vulnerable", "fixed", "expected"),
    [
        ("win", "fail", "confirmed"),
        ("win", "win", "not-specific"),
        ("fail", "win", "not-a-valid-exploit"),  # the inverted case: fails on buggy, passes on fixed
        ("fail", "fail", "not-a-valid-exploit"),
        ("error", "fail", "not-a-valid-exploit"),
        ("win", "error", "error"),
        ("win", "build-error", "patch-incompatible"),  # the patch broke the build — nothing learned
        ("build-error", "win", "error"),  # the archived evidence itself does not compile
        ("build-error", "fail", "error"),
    ],
)
def test_verdict(vulnerable, fixed, expected):
    assert verdict(vulnerable, fixed) == expected


def test_resolve_patch(tmp_path):
    (tmp_path / "fixes").mkdir()
    (tmp_path / "bugs.json").write_text(json.dumps([
        {"id": "bug-a", "fix": "fixes/bug-a.patch"},
        {"id": "bug-b"},
    ]))
    assert resolve_patch(tmp_path, "bug-a") == tmp_path / "fixes/bug-a.patch"
    with pytest.raises(ValueError, match="no fix patch"):
        resolve_patch(tmp_path, "bug-b")
    with pytest.raises(ValueError, match="not found"):
        resolve_patch(tmp_path, "bug-c")
