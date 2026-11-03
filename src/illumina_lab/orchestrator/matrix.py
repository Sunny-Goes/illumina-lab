"""Matrix expansion: an ExperimentSpec becomes the list of RunSpecs (D5/D14).

Two steps, kept separate so parsing stays engine-free: ``validate_experiment``
fails fast on an unrunnable spec (unknown canary, engine-store drift, or a win
the pack's reward table doesn't carry) and ``expand`` mints one RunSpec per
(canary × win × seed) cell in deterministic order. Expansion resolves each
canary through the canary store — the pointer's pack/target fill the RunSpec;
ground truth never crosses (D20).
"""

from __future__ import annotations

from pathlib import Path

from illumina_lab.canaries.crosscheck import pack_win_ids, validate_binding
from illumina_lab.canaries.loader import load_canary
from illumina_lab.canaries.models import RegistryError
from illumina_lab.experiment import ExperimentError, ExperimentSpec, RunSpec
from illumina_lab.naming import run_id


def validate_experiment(spec: ExperimentSpec, *, store_root: Path | None = None, engine_store: Path | None = None) -> None:
    """Fail fast on an unrunnable spec, ExperimentError listing every problem found."""
    problems: list[str] = []
    for cid in spec.canaries:
        try:
            canary = load_canary(cid, store_root)
        except RegistryError as e:
            problems.append(str(e))
            continue
        try:
            validate_binding(canary, engine_store)
        except RegistryError as e:
            problems.append(str(e))
        win_ids = pack_win_ids(canary.pointer.pack, engine_store)
        for w in spec.wins:
            if w not in win_ids:
                problems.append(f"{cid}: win {w!r} is not a row of {canary.pointer.pack}'s win table")
    if problems:
        raise ExperimentError(f"experiment {spec.name!r} cannot run:\n- " + "\n- ".join(problems))


def expand(spec: ExperimentSpec, label: str, *, store_root: Path | None = None) -> list[RunSpec]:
    """Expand the spec into one RunSpec per (canary × win × seed), sorted for determinism."""
    cells = []
    for cid in sorted(spec.canaries):
        pointer = load_canary(cid, store_root).pointer
        for win in sorted(spec.wins):
            for seed in range(1, spec.seeds + 1):
                cells.append(
                    RunSpec(
                        run_id=run_id(label, cid, win, seed),
                        label=label,
                        canary_id=cid,
                        pack=pointer.pack,
                        target=pointer.target,
                        win=win,
                        seed=seed,
                        models=spec.models,
                    )
                )
    return cells
