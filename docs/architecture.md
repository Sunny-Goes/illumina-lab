# Architecture (skeleton)

Component shapes and data formats as agreed. Everything here is a v0 design target, not yet implemented — the decisions behind each are in [decisions.md](decisions.md) (referenced as D*n*).

## Components

```
canaries/             the answer key: canary models, loader, engine-store cross-check
                      (data lives in illumina-training-set; D14, D19, D20)
illumina_interface.py where the engine lives: checkout, pack store, venv python (D9)
forge/                canary pointers → azimo pack store (pack.json, win table, target
                      manifests; D7; v1)
orchestrator/         run matrix (canary × win × seed; D5), folds (D21), Runner pool (D12), ledger
harvest/              run folder + final state → facts (D4)
judge/                facts × ground truth → per-bug outcomes + failure taxonomy (D6)
fitness/              pluggable pure functions over facts, registered by name (D4)
```

The optimizer is **not** a component — it is a separate repo behind the contract in D13.

## Data formats (to be pinned down in v0)

- **Canary entry** — `canaries/<codebase>/<snapshot>/` in the training-set: `canary.json`
  (the `CanaryPointer`: id, pack, target, snapshot_sha) + `bugs.json` (`BugEntry` rows:
  files, severity, win, source). Validated per D2/D3/D8 and cross-checked against the
  engine's store.
- **RunSpec** — one matrix cell: `{ run_id, label, canary_id, pack, target, win, seed, models }`, self-contained and serializable (D12).
- **Ledger** — append-only JSONL, one row per run *event* (`submitted`/`running`/`finished`/`failed`): `{ts, event, run_id, label, spec, cell: {canary, win, seed}, …}`. A run's state is its latest event; dedupe keys on (spec hash, canary, win, seed) since run ids embed the execution label (D10).
- **Facts** — append-only `facts.jsonl`, one `FactsRow` per run: identity (run_id, label, spec hash, cell), pins (azimo + training-set SHAs from the driver's `provenance.json`), target commit, findings + by-status counts, poc inputs/runs, aggregated coverage (files read, tool calls, LLM calls, probes, errored), resolved models per role, duration. Sources: state dump + runspec + provenance + azimo's run.json + the ledger. Harvested idempotently per run_id; facts are a re-derivable view, never the truth (D4, D15).

## Naming (D10)

- experiment spec hash: `exp-<sha12>`
- execution label: `exp-<sha12>-<yyyymmdd>-<n>` (→ `ILLUMINA_RUN_LABEL`, `LANGSMITH_PROJECT`)
- beam run id: `<label>-<canary>-<win>-s<k>` (passed as invoke input)

## Seams into azimo

- Runs: in-process driver calling `illumina.cli.run_graph`, one subprocess per beam (D9).
- Results: the returned final state + `run.json` + the evidence folder tree (until azimo#172 lands).
- Replays: `--replay` for the decider seam (generic env var after the #172 buglet fix); PoC replay after #172.
