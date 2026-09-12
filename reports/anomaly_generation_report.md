# Anomaly Generation Report

## Pipeline Result

- Status: passed
- Benchmark year: 2014
- Benchmark version: ACTUAL_WITH_EVENTS
- Events: 4
- Driver rows: 493
- Finance fact rows: 2,885
- Phase 5 snapshot: phase5-poc-complete-v1 (unchanged)

The benchmark is an isolated copy of authoritative Actual 2014. It does not retrain
the Phase 5 forecast and does not overwrite any file under `data/processed/`.

## Controlled Events

| event_id   | type          | period                   | scope                                              | operation     |   matched_rows | root_cause             |
|:-----------|:--------------|:-------------------------|:---------------------------------------------------|:--------------|---------------:|:-----------------------|
| EVT_001    | volume        | 2014-07-01 to 2014-09-01 | country=Mexico, product=Paseo                      | multiply 0.88 |              6 | volume_decline         |
| EVT_002    | unit_cogs     | 2014-10-01 to 2014-12-01 | country=Germany, product=VTT                       | multiply 1.08 |              4 | unit_cogs_increase     |
| EVT_003    | opex          | 2014-01-01 to 2014-12-01 | country=France, department=Marketing               | multiply 1.15 |             12 | marketing_overspend    |
| EVT_004    | discount_rate | 2014-04-01 to 2014-06-01 | country=United States of America, product=Amarilla | add 0.05      |              3 | discount_rate_increase |

Events are cumulative in the final benchmark. Event-level impacts below are measured
using one isolated event at a time against the same reconstructed baseline, which
keeps the ground-truth attribution unambiguous.

EVT_001 has a counterintuitive local EBITDA result: its Gross Profit decreases, but
the shared revenue-linked and country-allocated OPEX engine reduces Mexico OPEX by a
larger amount. The observed EBITDA increase is therefore recorded as ground truth,
not replaced with an assumed direction.

## Event Impacts

