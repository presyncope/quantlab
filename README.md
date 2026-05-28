# Quantlab Phase 1 Local MVP

Quantlab implements the Phase 1 Korean domestic-market premarket research loop from `.references/phase1.md` as a **local dashboard and SQLite workflow**.

It is a research and review aid. Signals are human review prompts, not trading instructions.

## Scope

Included:
- market brief
- sector/theme map
- A/B/C/Excluded watchlist
- stock research cards
- A/B-only generated alert logging
- separate user decision, optional manual execution, and postmarket review records
- summary rollups by grade, bias, signal/action/review quality, and failure reason
- deterministic demo data

Excluded:
- live broker API / Korea Investment Open API credentials
- real orders, account, balance, or position access
- automated advice phrasing or price-objective instructions
- production deployment and multi-user auth
- complex backtests and optimization

## Setup

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[test]'
```

## Run the local dashboard

```bash
streamlit run quantlab/app.py
```

The app stores data in `.quantlab/phase1.sqlite3` by default. Use **Reset and seed demo data** to create the complete sample daily loop for `2026-05-28`.

## Smoke start

```bash
streamlit run quantlab/app.py --server.headless true --server.port 8501
```

For automated smoke checks, start Streamlit in the background, wait for the `Local URL`/server-ready log, then terminate the process. Failure is a crash, credential prompt, import error, or missing server-ready log.

## Tests

```bash
pytest
```

The test suite covers:
- SQLite schema creation and seed/reset
- full daily-loop retrieval
- A/B-only generated alert eligibility
- C/Excluded manual non-alert notes
- separate signal/decision/execution/review records
- summary rollups
- English/Korean review-language guardrails
- absence of live broker/API/order runtime paths

## Design notes

- `quantlab/domain.py` owns vocabulary and generated alert eligibility.
- `quantlab/storage.py` uses stdlib `sqlite3` with stable IDs and relationships.
- `quantlab/workflow.py` owns business rules and summaries outside the UI.
- `quantlab/app.py` is a replaceable Streamlit adapter.
- `quantlab/ports.py` documents disabled future adapter seams; Phase 1 runtime stays local/offline.
