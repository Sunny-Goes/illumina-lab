"""The ``illumina-lab`` console script (D17).

Subcommands dispatch to their own argparse mains, so each owns its flags and
``<subcommand> --help`` output:

- ``replay``         — replay a persisted PoC workspace on a scratch copy, optionally patched;
- ``counterfactual`` — replay the same PoC on the vulnerable and the fixed target and print
                       the attribution verdict (confirmed / not-specific / not-a-valid-exploit);
- ``attribute``      — judge every PoC of an archived run against a canary's fix-carrying
                       bugs and write ``attribution.json`` next to the run's ``run.json``.
"""

from __future__ import annotations

import sys

from illumina_lab.judge import attribute, counterfactual, replay

_COMMANDS = {"replay": replay.main, "counterfactual": counterfactual.main, "attribute": attribute.main}


def main(argv: list[str] | None = None) -> int:
    """Dispatch to a subcommand; print usage on no/unknown input."""
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] in _COMMANDS:
        return _COMMANDS[argv[0]](argv[1:])
    print(__doc__)
    return 0 if argv and argv[0] in ("-h", "--help") else 2


if __name__ == "__main__":
    sys.exit(main())
