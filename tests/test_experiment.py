"""Experiment spec tests — parsing, defaults, vocabulary, loading errors. Offline."""

import json

import pytest
from pydantic import ValidationError

from illumina_lab.experiment import (
    ExperimentError,
    ExperimentSpec,
    ModelConfig,
    RunSpec,
    load_experiment,
)


def test_minimal_spec_defaults():
    s = ExperimentSpec(name="smoke", canaries=["honk-all-canaries"], wins=["griefing"])
    assert s.seeds == 1
    assert s.models == ModelConfig()


def test_spec_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        ExperimentSpec(name="s", canaries=["c"], wins=["w"], fitness="strict-recall")


def test_name_must_be_kebab():
    with pytest.raises(ValidationError, match="kebab"):
        ExperimentSpec(name="Honk Smoke", canaries=["c"], wins=["w"])


def test_ids_must_be_kebab():
    with pytest.raises(ValidationError, match="kebab"):
        ExperimentSpec(name="s", canaries=["honk_all"], wins=["w"])


def test_seeds_at_least_one():
    with pytest.raises(ValidationError):
        ExperimentSpec(name="s", canaries=["c"], wins=["w"], seeds=0)


def test_model_roles_vocabulary():
    ModelConfig(default="anthropic:claude-sonnet-4-6", roles={"detect": "openai:mimo-v2.5-pro"})
    with pytest.raises(ValidationError, match="unknown model roles"):
        ModelConfig(roles={"detector": "oops"})


def test_runspec_shape():
    r = RunSpec(run_id="exp-x-y-1-c-w-s1", label="exp-x-y-1", canary_id="c", pack="honk", target="t", win="w", seed=1)
    assert r.models == ModelConfig()


def test_load_experiment_roundtrip(tmp_path):
    p = tmp_path / "exp.json"
    p.write_text(json.dumps({"name": "smoke", "canaries": ["honk-all-canaries"], "wins": ["griefing"], "seeds": 2}))
    s = load_experiment(p)
    assert s.name == "smoke" and s.seeds == 2


def test_load_experiment_missing_file(tmp_path):
    with pytest.raises(ExperimentError, match="no experiment file"):
        load_experiment(tmp_path / "nope.json")


def test_load_experiment_malformed_json(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("{ nope")
    with pytest.raises(ExperimentError, match="malformed JSON"):
        load_experiment(p)


def test_load_experiment_invalid_spec_named(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text(json.dumps({"name": "s"}))
    with pytest.raises(ExperimentError, match="invalid experiment"):
        load_experiment(p)
