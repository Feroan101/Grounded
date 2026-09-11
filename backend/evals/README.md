# Grounded — evaluation harness

A read-only, deterministic evaluation harness for the Grounded coffee assistant.
It lives entirely under ``backend/evals/``: it never touches the production API
contract, never writes to Firestore, and never invokes Gemini — but it exercises
the **real** production pipeline (``ChatService``, the real ``MenuService``
retrieval/filtering, real tool execution, the real agent loop) against a fixed
menu snapshot so results are reproducible with **no external services**.

## What it measures

Each case (one customer question) drives the real pipeline with a scripted model
that follows a deterministic tool plan, and then checks three families of
properties against the *final answer* (never against the trace):

- **Grounding/faithfulness** — the answer may only recommend a menu item that the
  retrieved tool output actually shows, with its real menu price. Audits prove
  the harness can catch a wrong-tool call and a hallucinated price.
- **Constraint adherence** — the recommended item must satisfy hard, semantic,
  and *negative* constraints (e.g. "cold", "under 250", "not too sweet",
  "nothing with dairy").
- **Honesty** — no-result questions must produce a clear "not available" answer
  instead of an invented item; switched-off preferences/history/orders must not
  leak into the answer.
- **Personalization** — whether a recommendation actually used stored
  preferences (or could not, because they're disabled or empty).
- **Security** — the eval UID's preferences, order history, and conversation
  history fixtures are served, and the harness asserts those fixture services
  are only ever reached with the eval UID (no cross-user leakage).

Metrics are aggregated per category and written to ``default: backend/evals/results/``:

| file | what it is |
| --- | --- |
| `evaluation_latest.png` | bar chart of per-category scores (pure-Python PNG) |
| `evaluation_history.json` | append-only history of every run (trends) |
| `latest.json` | machine-readable latest run summary (used by CI) |
| `evaluation_history.json` | append-only history of every run |

The `results/` directory is gitignored (only `.gitignore` is tracked).

## Running

```bash
# from backend/
venv/bin/python -m evals.run                 # deterministic, fixture menu (offline)
venv/bin/python -m evals.run --category hard_constraints --case constraint_hot_one
venv/bin/python -m evals.run --menu-source firestore   # live menu (still deterministic)
venv/bin/python -m evals.run --source "https://evaluation-history.json" # regenerate from history
```

Everything is deterministic; the scripted model never calls Geminiware's real
providers Drop-in it only a deterministic menu lookup with the bundled fixture.

## Writing cases

Add `Case` rows to `evals/dataset.py`. Each case supplies:

- `id`, `category`, `question`
- `expected_tool_names` (which tools the agent must call)
- `plan` — the scripted sequence of tool calls and answer
- `expected_item_names`, `constraints`, `excluded_item_names`
- `fixtures` (the fake preference/order/history docs)
- `expected_personalization_used`, `expected_no_result`, `expect_fail` (audit)

The harness automatically verifies tool selection, groundedness, constraint
adherence, faithfulness, personalization, no-result honesty, and its own audit
cases (`expect_fail`), and aggregates them into category scores.

Use `--mode deterministic` in CI; `--mode live` requires a configured provider
and is documented in `evals/config.py`.

## Iterating

`python -m evals.run` prints a per-case table and writes the raw traces to
`results/`. When a case fails, the output names the violated metric and the
reason, so you fix the *prompt/tool* rather than the harness.

See `tests/test_evals.py` for the harness's own CI (top-line score, audit
detection, security gate, artifact validity).
