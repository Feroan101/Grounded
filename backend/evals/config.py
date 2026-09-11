"""Evaluation harness configuration.

The harness lives entirely under ``backend/evals/`` and never touches the
production app. Only two things are environmental:

- the menu data source (real Firestore or the bundled fixture snapshot), and
- the run mode (deterministic scripted agent vs. live Gemini).
"""
from __future__ import annotations

import os
from pathlib import Path

EVALS_DIR = Path(__file__).resolve().parent
RESULTS_DIR = EVALS_DIR / "results"
FIXTURES_DIR = EVALS_DIR / "fixtures"
MENU_FIXTURE_PATH = FIXTURES_DIR / "menu_fixture.json"

EVAL_VERSION = "1"

# The single UID every deterministic case runs as. Isolation is proven by
# checking that user-scoped services are only ever called with this UID.
DEFAULT_UID = "eval-user"

DEFAULT_MODE = os.environ.get("EVALS_MODE", "deterministic")
DEFAULT_MENU_SOURCE = os.environ.get("EVALS_MENU_SOURCE", "firestore")

# Deterministic currency rates (target per 1 source), so numeric assertions
# are exact and reproducible without a network call.
FIXED_CURRENCY_RATES = {
    ("INR", "USD"): "0.012",
    ("USD", "INR"): "83.0",
    ("EUR", "GBP"): "0.85",
    ("INR", "GBP"): "0.0095",
}