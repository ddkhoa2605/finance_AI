# Finance AI Planning Copilot

Finance Decision Intelligence platform for FP&A analysis.

## Current status

Phase 7 — Deterministic Scenario Engine completed

- Actual, synthetic OPEX, Budget, and Forecast pipelines are deterministic.
- Units forecasting benchmarks Seasonal Naive, Ridge, and XGBoost.
- Financial statements are reconstructed from drivers and validated before output.
- Controlled anomalies provide ground truth for later root-cause evaluation.
- Local what-if scenarios support Units, Price, Discount, Unit COGS, and OPEX levers.

## Stack

- Python
- FastAPI
- PostgreSQL
- pgvector
- Docker Compose

## Run

```bash
docker compose up -d --build
```

Run the data pipeline:

```bash
python scripts/02_build_actual.py
python scripts/03_generate_opex.py
python scripts/04_generate_budget.py
python scripts/05_generate_forecast.py
python scripts/06_generate_anomalies.py
python scripts/07_generate_scenarios.py
```
