# Decisions register

The decisions behind illumina-lab, numbered and dated, with the why. New decisions append; superseded ones are marked, never deleted.

## D1 — Historical bugs over seeded bugs

Canaries are real bugs from published audits and Immunefi programs, not seeded bugs. Real bugs carry real exploit logic, real severity, and a real fix commit to diff against. The seeded honk canaries (`Sunny-Goes/aztec-packages` fork) remain as the development target — zero curation cost, already judged by azimo's live canary test.

## D2 — Snapshot validity is mechanically proven, not trusted

A canary pins a commit at which **all** its ground-truth bugs provably coexist: for each bug, the pre-fix hunk of the fix commit's diff must appear verbatim at the snapshot. This is enforced by a registry validator (hunk-presence check), not by manual curation trust. A bug introduced *after* the snapshot (e.g. by an earlier fix) invalidates the snapshot choice.

## D3 — GitHub-centric fetch in v1

azimo's target loader assumes GitHub (repo slug → clone; per-file fallback via `raw.githubusercontent.com`). Forks under the org guarantee pin durability; upstream repos are allowed with a SHA-reachability validator that tells us when a pin must be forked. Arbitrary git hosts become an upstream patch if ever needed.

## D4 — Facts and fitness are separate layers

The lab harvests a fixed, append-only **facts** schema per run (findings, coverage, tool calls, LLM calls, tokens, cost, durations, models, run identity) — generously, including data no current metric uses. **Fitness** functions are pure, pluggable `facts → score` functions, registered by name and selected per experiment. Minimal fitness: strict recall on planted bugs. Consequence: new metrics never require re-running experiments.

## D5 — Run matrix = canary × win × seed, grown in that order

One beam is one pack × one win condition. The matrix adds seeds (repetitions — the pipeline is nondeterministic even at temperature 0). Rollout order: single run first, then multiple wins per canary, then seeds, then scale. Statistics (per-run recall, caught@k) before multi-repo scaling: without repetitions no signal is distinguishable from noise.

## D6 — Detection-level judgment first

A bug counts as found when the pipeline flags the seeded site (a constructed PoCInput or a non-dismissed finding at the location) — the same bar azimo's live canary test uses. PoC-confirmed judgment is a later track: it needs docker, a Foundry-buildable repo, and slashes measured recall. Graded outcomes (confirmed > poc_input > finding at location > finding in file > nothing) refine the v0 binary.

## D7 — Generic pack banks, per-codebase target manifests

Pack knowledge banks (win conditions, invariants, mechanisms) are generic across canaries, so the lab measures engine generalization rather than per-codebase authoring effort. Win tables are lifted from Immunefi scope pages (impact lists with criticality). Per-codebase data is limited to the target manifest (repo, SHA, in-scope files) plus registry metadata. azimo is expected to remove `invariants.json`; the forge invests accordingly.

## D8 — Ground truth is structurally unreachable by the detector

The detector's world is the in-scope sources plus the `tool_root` sandbox. Hygiene rules: methodology docs and `bugs.json` live outside every `sparse` path; the pinned snapshot commit *predates* the docs commit (the fetched tree contains no docs at all, and stays byte-identical to upstream); pack/manifest naming never telegraphs the bug into a prompt; a CI leak check greps the resolved `tool_root` for bug ids, fix SHAs, and marker words.

## D9 — Subprocess-per-beam isolation; azimo pinned and untouched

Each beam runs as its own OS process with its own env dict (`ILLUMINA_STORE`, `ILLUMINA_CACHE`, `ILLUMINA_<PACK>_TARGET`, `ILLUMINA_MODEL*`, `LANGSMITH_PROJECT`, `ILLUMINA_RUN_LABEL`). azimo is a pinned submodule using its own locked venv (`uv.lock`) — the engine under test is never contaminated by lab dependencies. Runs are `--local`/in-process only: the dev server cannot receive per-run env.

## D10 — Naming: spec hash, execution label, minted run ids

An experiment **spec** (canary set, wins, seeds, azimo SHA, store snapshot, models, fitness config) hashes to `exp-<sha12>` — same spec, same id, so reruns dedupe and reproducibility is checkable. One **execution** of a spec is `<exp>-<yyyymmdd>-<n>`, used as `ILLUMINA_RUN_LABEL` and `LANGSMITH_PROJECT`. Each beam cell's `run_id` is lab-minted (`<label>-<canary>-<win>-s<k>`, kebab-safe — it becomes a directory name) and passed as invoke input, which azimo's `ingest` honors.

## D11 — Observability goes upstream

