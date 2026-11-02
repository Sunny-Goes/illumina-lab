"""The canary registry — the code that defines, reads, and validates the ground-truth store.

The data lives in the training-set repo (``vendor/illumina-training-set``), one
directory per canary; this package is the contract (``models``) and the
reader/validator (``loader``). The engine under test never sees any of it (D8).
"""

from illumina_lab.registry.models import (
    SEVERITIES,
    BugEntry,
    Canary,
    CanaryPointer,
    RegistryError,
)

__all__ = ["SEVERITIES", "BugEntry", "Canary", "CanaryPointer", "RegistryError"]
