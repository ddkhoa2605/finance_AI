# Financial Sample Data Profile

## 1. Dataset Overview

- Rows: 700
- Columns: 16
- Duplicate rows: 0

## 2. Schema

| column              | dtype          |   non_null |   null |   unique |
|:--------------------|:---------------|-----------:|-------:|---------:|
| Segment             | str            |        700 |      0 |        5 |
| Country             | str            |        700 |      0 |        5 |
| Product             | str            |        700 |      0 |        6 |
| Discount Band       | str            |        647 |     53 |        3 |
| Units Sold          | float64        |        700 |      0 |      510 |
| Manufacturing Price | int64          |        700 |      0 |        6 |
| Sale Price          | int64          |        700 |      0 |        7 |
| Gross Sales         | float64        |        700 |      0 |      550 |
| Discounts           | float64        |        700 |      0 |      515 |
| Sales               | float64        |        700 |      0 |      559 |
| COGS                | float64        |        700 |      0 |      545 |
| Profit              | float64        |        700 |      0 |      557 |
| Date                | datetime64[us] |        700 |      0 |       16 |
| Month Number        | int64          |        700 |      0 |       12 |
| Month Name          | str            |        700 |      0 |       12 |
| Year                | int64          |        700 |      0 |        2 |

## 3. Null Analysis

| column              |   null_count |   null_pct |
|:--------------------|-------------:|-----------:|
| Segment             |            0 |    0       |
| Country             |            0 |    0       |
| Product             |            0 |    0       |
| Discount Band       |           53 |    7.57143 |
| Units Sold          |            0 |    0       |
| Manufacturing Price |            0 |    0       |
| Sale Price          |            0 |    0       |
| Gross Sales         |            0 |    0       |
| Discounts           |            0 |    0       |
| Sales               |            0 |    0       |
| COGS                |            0 |    0       |
| Profit              |            0 |    0       |
| Date                |            0 |    0       |
| Month Number        |            0 |    0       |
| Month Name          |            0 |    0       |
| Year                |            0 |    0       |

## 4. Time Range

- Min date: 2013-09-01 00:00:00
- Max date: 2014-12-01 00:00:00
- Invalid dates: 0

## 5. Dimensions

### Country
- Cardinality: 5
- Values: Canada, France, Germany, Mexico, United States of America

### Product
- Cardinality: 6
- Values: Amarilla, Carretera, Montana, Paseo, VTT, Velo

### Segment
- Cardinality: 5
- Values: Channel Partners, Enterprise, Government, Midmarket, Small Business

### Discount Band
- Cardinality: 3
- Values: High, Low, Medium

## 6. Numeric Statistics

| column              |   count |        mean |           std |       min |      25% |      50% |       75% |             max |
|:--------------------|--------:|------------:|--------------:|----------:|---------:|---------:|----------:|----------------:|
| Units Sold          |     700 |   1608.29   |    867.428    |    200    |   905    |  1542.5  |   2229.12 |   4492.5        |
| Manufacturing Price |     700 |     96.4771 |    108.603    |      3    |     5    |    10    |    250    |    260          |
| Sale Price          |     700 |    118.429  |    136.776    |      7    |    12    |    20    |    300    |    350          |
| Gross Sales         |     700 | 182759      | 254262        |   1799    | 17391.8  | 37980    | 279025    |      1.2075e+06 |
| Discounts           |     700 |  13150.4    |  22962.9      |      0    |   800.32 |  2585.25 |  15956.3  | 149678          |
| Sales               |     700 | 169609      | 236726        |   1655.08 | 15928    | 35540.2  | 261078    |      1.1592e+06 |
| COGS                |     700 | 145475      | 203866        |    918    |  7490    | 22506.2  | 245608    | 950625          |
| Profit              |     700 |  24133.9    |  42760.6      | -40617.5  |  2805.96 |  9242.2  |  22662    | 262200          |
| Month Number        |     700 |      7.9    |      3.37732  |      1    |     5.75 |     9    |     10.25 |     12          |
| Year                |     700 |   2013.75   |      0.433322 |   2013    |  2013.75 |  2014    |   2014    |   2014          |

## 7. Negative Values