illumina owns run truth; the lab owns experiment truth. Missing run-side primitives (CLI state dump, complete `run.json` with `poc_inputs` payloads, PoC replay entry point, the `ILLUMINA_HONK_REPLAY` hardcode) are filed upstream as [azimo#172](https://github.com/Sunny-Goes/azimo/issues/172) (milestone M2). The lab keeps only thin glue: a driver that calls `run_graph` and serializes the result.

## D12 — Runner abstraction, local first

A `Runner` protocol: `submit(RunSpec) → handle`, `wait(handle) → artifacts`. `LocalRunner` is a subprocess pool. `RemoteRunner` ships self-contained RunSpecs to a provider and pulls back run-folder tarballs; LangSmith centralizes traces regardless of where a run executed, so token harvesting is identical locally and remotely. illumina itself needs no GPU (models are API calls); self-hosted models plug in via the OpenAI-compatible endpoint override azimo already supports.

## D13 — The optimizer is a separate repo behind a contract

The lab exposes exactly three things: an **experiment API** (submit run matrix → facts), a **workspace + editable-surface manifest** (an azimo checkout and what may be edited), and a **fitness function**. The autoresearch repo owns the report agent (reads lab facts + the illumina codebase, writes the diagnostic narrative) and the updater agent (proposes patches). The deterministic failure taxonomy (never-read / no-hypothesis / dismissed / poc-failed) stays lab-side because it needs the ground-truth join — which also makes leak control a lab-side policy decision. harness2 is a candidate citizen behind this boundary, not a dependency.

## D14 — Schemas are N-agnostic from day one

The registry, run matrix, ledger, and facts schema never special-case one codebase. Rollout is purely registry growth: 1 codebase → 2 → N.

## D15 — Storage: one seam module, local files first, DB-shaped records

All lab persistence (ledger, facts, artifact paths) flows through a single workspace module — no scattered file access, but no storage abstraction ceremony either. Ledger and facts are flat, join-keyed JSONL records (`run_id` joins everything) that map 1:1 to table rows, so a DuckDB/SQLite/Postgres backend is a one-module swap later. Run artifacts (evidence trees, transcripts) stay files under any backend; a DB would hold metadata only.

## D16 — Experiments are data, tests are code

An experiment file is a declarative spec (canaries × wins × seeds × models × fitness selection), committed and hashed into the `exp-<sha12>` id — it asserts nothing by itself. The pytest suite verifies the lab's own code. The live-gated acceptance test consumes an experiment and asserts run *validity* (the coverage gate: the hunt actually happened), never that a bug was caught — caught/missed is the metric, read off the scoreboard, not a CI assertion.

## D17 — The console script is `illumina-lab`

Explicit over terse (`lab` would collide): `illumina-lab = illumina_lab.cli:main`, mirroring azimo's `illumina = illumina.cli:main`.

## D18 — The lab compares executors, not just illumina versions

## D18 — The lab compares executors, not just illumina versions

The Runner protocol and the facts/judge/fitness pipeline are executor-agnostic. A baseline agent — a vanilla prompted agent, or an off-the-shelf coding agent via harness2's substrates — is a second driver behind the same Runner seam, run against the same canaries, harvested into the same facts schema, joined to the same ground truth, scored by the same fitness. That yields the "illumina vs a normal agent" scoreboard: the baseline every illumina improvement claim is measured against. Pinned external baselines live under `vendor/` like azimo.

## D19 — Canary data lives in the training-set from day one

No in-lab fixtures: the lab's first canaries (the four seeded honk snapshots) were authored directly in `illumina-training-set`, pinned as `vendor/illumina-training-set`. The format is validated against its final home immediately, ground truth is version-pinned (every experiment records which training-set SHA judged it), and v1 has no migration. Lab unit tests use synthetic tmp_path stores; integration tests use the submodule.

## D20 — The leak boundary is a type boundary

Execution stages are typed to accept only `CanaryPointer` (id/pack/target/snapshot_sha) — a type with no ground-truth fields — so "ground truth never reaches the detector" (D8) is enforced by the shapes, not by discipline. Only the judge receives a full `Canary` (pointer + bugs). The runner builds its subprocess env from a pointer, so no code path can serialize the answer key into a run.

## D21 — Folds split by codebase namespace

The training-set groups snapshots under `canaries/<codebase>/`, so one codebase may carry several snapshots (different commits, different coexisting bug subsets). Train/eval/test splits therefore assign whole namespaces to folds, never individual snapshots or bugs — two plether snapshots in different folds would leak codebase-specific tuning into the test fold.
