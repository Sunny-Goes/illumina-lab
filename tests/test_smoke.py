"""The foundation tripwire: the lab package imports, and the engine under test imports from its own venv.

A broken submodule pin or a missing ``uv sync`` in ``vendor/azimo`` is caught
here, before any real work: the azimo check skips with a clear message on a
fresh clone (venv absent) and fails loud when the venv exists but the import
fails — or resolves to some illumina outside the submodule.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

AZIMO = Path(__file__).resolve().parents[1] / "vendor" / "azimo"
AZIMO_PYTHON = AZIMO / ".venv" / "bin" / "python"


def test_lab_package_imports():
    import illumina_lab

    assert illumina_lab.__doc__


def test_azimo_importable_from_its_venv():
    if not AZIMO_PYTHON.is_file():
        pytest.skip("azimo venv missing — set up the engine env: cd vendor/azimo && uv sync")
    proc = subprocess.run(
        [str(AZIMO_PYTHON), "-c", "import illumina, pathlib; print(pathlib.Path(illumina.__file__).resolve())"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, f"azimo import failed:\n{proc.stderr[-800:]}"
    assert str(AZIMO) in proc.stdout, f"illumina imported from outside the submodule: {proc.stdout}"
