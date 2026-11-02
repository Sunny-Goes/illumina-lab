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