| event_id   | metric             |          before |           after |          delta |   delta_pct | expected_direction   | actual_direction   | direction_pass   |
|:-----------|:-------------------|----------------:|----------------:|---------------:|------------:|:---------------------|:-------------------|:-----------------|
| EVT_001    | average_sale_price |       34.272609 |       34.272609 |       0.000000 |    0.000000 | unchanged            | unchanged          | True             |
| EVT_001    | cogs               |   299378.000000 |   263452.640000 |  -35925.360000 |   -0.120000 | decrease             | decrease           | True             |
| EVT_001    | discount           |    11231.910000 |     9884.080800 |   -1347.829200 |   -0.120000 | decrease             | decrease           | True             |
| EVT_001    | discount_rate      |        0.030554 |        0.030554 |      -0.000000 |   -0.000000 | unchanged            | unchanged          | True             |
| EVT_001    | ebitda             |  -302388.710532 |  -299933.164862 |    2455.545670 |    0.008120 | increase             | increase           | True             |
| EVT_001    | gross_profit       |    56998.090000 |    50158.319200 |   -6839.770800 |   -0.120000 | decrease             | decrease           | True             |
| EVT_001    | gross_sales        |   367608.000000 |   323495.040000 |  -44112.960000 |   -0.120000 | decrease             | decrease           | True             |
| EVT_001    | revenue            |   356376.090000 |   313610.959200 |  -42765.130800 |   -0.120000 | decrease             | decrease           | True             |
| EVT_001    | unit_cogs          |       27.911430 |       27.911430 |      -0.000000 |   -0.000000 | unchanged            | unchanged          | True             |
| EVT_001    | units              |    10726.000000 |     9438.880000 |   -1287.120000 |   -0.120000 | decrease             | decrease           | True             |
| EVT_002    | average_sale_price |      166.594096 |      166.594096 |       0.000000 |    0.000000 | unchanged            | unchanged          | True             |
| EVT_002    | cogs               |   844520.000000 |   912081.600000 |   67561.600000 |    0.080000 | increase             | increase           | True             |
| EVT_002    | discount           |    37308.350000 |    37308.350000 |       0.000000 |    0.000000 | unchanged            | unchanged          | True             |
| EVT_002    | discount_rate      |        0.033055 |        0.033055 |       0.000000 |    0.000000 | unchanged            | unchanged          | True             |
| EVT_002    | ebitda             |  -382326.346856 |  -449887.946856 |  -67561.600000 |   -0.176712 | decrease             | decrease           | True             |
| EVT_002    | gross_profit       |   246846.650000 |   179285.050000 |  -67561.600000 |   -0.273699 | decrease             | decrease           | True             |
| EVT_002    | gross_sales        |  1128675.000000 |  1128675.000000 |       0.000000 |    0.000000 | unchanged            | unchanged          | True             |
| EVT_002    | revenue            |  1091366.650000 |  1091366.650000 |       0.000000 |    0.000000 | unchanged            | unchanged          | True             |
| EVT_002    | unit_cogs          |      124.652399 |      134.624590 |       9.972192 |    0.080000 | increase             | increase           | True             |
| EVT_002    | units              |     6775.000000 |     6775.000000 |       0.000000 |    0.000000 | unchanged            | unchanged          | True             |
| EVT_003    | ebitda             | -2021094.630652 | -2199812.500544 | -178717.869891 |   -0.088426 | decrease             | decrease           | True             |
| EVT_003    | gross_profit       |  2969688.610000 |  2969688.610000 |       0.000000 |    0.000000 | unchanged            | unchanged          | True             |
| EVT_003    | opex_marketing     |  1191452.465942 |  1370170.335834 |  178717.869891 |    0.150000 | increase             | increase           | True             |
| EVT_003    | opex_total         |  4990783.240652 |  5169501.110544 |  178717.869891 |    0.035810 | increase             | increase           | True             |
| EVT_003    | revenue            | 19221377.110000 | 19221377.110000 |       0.000000 |    0.000000 | unchanged            | unchanged          | True             |
| EVT_004    | average_sale_price |       47.287447 |       47.287447 |       0.000000 |    0.000000 | unchanged            | unchanged          | True             |
| EVT_004    | cogs               |   374494.000000 |   374494.000000 |       0.000000 |    0.000000 | unchanged            | unchanged          | True             |
| EVT_004    | discount           |    53449.120000 |    74695.370000 |   21246.250000 |    0.397504 | increase             | increase           | True             |
| EVT_004    | discount_rate      |        0.125785 |        0.175785 |       0.050000 |    0.397504 | increase             | increase           | True             |
| EVT_004    | ebitda             |  -712405.239123 |  -728455.559282 |  -16050.320159 |   -0.022530 | decrease             | decrease           | True             |
| EVT_004    | gross_profit       |    -3018.120000 |   -24264.370000 |  -21246.250000 |   -7.039564 | decrease             | decrease           | True             |
| EVT_004    | gross_sales        |   424925.000000 |   424925.000000 |       0.000000 |    0.000000 | unchanged            | unchanged          | True             |
| EVT_004    | revenue            |   371475.880000 |   350229.630000 |  -21246.250000 |   -0.057194 | decrease             | decrease           | True             |
| EVT_004    | unit_cogs          |       41.675273 |       41.675273 |       0.000000 |    0.000000 | unchanged            | unchanged          | True             |
| EVT_004    | units              |     8986.000000 |     8986.000000 |       0.000000 |    0.000000 | unchanged            | unchanged          | True             |

`delta_pct` is calculated as `(after - before) / abs(before)`. A blank value means
the baseline metric is zero. Discount event value `0.05` means five percentage
points, not a five-percent multiplier.

## Validation Checks

- phase5_authoritative_outputs_unchanged: passed
- event_ids_unique_and_config_valid: passed
- event_filters_match_nonzero_rows: passed
- direct_event_scopes_do_not_overlap: passed
- exact_event_operations: passed
- expected_financial_directions: passed
- baseline_reconstruction_matches_actual: passed
- driver_grain_unique_and_bounds_valid: passed
- gross_sales_reconciliation: passed
- revenue_reconciliation: passed
- cogs_reconciliation: passed
- gross_profit_reconciliation: passed
- opex_total_reconciliation: passed
- ebitda_reconciliation: passed
- derived_row_coverage: passed
- deterministic_rerun: passed
- row_order_independence: passed
- csv_round_trip: passed

## Lineage and Isolation

- Authoritative driver input: `data/processed/drivers.csv`
- Shared finance engine: `scripts/calculation/finance.py`
- Shared OPEX engine: `scripts/calculation/opex.py`
- Event configuration: `config/anomalies.yaml`
- Ground truth attribution: isolated event versus baseline
- Final benchmark semantics: all configured events applied cumulatively
- Phase 5 baseline SHA-256 checks: passed before and after generation

## Output Files

- `data/anomaly_benchmark/drivers_with_events.csv`: 493 rows
- `data/anomaly_benchmark/finance_fact_with_events.csv`: 2,885 rows
- `data/anomaly_benchmark/event_impacts.csv`: 35 rows
- `data/ground_truth/events.json`: 4 events
