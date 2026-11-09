"""Experiments as data (D16): the ExperimentSpec — what to run — and the RunSpec — one matrix cell.

An experiment file asserts nothing and scores nothing: it describes the run
matrix (canaries × wins × seeds) and the model config, and hashes into the
``exp-<sha8>`` identity (``naming.py``). Judgment lives downstream (the judge,
then pluggable fitness over stored outcomes) and never in the spec — changing
the metric must not change the experiment's identity, so there is no fitness
field here (D4).

One matrix cell = one :class:`RunSpec`: self-contained and serializable (D12),
the Runner's currency (PR 4). It carries the CanaryPointer's binding
(pack/target) and never ground truth (D20).
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator

from illumina_lab.canaries.models import _kebab

#: azimo's model roles (ILLUMINA_MODEL_<ROLE>) — keep in sync with azimo's core/llm.py.
ROLES = ("detect", "decide", "plan", "build", "check", "assess")


class ExperimentError(Exception):
    """An experiment file is malformed — fail fast, naming the file."""


class ModelConfig(BaseModel):
    """Which models run the beam's agents: a default plus per-role overrides.

    Maps onto azimo's env resolution (``ILLUMINA_MODEL_<ROLE>`` →
    ``ILLUMINA_MODEL`` → built-in default): the runner stamps env per run, so
    model choice is a first-class experiment variable — an ablation is just
    more matrix cells. Empty ``default`` defers to azimo's default.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    default: str = ""
    roles: dict[str, str] = {}

    @field_validator("roles")
    @classmethod
    def _known_roles(cls, v: dict[str, str]) -> dict[str, str]:
        """Restrict role keys to azimo's role vocabulary."""
        unknown = sorted(set(v) - set(ROLES))
        if unknown:
            raise ValueError(f"unknown model roles {unknown}; known: {', '.join(ROLES)}")
        return v


class ExperimentSpec(BaseModel):
    """The experiment file: the run matrix plus model config. Execution only — no fitness (D4/D16)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    canaries: list[str] = Field(min_length=1)
    wins: list[str] = Field(min_length=1)
    seeds: int = Field(default=1, ge=1)
    models: ModelConfig = ModelConfig()

    @field_validator("name", mode="before")
    @classmethod
    def _name_kebab(cls, v: str) -> str:
        """Require a kebab-case name — it rides the execution label (exp-<sha8>-<name>-<date>-<n>)."""
        return _kebab(v)

    @field_validator("canaries", "wins")
    @classmethod
    def _kebab_lists(cls, v: list[str]) -> list[str]:
        """Require kebab-case canary and win ids — they become run-id components."""
        return [_kebab(x) for x in v]


class RunSpec(BaseModel):
    """One matrix cell: the Runner's self-contained currency (D12)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    run_id: str
    label: str
    canary_id: str
    pack: str
    target: str
    win: str
    seed: int = Field(ge=1)
    models: ModelConfig = ModelConfig()


def load_experiment(path: Path) -> ExperimentSpec:
    """Load one experiment file, ExperimentError naming the file on any failure."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ExperimentError(f"no experiment file at {path}") from None
    except json.JSONDecodeError as e:
        raise ExperimentError(f"{path}: malformed JSON: {e}") from e
    try:
        return ExperimentSpec(**data)
    except Exception as e:  # pydantic ValidationError — normalized to the lab's error type
        raise ExperimentError(f"{path}: invalid experiment: {e}") from e
