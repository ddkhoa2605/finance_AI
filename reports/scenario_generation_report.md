# Scenario Generation Report

## Pipeline Result

- Status: passed
- Engine: LocalScenarioEngine
- Default baseline: FORECAST
- Scenarios generated: 4
- Scenario driver rows: 1,972
- Scenario finance rows: 11,540
- Scenario comparison rows: 64

Scenario is a deterministic management simulation, not a forecast or prediction.
Each scenario starts from canonical baseline drivers, leaves the baseline untouched,
reconstructs the five operating accounts, recalculates revenue-linked OPEX, applies
any explicit department OPEX lever, and finally recalculates OPEX Total and EBITDA.

For a Budget baseline, authoritative management-plan OPEX is preserved as the base;
the shared OPEX engine contributes only the incremental change caused by scenario
Revenue. This prevents an unrelated Budget-versus-synthetic-methodology variance.

## Scenario Impact Summary

| scenario_id   | name                               | baseline   | lever                 |   scope_driver_rows |   opex_rows |   revenue_impact |   gross_profit_impact |   opex_total_impact |   ebitda_impact |
|:--------------|:-----------------------------------|:-----------|:----------------------|--------------------:|------------:|-----------------:|----------------------:|--------------------:|----------------:|
| SCN_001       | Canada Paseo Q1 Price Increase     | FORECAST   | Price +3.0%           |                   6 |           0 |         21649.69 |              21649.69 |             2092.82 |        19556.87 |
| SCN_002       | Germany VTT Q2 Volume Downside     | FORECAST   | Units -10.0%          |                   5 |           0 |        -23079.51 |              -3732.50 |            -2657.12 |        -1075.38 |
| SCN_003       | USA Q3 Unit COGS Inflation         | FORECAST   | Unit COGS +5.0%       |                  21 |           0 |             0.00 |            -154025.58 |                0.00 |      -154025.58 |
| SCN_004       | France FY Marketing OPEX Reduction | FORECAST   | Marketing OPEX -10.0% |                  99 |          12 |             0.00 |                  0.00 |          -115806.46 |       115806.46 |

Financial impacts use company-wide totals within the scenario period so that
cross-country fixed-OPEX allocation effects are not omitted. Driver comparisons use
the direct request scope.

## Driver Comparison

| scenario_id   | metric             |   baseline_value |   scenario_value |      impact |   impact_pct |
|:--------------|:-------------------|-----------------:|-----------------:|------------:|-------------:|
| SCN_001       | average_sale_price |        80.835608 |        83.260676 |    2.425068 |     0.030000 |
| SCN_001       | discount_rate      |         0.084330 |         0.084330 |    0.000000 |     0.000000 |
| SCN_001       | unit_cogs          |        67.049041 |        67.049041 |    0.000000 |     0.000000 |
| SCN_001       | units              |      9749.646484 |      9749.646484 |    0.000000 |     0.000000 |
| SCN_002       | average_sale_price |        32.055119 |        32.055119 |    0.000000 |     0.000000 |
| SCN_002       | discount_rate      |         0.031388 |         0.031388 |    0.000000 |     0.000000 |
| SCN_002       | unit_cogs          |        26.027617 |        26.027617 |   -0.000000 |    -0.000000 |
| SCN_002       | units              |      7433.261597 |      6689.935437 | -743.326160 |    -0.100000 |
| SCN_003       | average_sale_price |       117.197953 |       117.197953 |    0.000000 |     0.000000 |
| SCN_003       | discount_rate      |         0.090348 |         0.090348 |    0.000000 |     0.000000 |
| SCN_003       | unit_cogs          |        92.910009 |        97.555509 |    4.645500 |     0.050000 |
| SCN_003       | units              |     33155.863892 |     33155.863892 |    0.000000 |     0.000000 |
| SCN_004       | average_sale_price |       117.945640 |       117.945640 |    0.000000 |     0.000000 |
| SCN_004       | discount_rate      |         0.067794 |         0.067794 |    0.000000 |     0.000000 |
| SCN_004       | unit_cogs          |        94.086291 |        94.086291 |    0.000000 |     0.000000 |
| SCN_004       | units              |    163538.790405 |    163538.790405 |    0.000000 |     0.000000 |

For percentage levers, the request value is multiplicative change (for example
`0.03` means +3%). `discount_rate_change_pp` is additive percentage points. No price
elasticity or other implicit driver relationship is assumed in V1.

## Validation Checks

- scenario_engine_interface_and_local_implementation: passed
- actual_budget_forecast_baselines_selectable_and_reconciled: passed
- baseline_and_anomaly_artifacts_preserved: passed
- scenario_ids_unique: passed
- scope_nonzero_and_isolated: passed
- explicit_driver_lever_magnitude: passed
- no_implicit_elasticity: passed
- driver_grain_unique_and_bounds_valid: passed
- finance_reconstruction: passed
- five_department_opex_coverage: passed
- department_opex_lever_magnitude: passed
- opex_total_reconciliation: passed
- ebitda_reconciliation: passed
- scenario_vs_baseline_comparison: passed
- sample_scenario_causal_directions: passed
- derived_row_coverage: passed
- deterministic_rerun: passed
- row_order_independence: passed
- csv_round_trip: passed

## Isolation and Lineage

- Supported baselines validated: ACTUAL, BUDGET, FORECAST
- Default forward-looking baseline: FORECAST
- Anomaly benchmark is never used as a Scenario Engine baseline
- Phase 2-6 protected artifacts are hash-identical before and after generation
- Shared finance engine: `scripts/calculation/finance.py`
- Shared OPEX engine: `scripts/calculation/opex.py`
- Structured scenario assumptions: `config/scenarios.yaml`
- Registry contains request, config, baseline and output hashes; no runtime timestamp

## Output Files

- `data/scenarios/scenario_drivers.csv`: 1,972 rows
- `data/scenarios/scenario_finance.csv`: 11,540 rows
- `data/scenarios/scenario_comparison.csv`: 64 rows
- `data/scenarios/scenario_registry.json`: 4 scenarios
