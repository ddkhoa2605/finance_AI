# Finance AI Planning Copilot

Finance Decision Intelligence platform for FP&A analysis.

## Current status

Phase 5 — ML-assisted Forecasting Engine completed

- Actual, synthetic OPEX, Budget, and Forecast pipelines are deterministic.
- Units forecasting benchmarks Seasonal Naive, Ridge, and XGBoost.
- Financial statements are reconstructed from drivers and validated before output.

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
```
