# Budget Generation Report

## Pipeline Result

- Status: passed
- Base year: 2014
- Budget year: 2015
- Planning method: driver-based deterministic budget
- Budget driver rows: 493
- Budget finance rows: 2,885
- Combined finance fact rows: 6,745

## Planning Assumptions

- Units growth: 3.00%
- Price growth: 2.50%
- Discount-rate change: 0.00% points
- COGS inflation: 2.00%

| scenario   |   period | dimension_type   | dimension_value   | assumption_name      |   assumption_value |
|:-----------|---------:|:-----------------|:------------------|:---------------------|-------------------:|
| BUDGET     |     2015 | GLOBAL           | ALL               | units_growth         |              0.03  |
| BUDGET     |     2015 | GLOBAL           | ALL               | price_growth         |              0.025 |
| BUDGET     |     2015 | GLOBAL           | ALL               | discount_rate_change |              0     |
| BUDGET     |     2015 | GLOBAL           | ALL               | cogs_inflation       |              0.02  |
| BUDGET     |     2015 | DEPARTMENT       | Sales             | opex_growth          |              0.04  |
| BUDGET     |     2015 | DEPARTMENT       | Marketing         | opex_growth          |              0.05  |
| BUDGET     |     2015 | DEPARTMENT       | Operations        | opex_growth          |              0.03  |
| BUDGET     |     2015 | DEPARTMENT       | R&D               | opex_growth          |              0.06  |
| BUDGET     |     2015 | DEPARTMENT       | Finance & G&A     | opex_growth          |              0.04  |

## Validation Checks

- driver_formulas: passed
- revenue_reconciliation: passed
- gross_profit_reconciliation: passed
- opex_growth_assumptions: passed
- opex_total_reconciliation: passed
- ebitda_reconciliation: passed
- canonical_grains_unique: passed
- date_alignment_2014_to_2015: passed
- no_accidental_row_loss: passed
- actual_2014_preserved: passed
- assumptions_stored_separately: passed
- budget_version: passed
- deterministic_rebuild: passed
- csv_round_trip_and_formulas: passed

## Actual 2014 vs Budget 2015

| account      |   actual_2014 |   budget_2015 |   variance |   variance_pct |
|:-------------|--------------:|--------------:|-----------:|---------------:|
| REVENUE      |   92311094.75 |   97457438.28 | 5146343.53 |         0.0557 |
| COGS         |   79295857.00 |   83308227.36 | 4012370.36 |         0.0506 |
| GROSS_PROFIT |   13015237.75 |   14149210.92 | 1133973.17 |         0.0871 |
| OPEX_TOTAL   |   23799570.80 |   24864946.71 | 1065375.91 |         0.0448 |
| EBITDA       |  -10784333.05 |  -10715735.79 |   68597.26 |        -0.0064 |

## Output Files

- `budget_drivers.csv`: 493 rows
- `budget_assumptions.csv`: 9 rows
- `budget.csv`: 2,885 rows
- `finance_fact.csv`: 6,745 rows

`finance_fact.csv` is rebuilt from authoritative Actual files plus Budget on every run; Budget rows are never appended in place.