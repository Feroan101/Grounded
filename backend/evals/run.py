"""Evaluation runner CLI.

    python -m evals.run [options]

Run from the ``backend/`` directory so the ``evals`` and ``app`` packages are
on ``sys.path``.  All files written to ``evals/results/`` are gitignored.
"""
from __future__ import annotations

import argparse

from evals.runner import run


def main() -> None:
    parser = argparse.ArgumentParser(description="Grounded evaluation harness")
    parser.add_argument("--category", action="append", help="Category filter (repeatable).")
    parser.add_argument("--case", action="append", help="Specific case id (repeatable).")
    parser.add_argument("--mode", default="deterministic", help="Deterministic or live.")
    parser.add_argument("--menu-source", default="firestore", help="firestore or fixture.")
    args = parser.parse_args()
    run(
        include_categories=args.category,
        include_cases=args.case,
        mode=args.mode,
        menu_source=args.menu_source,
    )


if __name__ == "__main__":
    main()