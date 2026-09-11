# Actual Build Report

## Pipeline Result

- Source: `microsoft_financial_sample`
- Version: `ACTUAL`
- Currency: `USD`
- Status: passed

## Validation Checks

- source_row_id_unique: passed
- finance_fact_grain_unique: passed
- drivers_grain_unique: passed
- sales_reconciliation: passed
- gross_profit_reconciliation: passed
- source_to_fact_reconciliation: passed
- source_to_driver_reconciliation: passed
- revenue_by_product_drill_down: passed
- gross_profit_by_country_drill_down: passed
- csv_round_trip_validation: passed
- csv_round_trip_drill_down_validation: passed

## Output Files

- `actual_staging.csv`: 700 rows, 21 columns, 120,008 bytes
- `actual.csv`: 3,300 rows, 9 columns, 323,453 bytes
- `drivers.csv`: 660 rows, 11 columns, 69,844 bytes

## Drill-down Checks

### Revenue by Product

| product   |      amount |
|:----------|------------:|
| Paseo     | 3.30111e+07 |
| VTT       | 2.05119e+07 |
| Velo      | 1.82501e+07 |
| Amarilla  | 1.77471e+07 |
| Montana   | 1.53908e+07 |
| Carretera | 1.38153e+07 |

### Gross Profit by Country

| country                  |      amount |
|:-------------------------|------------:|
| France                   | 3.78102e+06 |
| Germany                  | 3.68039e+06 |
| Canada                   | 3.52923e+06 |
| United States of America | 2.99554e+06 |
| Mexico                   | 2.90752e+06 |

Both drill-down tables reconcile to the corresponding account total.

## Canonical Grain

- `actual.csv`: Month × Country × Product × Segment × Account × Version × Currency × Source
- `drivers.csv`: Month × Country × Product × Segment × Version × Currency × Source

`actual_staging.csv` retains every raw source observation and its `source_row_id` for auditability. `actual.csv` aggregates those observations; no source rows are deleted.

Missing Discount Band values are retained as null in staging; no null-to-None mapping is applied.