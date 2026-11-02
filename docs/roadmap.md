# Roadmap

Four milestones. Each has a goal, a scope, and an exit criterion that is checked, not vibes.

## v0 — Walking skeleton (honk)

**Goal.** One command runs the run matrix (1 canary × 1 win × 1 seed) through azimo and emits facts plus a recall score.

**Scope.** Repo skeleton; azimo as pinned submodule; canary registry entry schema with honk fixture entries; `RunSpec` schema and run ledger (JSONL); the local runner (subprocess-per-beam, per-run env, run-id minting, logs); harvest (run folder + final state → `facts.jsonl`); judge v0 (ground-truth join → per-bug caught/missed, with the coverage gate); the fitness plugin interface with strict recall; the `illumina-lab run` CLI; experiment-spec hashing.

**Exit.** `illumina-lab run <experiment>` works end-to-end on a honk canary: ledger, facts, score. A rerun of the same spec dedupes. Every run records azimo SHA and target SHA.

PR decomposition: [plans/v0.md](plans/v0.md).

## v1 — Real canaries + judge

**Goal.** The first real canary is curated end-to-end and the judgment gains structure.

**Scope.** `illumina-training-set` repo populated: plether fork curated (snapshot predates docs, ground truth from published audits only); registry validators (hunk-presence, SHA-reachability, leak check) green in CI; the forge generates packs from the registry into `ILLUMINA_STORE`; graded outcomes + failure taxonomy (never-read / no-hypothesis / dismissed / poc-failed); second codebase in the matrix; seeds > 1.

**Exit.** Two codebases run through the matrix with repetitions; taxonomy is reported per run; validators gate the registry in CI.

## v2 — Scale + stage isolation

**Goal.** N canaries, full win tables, statistical reporting, cheap iteration loops.

**Scope.** Multi-win sweeps; per-run recall + caught@k; decider-replay iteration (PoC replay when [azimo#172](https://github.com/Sunny-Goes/azimo/issues/172) lands); `RemoteRunner`; tokens and cost in facts; train/eval/test splits by codebase, stratified by bug class.

**Exit.** A scoreboard over N canaries × wins × seeds; a decider-side change re-evaluated via replay without full detector runs.

## v3 — Autoresearch boundary

**Goal.** The optimizer contract goes live.

**Scope.** Experiment API stabilized; editable-surface manifest for azimo; fitness registry; eval-fold acceptance gate (improvement beyond run-to-run noise, no regression); the autoresearch repo's report agent consumes lab facts.

**Exit.** An externally proposed patch → eval fold run → fitness delta → accept/reject, entirely through the lab API. The test fold is touched on milestones only.
