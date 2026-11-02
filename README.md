# illumina-lab

An evaluation and experimentation harness for [illumina](https://github.com/Sunny-Goes/azimo) — the playground for the autoresearch loop.

illumina audits smart-contract codebases by casting **beams** (one run = one pack × one win condition). illumina-lab answers: *how well does it do that, and does a change make it better?* It runs beams against **canaries** — codebases pinned at a commit where known, real bugs (from published audits and Immunefi programs) are provably present — harvests each run into a facts layer, and scores experiments with pluggable fitness functions. The long-run goal is an autoresearch loop: an external optimizer proposes illumina changes, the lab measures them.

## The loop

```
registry ─► forge ─► orchestrator ─► harvest ─► judge ─► fitness
(canaries)  (packs)  (run matrix:    (facts)    (ground  (pluggable:
                      canary × win              truth     strict recall →
                      × seed)                   join)     cost, exploration)
                                                          ▲
                    optimizer (separate repo) ────────────┘
                    reads facts, patches illumina, re-measures
```

## Core vocabulary

- **canary** — a codebase pinned at a snapshot commit with known, documented bugs (the ground truth).
- **beam** — one illumina run: one pack × one win condition.
- **run matrix** — canary × win × seed; the lab's unit of experiment.
- **facts** — append-only per-run measurements (findings, coverage, tokens, cost, …). Fixed schema.
- **fitness** — a pluggable pure function over facts. Minimal fitness: strict recall on planted bugs.
- **folds** — train/eval/test split over canaries, always by codebase, never by bug.

## Key decisions

The full register with rationale lives in [docs/decisions.md](docs/decisions.md). Highlights:

- Historical bugs from published audits over seeded bugs; snapshots are validated so all ground-truth bugs provably coexist at the pinned commit.
- Facts and fitness are separate layers — adding a metric never requires re-running experiments.
- Detection-level judgment first (a finding or PoCInput at the seeded site); PoC-confirmed track later.
- Ground truth is structurally unreachable by the detector: docs live outside tool reach, the snapshot commit predates the docs commit, and a CI leak check proves it.
- azimo runs pinned as a submodule, in its own locked venv, one subprocess per beam.
- Observability improvements go upstream into azimo ([#172](https://github.com/Sunny-Goes/azimo/issues/172)), not into lab workarounds.
- The optimizer is a separate repo behind a three-part contract (experiment API, workspace + editable surface, fitness); [harness2](https://github.com/Sunny-Goes/harness2) is a candidate citizen.

## Development setup

```bash
git clone --recurse-submodules https://github.com/Sunny-Goes/illumina-lab.git
```

azimo (the engine under test) is a submodule at `vendor/azimo`: **a pinned pointer, not a copy**. This repo commits only a gitlink (azimo's URL + a recorded commit SHA); azimo's files never enter this repo's history — `--recurse-submodules` fetches them from azimo's own repo at exactly that commit. Moving the pin is `git -C vendor/azimo checkout <sha-or-branch>` plus committing the new gitlink. Currently pinned to the head of azimo PR [#171](https://github.com/Sunny-Goes/azimo/pull/171) (`drop-poc-templates`); it moves to `main` once that lands, and later to autoresearch branches as the optimizer produces them.

## Status & roadmap

Template stage — the repo is being set up. See [docs/roadmap.md](docs/roadmap.md) for full milestone definitions.

| milestone | goal |
| --- | --- |
| v0 | walking skeleton on honk: 1 canary × 1 win × 1 seed → facts + strict recall |
| v1 | real canaries + judge: training-set repo, plether curation, forge, failure taxonomy |
| v2 | scale + stage isolation: N canaries, full win tables, replay loops, remote runner |
| v3 | autoresearch boundary: experiment API, acceptance gate, optimizer integration |

## Related repos

- [Sunny-Goes/azimo](https://github.com/Sunny-Goes/azimo) — illumina, the engine under test (pinned submodule).
- [Sunny-Goes/illumina-training-set](https://github.com/Sunny-Goes/illumina-training-set) — the curated canaries (pinned submodule, from v1).
