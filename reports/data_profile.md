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

## 8. Candidate Business Context / Grain Check

Candidate dimensions: Date × Country × Segment × Product × Discount Band
- Repeated candidate-context groups: 12
- Rows in repeated groups: 24
- Rows beyond the first observation in repeated groups: 12
- Largest group size: 2
- Candidate context is unique: False

### Repeated Candidate Context Groups

| Date                | Country                  | Segment    | Product   | Discount Band   |   row_count |
|:--------------------|:-------------------------|:-----------|:----------|:----------------|------------:|
| 2013-10-01 00:00:00 | Canada                   | Government | Paseo     | Medium          |           2 |
| 2013-10-01 00:00:00 | France                   | Government | Amarilla  | Medium          |           2 |
| 2013-10-01 00:00:00 | France                   | Government | Montana   | Medium          |           2 |
| 2013-10-01 00:00:00 | Mexico                   | Government | Amarilla  | High            |           2 |
| 2013-10-01 00:00:00 | Mexico                   | Government | Montana   | High            |           2 |
| 2014-06-01 00:00:00 | Canada                   | Government | Amarilla  | Medium          |           2 |
| 2014-06-01 00:00:00 | United States of America | Government | Amarilla  | Medium          |           2 |
| 2014-06-01 00:00:00 | United States of America | Government | Velo      | Medium          |           2 |
| 2014-10-01 00:00:00 | Canada                   | Government | Montana   | High            |           2 |
| 2014-12-01 00:00:00 | Germany                  | Government | VTT       | High            |           2 |
| 2014-12-01 00:00:00 | Mexico                   | Government | Carretera | Medium          |           2 |
| 2014-12-01 00:00:00 | United States of America | Government | VTT       | Medium          |           2 |

### Source Rows in Repeated Candidate Context Groups

| Date                | Country                  | Segment    | Product   | Discount Band   |   Units Sold |   Manufacturing Price |   Sale Price |   Gross Sales |   Discounts |   COGS |    Profit |
|:--------------------|:-------------------------|:-----------|:----------|:----------------|-------------:|----------------------:|-------------:|--------------:|------------:|-------:|----------:|
| 2013-10-01 00:00:00 | Canada                   | Government | Paseo     | Medium          |         1228 |                    10 |          350 |        429800 |    21490    | 319280 |  89030    |
| 2013-10-01 00:00:00 | Canada                   | Government | Paseo     | Medium          |         1389 |                    10 |           20 |         27780 |     1389    |  13890 |  12501    |
| 2013-10-01 00:00:00 | France                   | Government | Amarilla  | Medium          |         1403 |                   260 |            7 |          9821 |      589.26 |   7015 |   2216.74 |
| 2013-10-01 00:00:00 | France                   | Government | Amarilla  | Medium          |         2076 |                   260 |          350 |        726600 |    43596    | 539760 | 143244    |
| 2013-10-01 00:00:00 | France                   | Government | Montana   | Medium          |         1403 |                     5 |            7 |          9821 |      589.26 |   7015 |   2216.74 |
| 2013-10-01 00:00:00 | France                   | Government | Montana   | Medium          |         1757 |                     5 |           20 |         35140 |     2108.4  |  17570 |  15461.6  |
| 2013-10-01 00:00:00 | Mexico                   | Government | Amarilla  | High            |          344 |                   260 |          350 |        120400 |    13244    |  89440 |  17716    |
| 2013-10-01 00:00:00 | Mexico                   | Government | Amarilla  | High            |         1727 |                   260 |            7 |         12089 |     1692.46 |   8635 |   1761.54 |
| 2013-10-01 00:00:00 | Mexico                   | Government | Montana   | High            |         1715 |                     5 |           20 |         34300 |     4116    |  17150 |  13034    |
| 2013-10-01 00:00:00 | Mexico                   | Government | Montana   | High            |         1727 |                     5 |            7 |         12089 |     1692.46 |   8635 |   1761.54 |
| 2014-06-01 00:00:00 | Canada                   | Government | Amarilla  | Medium          |         1135 |                   260 |            7 |          7945 |      556.15 |   5675 |   1713.85 |
| 2014-06-01 00:00:00 | Canada                   | Government | Amarilla  | Medium          |          708 |                   260 |           20 |         14160 |     1132.8  |   7080 |   5947.2  |
| 2014-06-01 00:00:00 | United States of America | Government | Amarilla  | Medium          |         1282 |                   260 |           20 |         25640 |     2051.2  |  12820 |  10768.8  |
| 2014-06-01 00:00:00 | United States of America | Government | Amarilla  | Medium          |         2907 |                   260 |            7 |         20349 |     1627.92 |  14535 |   4186.08 |
| 2014-06-01 00:00:00 | United States of America | Government | Velo      | Medium          |          602 |                   120 |          350 |        210700 |    10535    | 156520 |  43645    |
| 2014-06-01 00:00:00 | United States of America | Government | Velo      | Medium          |         2907 |                   120 |            7 |         20349 |     1627.92 |  14535 |   4186.08 |
| 2014-10-01 00:00:00 | Canada                   | Government | Montana   | High            |         2734 |                     5 |            7 |         19138 |     2296.56 |  13670 |   3171.44 |
| 2014-10-01 00:00:00 | Canada                   | Government | Montana   | High            |         1249 |                     5 |           20 |         24980 |     3247.4  |  12490 |   9242.6  |
| 2014-12-01 00:00:00 | Germany                  | Government | VTT       | High            |         1531 |                   250 |           20 |         30620 |     3674.4  |  15310 |  11635.6  |
| 2014-12-01 00:00:00 | Germany                  | Government | VTT       | High            |          280 |                   250 |            7 |          1960 |      274.4  |   1400 |    285.6  |
| 2014-12-01 00:00:00 | Mexico                   | Government | Carretera | Medium          |         1362 |                     3 |          350 |        476700 |    38136    | 354120 |  84444    |
| 2014-12-01 00:00:00 | Mexico                   | Government | Carretera | Medium          |          521 |                     3 |            7 |          3647 |      328.23 |   2605 |    713.77 |
| 2014-12-01 00:00:00 | United States of America | Government | VTT       | Medium          |         2663 |                   250 |           20 |         53260 |     2663    |  26630 |  23967    |
| 2014-12-01 00:00:00 | United States of America | Government | VTT       | Medium          |          570 |                   250 |            7 |          3990 |      199.5  |   2850 |    940.5  |

### Interpretation

The candidate dimensions describe the business context of a source sales observation, but they do not form a natural unique key for the source rows.

The source does not provide an explicit Transaction ID, Order ID, Invoice ID, or equivalent record identifier. Therefore, this profiling step does not conclude that the candidate dimensions are the true source grain.

Rows in repeated candidate-context groups are retained as-is. No deduplication, aggregation, or cleaning is performed during Phase 1.

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