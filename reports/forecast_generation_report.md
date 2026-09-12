# Forecast Generation Report

## Pipeline Result

- Status: passed
- Forecast horizon: January–December 2015
- Training history: September 2013–December 2014
- ML target: Units only
- Champion: xgboost
- Simplicity tolerance: 0.500% WAPE points
- Forecast driver rows: 493
- Forecast finance rows: 2,885
- Combined finance fact rows: 9,630

## Dataset Limitation

The Microsoft Financial Sample contains only 16 months of sparse series history. ML results are a proof of concept, not a production-grade 12-month accuracy claim. Missing observations are not treated as zero sales.

## One-step Walk-forward Evaluation

| model          |        mae |        rmse |     wape |    smape |   macro_wape |   median_series_wape |   prediction_coverage |
|:---------------|-----------:|------------:|---------:|---------:|-------------:|---------------------:|----------------------:|
| seasonal_naive | 980.256684 | 1241.122663 | 0.571502 | 0.601898 |     0.746764 |             0.579162 |              1.000000 |
| ridge          | 749.971784 |  949.692469 | 0.437243 | 0.459089 |     0.567134 |             0.386661 |              1.000000 |
| xgboost        | 749.790722 |  958.709660 | 0.437137 | 0.464290 |     0.539270 |             0.380439 |              1.000000 |

## Recursive Stability Evaluation

| model          |        mae |        rmse |     wape |    smape |   macro_wape |   median_series_wape |   prediction_coverage |
|:---------------|-----------:|------------:|---------:|---------:|-------------:|---------------------:|----------------------:|
| seasonal_naive | 970.695187 | 1218.041450 | 0.565927 | 0.607809 |     0.752702 |             0.580610 |              1.000000 |
| ridge          | 818.451242 |  981.885410 | 0.477167 | 0.481343 |     0.722113 |             0.417245 |              1.000000 |
| xgboost        | 743.452754 |  963.602698 | 0.433442 | 0.463494 |     0.562170 |             0.385047 |              1.000000 |

## Recursive WAPE by Country

| model          | country                  |     wape |   prediction_coverage |
|:---------------|:-------------------------|---------:|----------------------:|
| seasonal_naive | Canada                   | 0.499470 |              1.000000 |
| seasonal_naive | France                   | 0.616456 |              1.000000 |
| seasonal_naive | Germany                  | 0.600886 |              1.000000 |
| seasonal_naive | Mexico                   | 0.472000 |              1.000000 |
| seasonal_naive | United States of America | 0.648279 |              1.000000 |
| ridge          | Canada                   | 0.380279 |              1.000000 |
| ridge          | France                   | 0.506749 |              1.000000 |
| ridge          | Germany                  | 0.533651 |              1.000000 |
| ridge          | Mexico                   | 0.475183 |              1.000000 |
| ridge          | United States of America | 0.512669 |              1.000000 |
| xgboost        | Canada                   | 0.386296 |              1.000000 |
| xgboost        | France                   | 0.432731 |              1.000000 |
| xgboost        | Germany                  | 0.450614 |              1.000000 |
| xgboost        | Mexico                   | 0.464152 |              1.000000 |
| xgboost        | United States of America | 0.445971 |              1.000000 |

Champion selection uses recursive pooled WAPE. A more complex model must improve WAPE by at least the configured simplicity tolerance.

## Champion Decisions

| incumbent      | candidate   |   recursive_wape_improvement |   required_improvement | candidate_selected   |
|:---------------|:------------|-----------------------------:|-----------------------:|:---------------------|
| seasonal_naive | ridge       |                     0.088760 |               0.005000 | True                 |
| ridge          | xgboost     |                     0.043725 |               0.005000 | True                 |

## Driver Rule Fallback Usage

| metric             | fallback_level                      |   row_count |
|:-------------------|:------------------------------------|------------:|
| average_sale_price | same_grain_same_month_previous_year |         493 |
| discount_rate      | same_grain_same_month_previous_year |         493 |
| unit_cogs          | same_grain_same_month_previous_year |         493 |

ASP, Unit COGS, and Discount Rate use same-grain/same-month prior year first, followed by deterministic historical fallbacks. Unit COGS is distinct from Average Manufacturing Price.

## Forecast vs Budget

| account      |   forecast_2015 |    budget_2015 |       variance |   variance_pct |
|:-------------|----------------:|---------------:|---------------:|---------------:|
| REVENUE      |   84818796.1549 |  97457438.2823 | -12638642.1274 |        -0.1297 |
| GROSS_PROFIT |   11668843.1910 |  14149210.9181 |  -2480367.7271 |        -0.1753 |
| OPEX_TOTAL   |   22883227.8512 |  24864946.7053 |  -1981718.8542 |        -0.0797 |
| EBITDA       |  -11214384.6602 | -10715735.7872 |   -498648.8730 |        -0.0465 |

Budget is comparison context only. It is not a model feature, target, or champion-selection input.

## Validation Checks

- forecast_horizon_12_months: passed
- actual_derived_scaffold: passed
- budget_coverage_only: passed
- one_step_and_recursive_backtests: passed
- candidate_prediction_coverage_100_percent: passed
- leakage_safe_preprocessing: passed
- simplicity_aware_champion: passed
- canonical_driver_grain_unique: passed
- driver_bounds: passed
- operating_reconciliation: passed
- fixed_allocation_reconciliation: passed
- opex_and_ebitda_reconciliation: passed
- derived_row_coverage: passed
- actual_and_budget_preserved: passed
- forecast_distinct_from_budget: passed
- keyed_opex_noise_order_independent: passed
- deterministic_rerun: passed
- shuffled_input_order: passed
- csv_round_trip: passed

## Lineage

- Prediction input hash: `8749f2b687dbd82566b2416a6248049d93ab6106eb32e0c89690573b5912dcd8`
- Evaluation context hash: `93ac4605e9fe2015c74af2cf107079e69951ec7a435e7777095b5118cd413c29`
- Operating Forecast source: `forecast_engine_v1`
- Forecast OPEX source: `synthetic_opex_v1_forecast`
- Forecast EBITDA source: `derived_forecast_v1`

## Output Files

- `forecast_drivers.csv`: 493 rows
- `forecast.csv`: 2,885 rows
- `forecast_model_evaluation.csv`: 45 rows
- `finance_fact.csv`: 9,630 rows
- `models/forecast/model_registry.json`: final-refit model registry