| column              |   negative_count |
|:--------------------|-----------------:|
| Units Sold          |                0 |
| Manufacturing Price |                0 |
| Sale Price          |                0 |
| Gross Sales         |                0 |
| Discounts           |                0 |
| Sales               |                0 |
| COGS                |                0 |
| Profit              |               58 |
| Month Number        |                0 |
| Year                |                0 |

## 8. Candidate Grain

- Columns: ['Date', 'Country', 'Segment', 'Product', 'Discount Band']
- Duplicate rows at candidate grain: 24
- Unique grain: False

## 9. Formula Validation

### Sales = Gross Sales - Discounts

```text
{'rows_checked': 700, 'rows_passed': 700, 'rows_failed': 0, 'max_abs_difference': 1.4551915228366852e-11, 'mean_abs_difference': 1.1043864235814128e-13, 'status': 'checked'}
```

### Profit = Sales - COGS

```text
{'rows_checked': 700, 'rows_passed': 700, 'rows_failed': 0, 'max_abs_difference': 7.275957614183426e-12, 'mean_abs_difference': 5.5544140715418114e-14, 'status': 'checked'}
```

### Gross Sales = Units Sold × Sale Price

```text
{'rows_checked': 700, 'rows_passed': 700, 'rows_failed': 0, 'max_abs_difference': 0.0, 'mean_abs_difference': 0.0, 'status': 'checked'}
```

## 10. Discount Band Values

| discount_band   |   row_count |
|:----------------|------------:|
| High            |         245 |
| Medium          |         242 |
| Low             |         160 |
| nan             |          53 |

Missing values are reported as-is; they are not mapped to `None`.

## 11. Discount Band Sanity Check

| Discount Band   |   avg_discounts |   total_discounts |   avg_gross_sales |
|:----------------|----------------:|------------------:|------------------:|
| High            |        21702.1  |       5.31703e+06 |            174243 |
| Low             |         5535.47 |  885676           |            221972 |
| Medium          |        12407.2  |       3.00255e+06 |            172657 |
| nan             |            0    |       0           |            149880 |

## 12. Country and Product Coverage

| Country                  | Product   |   row_count |
|:-------------------------|:----------|------------:|
| Canada                   | Amarilla  |          18 |
| Canada                   | Carretera |          20 |
| Canada                   | Montana   |          18 |
| Canada                   | Paseo     |          42 |
| Canada                   | VTT       |          22 |
| Canada                   | Velo      |          20 |
| France                   | Amarilla  |          18 |
| France                   | Carretera |          18 |
| France                   | Montana   |          20 |
| France                   | Paseo     |          40 |
| France                   | VTT       |          22 |
| France                   | Velo      |          22 |
| Germany                  | Amarilla  |          18 |
| Germany                  | Carretera |          20 |
| Germany                  | Montana   |          18 |
| Germany                  | Paseo     |          40 |
| Germany                  | VTT       |          22 |
| Germany                  | Velo      |          22 |
| Mexico                   | Amarilla  |          20 |
| Mexico                   | Carretera |          18 |
| Mexico                   | Montana   |          20 |
| Mexico                   | Paseo     |          40 |
| Mexico                   | VTT       |          20 |
| Mexico                   | Velo      |          22 |
| United States of America | Amarilla  |          20 |
| United States of America | Carretera |          17 |
| United States of America | Montana   |          17 |
| United States of America | Paseo     |          40 |
| United States of America | VTT       |          23 |
| United States of America | Velo      |          23 |

## 13. Monthly Coverage

| month   |   row_count |
|:--------|------------:|
| 2013-09 |          35 |
| 2013-10 |          70 |
| 2013-11 |          35 |
| 2013-12 |          35 |
| 2014-01 |          35 |
| 2014-02 |          35 |
| 2014-03 |          35 |
| 2014-04 |          35 |
| 2014-05 |          35 |
| 2014-06 |          70 |
| 2014-07 |          35 |
| 2014-08 |          35 |
| 2014-09 |          35 |
| 2014-10 |          70 |
| 2014-11 |          35 |
| 2014-12 |          70 |

Months with `row_count` equal to 0 are missing from the historical data.