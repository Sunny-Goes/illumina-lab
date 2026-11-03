"""The orchestrator — turns experiments into runs and keeps the books.

``matrix`` expands an ExperimentSpec into the run matrix and validates it
against the stores; ``ledger`` (PR 3, item 4) records every run event; the
``runner`` pool (PR 4) executes the cells. Folds — train/eval/test by codebase
namespace (D21) — arrive with v2.
"""
