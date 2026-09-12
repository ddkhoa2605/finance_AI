# Finance AI Planning Copilot — `plan.md`

> Mục tiêu: xây dựng một Finance AI Platform có thể hỏi đáp dữ liệu tài chính, phân tích Actual vs Budget/Forecast, tìm driver/root cause, chạy what-if scenario, truy xuất Knowledge Base và sẵn sàng tích hợp Anaplan qua adapter.
>
> Chiến lược: **không xây lại toàn bộ platform từ đầu**. Tận dụng các thành phần open-source cho semantic layer, agent orchestration, document parsing và Anaplan integration; tập trung phần nghiên cứu/cải thiện vào **Finance AI reasoning, semantic resolution, numerical validation, driver analysis, scenario recommendation và evaluation**.

---

## 1. Kết luận về dataset

### 1.1 Dataset chính nên dùng

**Microsoft Financial Sample.xlsx** làm nguồn `Actual` ban đầu.

Nguồn chính thức:

- Documentation: https://learn.microsoft.com/en-us/power-bi/create-reports/sample-financial-download
- Direct Excel download:
  https://download.microsoft.com/download/1/4/E/14EDED28-6C58-4055-A65C-23B4DA81C4DE/Financial%20Sample.xlsx

Dataset này phù hợp cho MVP vì có các trường kiểu:

- Segment
- Country/Region
- Product
- Discount Band
- Units Sold
- Manufacturing Price
- Sale Price
- Gross Sales
- Discounts
- Sales
- COGS
- Profit
- Date / Month / Year

Nó cho phép làm ngay:

- Revenue analysis
- COGS analysis
- Gross Profit
- Product analysis
- Country/Region analysis
- Segment analysis
- Volume / Price / Discount driver analysis
- Time-series analysis

### 1.2 Vì sao không dùng SimFin làm dataset chính?

SimFin rất tốt cho:

- Financial statements thật
- Income Statement
- Balance Sheet
- Cash Flow
- Historical company fundamentals
- External company benchmarking

Nguồn:

- https://www.simfin.com/en/fundamental-data-download/

Nhưng SimFin không lý tưởng cho core FP&A demo vì dữ liệu public chủ yếu ở cấp:

```text
Company × Reporting Period × Financial Statement
```

Trong khi project cần:

```text
Time
× Region
× Product
× Department
× Scenario
× Version
× Metric
```

Ngoài ra Budget/Forecast nội bộ của công ty không phải dữ liệu public.

**Kết luận:** dùng SimFin ở Phase mở rộng để thêm chức năng:

```text
Internal Plan vs External Company/Industry Benchmark
```

### 1.3 Dataset scale-up

Khi MVP đã chạy tốt, chuyển hoặc bổ sung:

**Microsoft Contoso Retail Data Warehouse**

Nguồn:

- https://www.microsoft.com/en-us/download/details.aspx?id=18279
- https://github.com/microsoft/sql-server-samples/tree/master/samples/databases/contoso-data-warehouse

Ưu điểm:

- Dữ liệu lớn hơn
- Rich dimensions
- Product / customer / geography / channel
- Data warehouse structure thực tế hơn
- Phù hợp test NL2SQL và performance

Không nên bắt đầu ngay bằng Contoso vì sẽ tăng đáng kể thời gian data engineering.

---

# 2. Triết lý dataset cho project

Không tìm một dataset duy nhất chứa hoàn hảo:

```text
Actual
Budget
Forecast
Scenario
Product
Region
Department
Financial Statement
Operational Drivers
Policies
```

Public dataset gần như không có đầy đủ các lớp này.

Thay vào đó xây một **controlled FP&A benchmark dataset**:

```text
Microsoft Financial Sample
        │
        ▼
     ACTUALS
        │
        ├──────────────┐
        ▼              ▼
Generate Budget    Generate OPEX
        │              │
        ▼              ▼
Generate Forecast  Finance Summary
        │              │
        └──────┬───────┘
               ▼
      Scenario Assumptions
               │
               ▼
       Deterministic Engine
               │
               ▼
       Ground-truth Results
```

Điểm quan trọng:

> Budget, Forecast, OPEX và Scenario phải được sinh bằng code deterministic với `random_seed` cố định.

Không dùng LLM để tự sinh các con số này.

Lý do:

1. Reproducible.
2. Có ground truth.
3. Có thể unit test.
4. Có thể đánh giá numerical accuracy.
5. Có thể biết chính xác AI phân tích đúng hay sai.

---

# 3. Business case giả lập

Tạo một doanh nghiệp giả:

```text
Company: Contoso Global Retail
Industry: Consumer / Retail
Currency: USD
Fiscal Calendar: Calendar Year
```

Các dimensions ban đầu:

```text
Time
Country
Product
Segment
Department
Version
Account
```

### Version

```text
Actual
Budget
Forecast
```

Sau này:

```text
Scenario_Base
Scenario_Price_Increase
Scenario_Volume_Recovery
Scenario_Cost_Reduction
```

### Departments

Tạo synthetic:

```text
Sales
Marketing
Operations
R&D
Finance & G&A
```

### Finance hierarchy

```text
Revenue
│
├── Gross Sales
└── Discounts

Net Revenue
│
└── COGS
    │
    ▼
Gross Profit
    │
    └── OPEX
        ├── Sales Expense
        ├── Marketing Expense
        ├── Operations Expense
        ├── R&D Expense
        └── G&A Expense

EBITDA
```

---

# 4. Target questions hệ thống phải trả lời

Trước khi code, xác định benchmark questions.

## Level 1 — Lookup

```text
What was Vietnam revenue in Q2 2026?

What was Germany gross profit last month?

What is the FY2026 revenue forecast?
```

## Level 2 — Comparison

```text
How does Q3 revenue compare with budget?

What is Actual vs Forecast EBITDA YTD?

Which regions are below plan?
```

## Level 3 — Drill-down

```text
Which products caused the revenue shortfall?

Which department has the largest OPEX overrun?

Which country contributes most to gross profit?
```

## Level 4 — Root cause

```text
Why is gross margin below budget?

Why did Product A revenue decline?

Why is EBITDA forecast below plan?
```

## Level 5 — Knowledge

```text
How does the company define Gross Margin?

What is the approval policy for forecast changes?

When should Finance refresh the rolling forecast?
```

## Level 6 — Scenario

```text
What happens to EBITDA if price increases 3%?

What if volume falls 2% and COGS rises 1%?

How much cost reduction is required to close the EBITDA gap?
```

## Level 7 — Recommendation

```text
What actions can close the EBITDA gap with the least revenue risk?

Should we prioritize price increase or OPEX reduction?

Which lever gives the highest EBITDA improvement?
```

---

# 5. Repository structure

```text
finance-ai-copilot/
│
├── README.md
├── plan.md
├── .env.example
├── docker-compose.yml
│
├── data/
│   ├── raw/
│   │   └── Financial Sample.xlsx
│   │
│   ├── processed/
│   │   ├── actual.csv
│   │   ├── budget.csv
│   │   ├── forecast.csv
│   │   ├── opex.csv
│   │   ├── finance_fact.csv
│   │   └── drivers.csv
│   │
│   └── kb/
│       ├── finance_metric_dictionary.md
│       ├── budget_policy.md
│       ├── forecast_policy.md
│       ├── scenario_policy.md
│       └── company_context.md
│
├── scripts/
│   ├── 01_profile_source.py
│   ├── 02_build_actual.py
│   ├── 03_generate_opex.py
│   ├── 04_generate_budget.py
│   ├── 05_generate_forecast.py
│   ├── 06_generate_scenarios.py
│   ├── 07_load_postgres.py
│   └── 08_validate_dataset.py
│
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   │
│   │   ├── agents/
│   │   │   ├── state.py
│   │   │   ├── graph.py
│   │   │   ├── router.py
│   │   │   ├── finance_agent.py
│   │   │   ├── kb_agent.py
│   │   │   └── scenario_agent.py
│   │   │
│   │   ├── tools/
│   │   │   ├── metric_tool.py
│   │   │   ├── variance_tool.py
│   │   │   ├── driver_tool.py
│   │   │   ├── sql_tool.py
│   │   │   ├── rag_tool.py
│   │   │   └── scenario_tool.py
│   │   │
│   │   ├── calculation/
│   │   │   ├── engine.py
│   │   │   ├── formulas.py
│   │   │   ├── scenario.py
│   │   │   └── validator.py
│   │   │
│   │   ├── semantic/
│   │   │   ├── metrics.yaml
│   │   │   ├── dimensions.yaml
│   │   │   ├── glossary.yaml
│   │   │   └── mappings.yaml
│   │   │
│   │   ├── integrations/
│   │   │   ├── database/
│   │   │   └── anaplan/
│   │   │       ├── interface.py
│   │   │       ├── local_engine.py
│   │   │       ├── anaplan_engine.py
│   │   │       └── client.py
│   │   │
│   │   ├── rag/
│   │   │   ├── ingest.py
│   │   │   ├── chunk.py
│   │   │   ├── embed.py
│   │   │   └── retrieve.py
│   │   │
│   │   └── prompts/
│   │       ├── system.md
│   │       ├── router.md
│   │       ├── finance.md
│   │       ├── root_cause.md
│   │       └── recommendation.md
│   │
│   └── tests/
│       ├── unit/
│       └── integration/
│
├── eval/
│   ├── golden_questions.json
│   ├── expected_answers.json
│   ├── evaluate_router.py
│   ├── evaluate_metrics.py
│   ├── evaluate_numbers.py
│   └── evaluate_end_to_end.py
│
└── frontend/
```

---

# 6. Phase 0 — Setup

## 6.1 Tech stack

Core:

```text
Python 3.11+
FastAPI
PostgreSQL
pgvector
LangGraph
Pydantic
SQLAlchemy
pandas / Polars
Docker Compose
```

AI:

```text
LLM provider abstraction
Embedding model
LangGraph
Wren semantic/context engine
```

Documents:

```text
Docling
pgvector
```

Anaplan:

```text
anaplan-sdk
```

Open-source references:

- WrenAI: https://github.com/Canner/WrenAI
- LangGraph: https://github.com/langchain-ai/langgraph
- Anaplan SDK: https://github.com/VinzenzKlass/anaplan-sdk
- Docling: https://github.com/docling-project/docling
- pgvector: https://github.com/pgvector/pgvector

## 6.2 Initial Docker services

Chỉ cần:

```text
postgres
backend
frontend
```

Không thêm RAGFlow, OpenBB, Redis, Kafka… trong MVP nếu chưa cần.

## Definition of Done

- Backend chạy được.
- PostgreSQL kết nối được.
- pgvector extension bật được.
- `/health` trả HTTP 200.

---

# 7. Phase 1 — Data profiling

Download:

```text
Financial Sample.xlsx
```

Đưa vào:

```text
data/raw/
```

Viết:

```text
scripts/01_profile_source.py
```

Kiểm tra:

- row count
- columns
- null values
- duplicate rows
- time range
- countries
- products
- segments
- units
- currencies
- consistency

Kiểm tra công thức:

```text
Sales ≈ Gross Sales - Discounts

Profit ≈ Sales - COGS
```

Không giả định công thức đúng trước khi kiểm tra.

Output:

```text
reports/data_profile.md
```

## Definition of Done

Bạn hiểu rõ:

```text
grain của mỗi row là gì
metric nào source-provided
metric nào derived
dimension nào có thể drill-down
```

---

# 8. Phase 2 — Build canonical Actual dataset

Không query Excel trực tiếp từ Agent.

ETL:

```text
Excel
  ↓
Raw DataFrame
  ↓
Normalize
  ↓
Canonical Finance Model
  ↓
PostgreSQL
```

## 8.1 Table `fact_finance`

Đề xuất:

```sql
fact_finance
(
    period_date,
    country_id,
    product_id,
    segment_id,
    department_id,
    account_id,
    version_id,
    amount,
    currency,
    source
)
```

### Grain

```text
Month
× Country
× Product
× Segment
× Department(optional)
× Account
× Version
```

### Account examples

```text
GROSS_SALES
DISCOUNT
REVENUE
COGS
GROSS_PROFIT

OPEX_SALES
OPEX_MARKETING
OPEX_OPERATIONS
OPEX_RND
OPEX_GNA

OPEX_TOTAL
EBITDA
```

## 8.2 `fact_driver`

```sql
fact_driver
(
    period_date,
    country_id,
    product_id,
    segment_id,
    version_id,

    units,
    average_sale_price,
    unit_cogs,
    average_manufacturing_price,
    discount_rate,

    source
)
```

Các metrics:

```text
Units
ASP
Manufacturing Cost
Discount Rate
```

Rất quan trọng cho root-cause analysis.

---

# 9. Phase 3 — Generate synthetic OPEX

Financial Sample không phải full internal P&L.

Tạo OPEX synthetic nhưng deterministic.

Departments:

```text
Sales
Marketing
Operations
R&D
Finance & G&A
```

Ví dụ:

```text
Sales OPEX
= Fixed Sales Cost
+ Revenue × Sales Cost %

Marketing OPEX
= Marketing Base
+ Revenue × Marketing %

Operations OPEX
= Revenue × Operations %

R&D
= Fixed R&D + Product-dependent amount

G&A
= Fixed G&A + Revenue × small_ratio
```

Ví dụ config:

```yaml
opex:
  sales:
    fixed_monthly: 250000
    revenue_ratio: 0.025

  marketing:
    fixed_monthly: 180000
    revenue_ratio: 0.035

  operations:
    fixed_monthly: 150000
    revenue_ratio: 0.020

  rnd:
    fixed_monthly: 300000
    revenue_ratio: 0.010

  gna:
    fixed_monthly: 200000
    revenue_ratio: 0.015
```

Thêm:

```text
seasonality
country coefficient
controlled noise
```

Ví dụ:

```python
rng = np.random.default_rng(42)
```

Luôn giữ `seed=42`.

## Derived metrics

```text
Gross Profit = Revenue - COGS

OPEX = sum(Department OPEX)

EBITDA = Gross Profit - OPEX

Gross Margin % = Gross Profit / Revenue

EBITDA Margin % = EBITDA / Revenue
```

## Unit tests

```text
Revenue - COGS == Gross Profit

sum(OPEX departments) == OPEX

Gross Profit - OPEX == EBITDA
```

Sai số rounding phải xác định rõ.

---

# 10. Phase 4 — Generate Budget

Budget không phải Actual × random percentage một cách tùy tiện.

Tạo assumptions rõ ràng.

Ví dụ:

```yaml
budget:
  revenue_growth:
    default: 0.06

  units_growth:
    default: 0.03

  price_growth:
    default: 0.025

  cogs_inflation:
    default: 0.02

  marketing_growth:
    default: 0.05

  payroll_growth:
    default: 0.04
```

Có thể thay đổi theo country/product.

Ví dụ:

```text
Budget Units 2026
= Actual Units 2025 × (1 + Units Growth Assumption)

Budget Price
= Actual ASP 2025 × (1 + Price Growth)

Budget Revenue
= Budget Units × Budget Price × (1 - Discount Rate)

Budget COGS
= Budget Units × Budget Unit Cost

Budget EBITDA
= Budget Gross Profit - Budget OPEX
```

Lưu assumptions riêng.

```sql
fact_assumption
(
    scenario,
    period,
    dimension_type,
    dimension_value,
    assumption_name,
    assumption_value
)
```

Không hard-code assumptions sâu trong Python.

---

# 11. Phase 5 — ML-assisted Forecasting Engine

Phase 5 forecast toàn bộ năm 2015 từ Actual đến tháng 12/2014. Do Microsoft
Financial Sample chỉ có 16 tháng và các series ở grain chi tiết khá sparse,
ML trong phase này là proof of concept, không phải production accuracy claim.

```text
Actual → Features → Seasonal Naive / Ridge / XGBoost
       → One-step + Recursive Backtest → Champion
       → Forecast Units
       → Rule-based ASP / Unit COGS / Discount Rate
       → Deterministic P&L / OPEX / EBITDA
       → Forecast vs Budget
```

Nguyên tắc:

- ML chỉ dự báo `Units`; không dự báo độc lập Revenue, COGS, Gross Profit hay EBITDA.
- Budget chỉ dùng để kiểm tra coverage và so sánh sau forecast, không phải model input.
- Missing observation không tự động mang nghĩa `Units = 0`.
- `unit_cogs = COGS / Units`; không đồng nhất với `average_manufacturing_price`.
- Mọi expected row count được derive từ scaffold và grain, không hard-code.

## Phase 5A — Scaffold và leakage-safe features

Scaffold được tạo từ Actual 2014 chuyển sang cùng month/dimensions của năm 2015.
Feature của tháng `t` chỉ được dùng observations trước `t`, gồm calendar features,
ba observations gần nhất, rolling statistics, months since last observation,
Country × Product history và `units_same_month_last_year` cùng missing flag.

## Phase 5B–5D — Candidate models

- Seasonal Naive với deterministic sparse-series fallback.
- Global Ridge với preprocessing nằm trọn trong sklearn Pipeline.
- Global XGBoost với hyperparameters cố định và `random_seed = 42`.

Ridge và XGBoost dự báo `log1p(Units)`, inverse transform và clip về không âm.

## Phase 5E — Evaluation và Champion

Evaluation A là four-fold one-step expanding window cho Sep–Dec 2014.
Evaluation B train đến Aug 2014 rồi recursively forecast Sep–Dec theo month batch.

Metrics gồm MAE, RMSE, pooled WAPE, sMAPE, macro/median series WAPE, country WAPE
và prediction coverage. Coverage bắt buộc 100%.

Champion dùng recursive pooled WAPE. Model phức tạp hơn chỉ thay model đơn giản
hơn nếu cải thiện ít nhất `simplicity_tolerance = 0.005`.

## Phase 5F — Drivers và recursive deployment

Units được forecast theo month batch: predict toàn bộ keys một tháng, append toàn
bộ batch rồi mới build features cho tháng sau. ASP, Unit COGS và Discount Rate ưu
tiên same-grain/same-month previous year, sau đó trailing-three và aggregate fallback.

## Phase 5G — Canonical Forecast

```text
Gross Sales  = Units × Average Sale Price
Discount     = Gross Sales × Discount Rate
Revenue      = Gross Sales - Discount
COGS         = Units × Unit COGS
Gross Profit = Revenue - COGS
OPEX Total   = sum(Department OPEX)
EBITDA       = Gross Profit - OPEX Total
```

`PlanningEngine` quản lý Budget/Scenario assumptions. `ForecastEngine` tạo
prediction từ historical Actual. Rolling Actual YTD được hoãn đến khi có Actual
2015; Phase 5.1 sẽ dùng lịch sử dài hơn để đánh giá proper 12-month holdout.

---

# 12. Phase 6 — Create deliberate anomalies

Nếu data quá sạch, root-cause analysis không có gì thú vị.

Tạo 5–10 business events deterministic.

Ví dụ:

## Event A

```text
Vietnam
Product Paseo
Q3

Volume -12%
```

## Event B

```text
Germany
Product VTT
Q4

Manufacturing Cost +8%
```

## Event C

```text
France

Marketing OPEX +15%
```

## Event D

```text
USA
Product Amarilla

Discount Rate +5 percentage points
```

Lưu event ground truth:

```json
{
  "event_id": "EVT_001",
  "period": "2026-Q3",
  "country": "Vietnam",
  "product": "Paseo",
  "driver": "volume",
  "change": -0.12,
  "expected_effect": "revenue_down"
}
```

File:

```text
data/ground_truth/events.json
```

Đây là dữ liệu dùng để đánh giá:

> Agent có thực sự tìm đúng nguyên nhân hay chỉ viết explanation nghe hợp lý?

---

# 13. Phase 7 — Scenario engine

Đây là local replacement cho Anaplan trong development.

Tạo interface:

```python
class PlanningEngine:
    def get_metric(...):
        ...

    def compare_versions(...):
        ...

    def run_scenario(...):
        ...

    def get_drivers(...):
        ...
```

Implementation 1:

```text
LocalPlanningEngine
```

Implementation 2 sau này:

```text
AnaplanPlanningEngine
```

Agent chỉ gọi interface.

## Scenario input

```json
{
  "scenario_name": "price_up_volume_down",
  "filters": {
    "country": "Vietnam",
    "period": "FY2027"
  },
  "assumptions": {
    "price_pct": 0.03,
    "volume_pct": -0.01
  }
}
```

## Deterministic calculation

```text
Scenario Price
= Base Price × 1.03

Scenario Volume
= Base Volume × 0.99

Revenue
= Scenario Volume × Scenario Price × (1 - Discount)

COGS
= Scenario Volume × Unit Cost

Gross Profit
= Revenue - COGS

EBITDA
= Gross Profit - OPEX
```

Output:

```json
{
  "base_ebitda": 10000000,
  "scenario_ebitda": 10600000,
  "impact": 600000,
  "impact_pct": 0.06
}
```

---

# 14. Phase 8 — Semantic Layer

Đây là phần AI quan trọng nhất.

File:

```text
backend/app/semantic/metrics.yaml
```

Ví dụ:

```yaml
revenue:
  display_name: Revenue

  aliases:
    - sales
    - net sales
    - turnover

  type: currency

  definition: >
    Net revenue after discounts.

  formula:
    expression: gross_sales - discounts

  supported_dimensions:
    - period
    - country
    - product
    - segment

gross_profit:
  display_name: Gross Profit

  aliases:
    - GP

  formula:
    expression: revenue - cogs

gross_margin:
  display_name: Gross Margin %

  aliases:
    - GM
    - GM%
    - gross margin

  type: percentage

  formula:
    expression: gross_profit / revenue

ebitda:
  display_name: EBITDA

  aliases:
    - earnings before interest tax depreciation amortization

  formula:
    expression: gross_profit - opex
```

## Dimensions

`dimensions.yaml`:

```yaml
time:
  aliases:
    - month
    - quarter
    - year
    - period

country:
  aliases:
    - market
    - geography
    - region

product:
  aliases:
    - sku
    - product line
```

## Time semantics

Phải tự xử lý:

```text
this month
last month
current quarter
last quarter
YTD
FY2026
same period last year
YoY
QoQ
rolling 12 months
```

Không để raw LLM output đi thẳng xuống SQL.

---

# 15. Phase 9 — SQL / Semantic query

Đề xuất:

```text
Natural Language
      │
      ▼
Intent parser
      │
      ▼
Semantic resolution
      │
      ▼
Structured Finance Query
      │
      ▼
SQL generation
      │
      ▼
Validation
      │
      ▼
PostgreSQL
```

Intermediate representation:

```json
{
  "metric": "revenue",
  "version": "actual",
  "period": {
    "type": "quarter",
    "value": "2026-Q2"
  },
  "filters": {
    "country": "Vietnam"
  },
  "group_by": []
}
```

Lợi ích:

- test dễ
- không phụ thuộc LLM SQL hoàn toàn
- giảm hallucination
- audit được
- map sang Anaplan sau này được

Có thể dùng WrenAI ở semantic/context layer.

---

# 16. Phase 10 — Knowledge Base

Không cần bắt đầu bằng hàng nghìn PDF.

Tạo 5 tài liệu controlled:

```text
finance_metric_dictionary.md
budget_policy.md
forecast_policy.md
scenario_policy.md
company_context.md
```

Ví dụ `budget_policy.md`:

```text
Annual budget is approved in November.

Department managers may propose budget changes.

Changes above $100,000 require Finance Director approval.

Changes above $500,000 require CFO approval.
```

`forecast_policy.md`:

```text
Rolling forecast is refreshed monthly.

Actuals replace forecast values after month-end close.

Forecast horizon is 12 months.
```

Lợi ích:

- biết chắc correct answer
- kiểm tra retrieval accuracy
- kiểm tra citation
- không phụ thuộc documents quá phức tạp ngay từ đầu

## Pipeline

```text
Markdown / PDF
     ↓
Docling
     ↓
Structured chunks
     ↓
Embedding
     ↓
pgvector
```

Metadata:

```text
document_id
title
section
version
effective_date
access_level
chunk_id
```

---

# 17. Phase 11 — LangGraph Agent

Không xây single-agent prompt khổng lồ.

Graph:

```text
START
  │
  ▼
Understand Request
  │
  ▼
Resolve Finance Semantics
  │
  ▼
Intent Router
  │
  ├──────── Metric Query ───────► Metric Tool
  │
  ├──────── Variance ───────────► Variance Tool
  │
  ├──────── Driver Analysis ────► Driver Tool
  │
  ├──────── Scenario ───────────► Scenario Tool
  │
  └──────── Knowledge ──────────► RAG Tool
                                    │
             ┌──────────────────────┘
             ▼
      Numerical Validator
             │
             ▼
      Evidence Validator
             │
             ▼
       Answer Synthesis
             │
             ▼
            END
```

---

# 18. Tools

## `get_metric`

```python
get_metric(
    metric,
    period,
    version,
    filters,
    group_by
)
```

## `compare_metric`

```python
compare_metric(
    metric,
    period,
    base_version,
    comparison_version,
    filters
)
```

## `analyze_drivers`

```python
analyze_drivers(
    metric,
    period,
    base_version,
    comparison_version,
    filters
)
```

## `run_scenario`

```python
run_scenario(
    base_version,
    assumptions,
    filters
)
```

## `search_knowledge`

```python
search_knowledge(
    query,
    top_k
)
```

Không expose:

```text
execute_arbitrary_sql()
```

cho LLM ở production version.

---

# 19. Phase 12 — Driver decomposition

Đây là phần nên đầu tư AI/research.

Revenue:

```text
Revenue ≈ Volume × Price × (1 - Discount)
```

Variance có thể decomposition:

```text
Total Revenue Variance
│
├── Volume Impact
├── Price Impact
├── Discount Impact
└── Mix Impact
```

Gross Profit:

```text
Gross Profit Variance
│
├── Revenue Impact
└── COGS Impact
```

EBITDA:

```text
EBITDA Variance
│
├── Revenue
├── COGS
└── OPEX
    ├── Sales
    ├── Marketing
    ├── Operations
    ├── R&D
    └── G&A
```

Agent phải drill-down recursively.

Pseudo-flow:

```text
EBITDA below Budget
      │
      ▼
Compare Revenue / COGS / OPEX
      │
      ▼
Select largest contributors
      │
      ▼
Drill into Country
      │
      ▼
Drill into Product
      │
      ▼
Inspect Volume / Price / Discount / Cost
```

LLM dùng để:

- decide next drill-down
- summarize
- rank evidence

Calculation dùng deterministic code.

---

# 20. Phase 13 — Numerical Validator

Không cho LLM trả lời số liệu trước validation.

Các checks:

```text
Revenue - COGS = Gross Profit

Gross Profit - OPEX = EBITDA

Actual - Budget = Variance

Variance / Budget = Variance %

sum(driver impacts) ≈ total variance
```

Validator output:

```json
{
  "valid": true,
  "checks": [
    {
      "name": "variance_reconciliation",
      "status": "passed"
    }
  ]
}
```

Nếu fail:

```text
re-query
or
recalculate
```

Không hallucinate để “lấp” sai lệch.

---

# 21. Phase 14 — Recommendation engine

Không hỏi LLM:

```text
"What should the company do?"
```

rồi dùng output trực tiếp.

Pipeline:

```text
Problem
  ↓
Driver decomposition
  ↓
Controllability classification
  ↓
Generate action candidates
  ↓
Scenario simulation
  ↓
Financial impact
  ↓
Risk / constraint evaluation
  ↓
Rank options
```

Ví dụ:

```text
EBITDA gap = -5M
```

Drivers:

```text
Volume          -3.2M
COGS            -1.4M
Marketing       -0.8M
Other           +0.4M
```

Candidate actions:

```text
Price +2%
Marketing -5%
COGS -2%
Volume recovery +3%
```

Mỗi candidate phải chạy scenario engine.

Output:

| Action | EBITDA Impact | Revenue Risk | Controllability |
|---|---:|---|---|
| Price +2% | +2.1M | Medium | Medium |
| COGS -2% | +1.7M | Low | Medium |
| Marketing -5% | +0.5M | Low | High |
| Volume +3% | +1.9M | Medium | Medium |

LLM chỉ viết recommendation dựa trên bảng này.

---

# 22. Phase 15 — System prompts

## Global system prompt principles

```text
You are an enterprise Finance Decision Intelligence Assistant.

Never invent financial values.

Structured financial data must come from approved tools.

Budget, Forecast and Scenario values must come from the planning engine.

Company policies must come from the Knowledge Base.

Never use the LLM itself as the authoritative calculator.

Metric definitions must follow the Finance Semantic Catalog.

Clearly distinguish:
- observed facts
- deterministic calculations
- inferred explanations
- recommendations

Every numerical answer must preserve:
- metric
- version
- period
- dimensions
- currency
- unit

If evidence is insufficient, say so.

Do not expose data outside authorized dimensions.
```

Không nhét toàn bộ business glossary vào system prompt.

Glossary phải nằm semantic layer / retrieval context.

---

# 23. Phase 16 — Evaluation dataset

Tạo:

```text
eval/golden_questions.json
```

Tối thiểu:

```text
100 questions
```

Phân bố:

```text
20 metric lookup
15 comparison
20 variance
15 driver/root-cause
10 KB
10 scenario
10 recommendation
```

Mỗi question lưu:

```json
{
  "id": "Q001",
  "question": "What was Vietnam revenue in Q2 2026?",
  "expected_intent": "METRIC_QUERY",
  "expected_metric": "revenue",
  "expected_filters": {
    "country": "Vietnam"
  },
  "expected_period": "2026-Q2",
  "expected_tool": "get_metric",
  "expected_value": 1234567.89,
  "tolerance": 0.01
}
```

---

# 24. Evaluation metrics

## Semantic

```text
Intent Accuracy
Metric Resolution Accuracy
Dimension Resolution Accuracy
Time Resolution Accuracy
```

## Tool use

```text
Tool Selection Accuracy
Tool Argument Accuracy
Invalid Tool Call Rate
```

## Finance

```text
Numerical Accuracy
Variance Accuracy
Driver Recall@K
Driver Ranking Accuracy
Scenario Accuracy
Reconciliation Pass Rate
```

## RAG

```text
Retrieval Recall@K
Citation Accuracy
Answer Groundedness
```

## Safety

```text
Unauthorized Data Leakage = 0
Unapproved Write Action = 0
```

## End-to-end

```text
Answer Correctness
Hallucination Rate
Latency
Cost per question
```

---

# 25. Phase 17 — Anaplan adapter

Sau khi local version chạy tốt mới làm Anaplan.

Interface không đổi:

```text
PlanningEngine
```

Implement:

```text
LocalPlanningEngine
AnaplanPlanningEngine
```

Flow:

```text
Agent
  ↓
PlanningEngine
  ↓
if local:
    PostgreSQL + Python engine

if Anaplan:
    Anaplan adapter
      ↓
    anaplan-sdk
      ↓
    Anaplan API
```

Mapping:

```yaml
revenue:
  local:
    account: REVENUE

  anaplan:
    model: FP&A
    module: Revenue Planning
    line_item: Revenue

ebitda:
  local:
    account: EBITDA

  anaplan:
    model: FP&A
    module: P&L Summary
    line_item: EBITDA
```

Điều này giúp project vẫn chạy được dù chưa có Anaplan tenant.

---

# 26. Phase 18 — Anaplan module design tương lai

Khi có Anaplan:

## Module 1

```text
Revenue Planning

Dimensions:
Time
Country
Product
Scenario

Line Items:
Units
Price
Discount %
Revenue
COGS
Gross Profit
```

## Module 2

```text
OPEX Planning

Dimensions:
Time
Country
Department
Scenario

Line Items:
Headcount
Fixed Cost
Variable Cost
OPEX
```

## Module 3

```text
P&L Summary

Dimensions:
Time
Country
Scenario

Line Items:
Revenue
COGS
Gross Profit
OPEX
EBITDA
Gross Margin %
EBITDA Margin %
```

Agent không cần biết mọi module formula.

Adapter map semantic metric → module/line item.

---

# 27. Phase 19 — Optional SimFin extension

Sau MVP:

```text
SimFin
  ↓
External Fundamentals
  ↓
Company Benchmark Tool
```

Ví dụ câu hỏi:

```text
How does our gross margin compare with similar public companies?

Is our revenue growth above the external benchmark?

How does our cost structure compare with peers?
```

Không trộn SimFin vào internal Actual.

Tạo datasource riêng:

```text
internal_finance
external_benchmark
```

Agent phải nói rõ nguồn.

---

# 28. Phase 20 — UI

MVP UI chỉ cần:

```text
Chat
Table
Simple chart
Source/Evidence panel
Tool trace
```

Một response tốt:

```text
Answer

Evidence
- Actual Revenue: ...
- Budget Revenue: ...

Variance
- $...
- ...%

Top Drivers
1. Vietnam Product A Volume
2. Germany Cost Increase

Source
- Finance DB
- Version: Actual/Budget
- Period: Q3 FY2026
```

Thêm debug mode:

```text
intent
semantic parse
tools called
validation result
latency
```

Rất hữu ích khi demo AI Engineer.

---

# 29. Suggested implementation order

## Milestone 1 — Data Foundation

Làm:

- download source
- profile
- normalize
- generate OPEX
- generate Budget
- generate Forecast
- PostgreSQL load

**Không làm LLM trước.**

Output:

```text
SQL query được toàn bộ Actual/Budget/Forecast.
```

---

## Milestone 2 — Deterministic Finance Engine

Làm:

- metric formulas
- variance
- driver decomposition
- scenario engine
- numerical validation

Output:

```text
Không dùng LLM vẫn tính được toàn bộ finance answers.
```

Đây là milestone cực kỳ quan trọng.

---

## Milestone 3 — Semantic AI

Làm:

- metric catalog
- aliases
- time parser
- dimension resolver
- structured query representation
- Wren integration

Output:

```text
Natural language
→ structured finance request
```

---

## Milestone 4 — Agent

Làm:

- LangGraph
- router
- tool calls
- validation node
- response synthesis

Output:

```text
Q&A end-to-end.
```

---

## Milestone 5 — KB

Làm:

- Docling
- chunking
- pgvector
- citations
- KB route

Output:

```text
Structured data + policy QA.
```

---

## Milestone 6 — Root Cause AI

Làm:

- recursive drill-down
- driver scoring
- anomaly detection
- explanation grounding

Đây là phase nên đầu tư nhiều vào AI.

---

## Milestone 7 — Recommendation AI

Làm:

- candidate generation
- controllability
- scenario execution
- ranking
- explanations

---

## Milestone 8 — Anaplan

Làm cuối:

- adapter
- auth
- read
- scenario
- optional write-back with approval

---

# 30. 8-week roadmap gợi ý

## Week 1

```text
Dataset
Schema
ETL
Actual
PostgreSQL
```

## Week 2

```text
Budget
Forecast
OPEX
Scenario
Validation
```

## Week 3

```text
Semantic catalog
Time parsing
Finance query representation
```

## Week 4

```text
LangGraph
Metric
Comparison
Variance
```

## Week 5

```text
Driver analysis
Root cause
Numerical validator
```

## Week 6

```text
KB
Docling
pgvector
RAG
```

## Week 7

```text
Scenario
Recommendation
Evaluation
```

## Week 8

```text
Anaplan adapter
UI polish
README
Demo
CV metrics
```

Nếu thời gian ít, bỏ Anaplan integration thật và chỉ giữ adapter/interface + architecture diagram.

---

# 31. Những thứ KHÔNG nên làm ở đầu project

Không bắt đầu bằng:

```text
Fine-tune LLM
Multi-agent phức tạp
Knowledge Graph lớn
Kafka
Microservices
Kubernetes
Full Anaplan write-back
1000 PDFs
Real-time streaming
```

Những thứ này không giải quyết core problem.

Core problem là:

```text
User Question
     ↓
Correct Finance Semantics
     ↓
Correct Data
     ↓
Correct Calculation
     ↓
Correct Drivers
     ↓
Correct Scenario
     ↓
Grounded Explanation
```

---

# 32. AI improvements nên nghiên cứu

Sau baseline, tập trung experiment từng phần.

## Experiment A — Metric Resolution

Baseline:

```text
prompt-only
```

Improved:

```text
aliases + semantic retrieval + schema context
```

Measure:

```text
Metric Resolution Accuracy
```

---

## Experiment B — Tool Routing

Compare:

```text
single prompt
vs
classifier
vs
LangGraph router
```

Measure:

```text
Tool Selection Accuracy
```

---

## Experiment C — Root Cause Search

Baseline:

```text
top variance dimension
```

Improved:

```text
recursive drill-down
+
contribution scoring
+
anomaly score
```

Measure:

```text
Driver Recall@3
Driver NDCG
```

---

## Experiment D — RAG + Structured Data

Compare:

```text
RAG-only
vs
SQL-only
vs
hybrid routing
```

Measure:

```text
answer accuracy
numerical hallucination
groundedness
```

---

## Experiment E — Recommendation

Baseline:

```text
LLM recommendation
```

Improved:

```text
LLM candidate generation
+
deterministic scenario simulation
+
constraint ranking
```

Measure:

```text
Scenario validity
Recommendation utility
Unsupported recommendation rate
```

Đây có thể trở thành điểm nổi bật nhất của project.

---

# 33. Demo story cuối project

Demo theo một conversation liên tục.

### Q1

```text
What is our FY2026 revenue forecast?
```

Agent:

```text
Forecast = ...
```

### Q2

```text
How does it compare with budget?
```

Agent:

```text
Variance = ...
```

### Q3

```text
Why are we below budget?
```

Agent:

```text
Top drivers:
1. ...
2. ...
3. ...
```

### Q4

```text
Which product is the biggest problem?
```

Agent giữ context và drill-down.

### Q5

```text
What can we do?
```

Agent generate candidate levers.

### Q6

```text
What if we increase price by 2%?
```

Scenario engine chạy.

### Q7

```text
Which option is best?
```

Agent compare scenario results.

### Q8

```text
Can I directly change the forecast?
```

Agent kiểm tra policy và approval rule từ KB.

Đây là demo thể hiện gần đầy đủ:

```text
Conversation Memory
Semantic Layer
Structured Data
RAG
Finance Reasoning
Scenario Planning
Tool Use
Governance
```

---

# 34. CV description mục tiêu

Khi hoàn thành có thể mô tả theo kiểu:

```text
Finance Decision Intelligence Copilot

- Built an agentic FP&A assistant integrating structured financial data,
  semantic metrics, knowledge retrieval, deterministic financial
  calculations, and scenario planning.

- Implemented natural-language finance queries across Actual, Budget,
  and Forecast with metric/time/dimension resolution and auditable
  tool execution.

- Developed recursive variance and driver analysis for Revenue,
  Gross Margin, OPEX, and EBITDA.

- Added deterministic what-if scenario simulation and ranked
  recommendation generation with numerical validation.

- Designed an adapter architecture supporting a local planning engine
  and future Anaplan integration.

- Evaluated the system using a controlled finance benchmark covering
  intent routing, numerical accuracy, driver attribution, retrieval,
  and scenario correctness.
```

Sau này thay bằng số metric thật từ evaluation.

---

# 35. Definition of Done cho toàn project

Project chỉ được xem là hoàn thành khi:

- [ ] Actual dataset được normalize.
- [ ] Budget được sinh deterministic.
- [ ] Forecast được sinh deterministic.
- [ ] OPEX và EBITDA tồn tại.
- [ ] Driver data tồn tại.
- [ ] Có ít nhất 5 deliberate business events.
- [ ] SQL trả lời đúng metric queries.
- [ ] Semantic layer resolve metric aliases.
- [ ] Time expressions được normalize.
- [ ] Agent route đúng structured vs KB vs scenario.
- [ ] Variance được deterministic calculate.
- [ ] Root-cause trả về evidence.
- [ ] Scenario engine có unit tests.
- [ ] Numerical validator hoạt động.
- [ ] KB có citations.
- [ ] Có ít nhất 100 golden questions.
- [ ] Có evaluation report.
- [ ] Có Docker setup.
- [ ] Có architecture diagram.
- [ ] Có demo video/GIF.
- [ ] Anaplan adapter interface tồn tại.
- [ ] Không có số liệu do LLM tự bịa.

---

# 36. Việc nên làm ngay bây giờ

Thực hiện đúng thứ tự sau.

## Step 1

Download:

```text
Financial Sample.xlsx
```

## Step 2

Tạo repository:

```bash
mkdir finance-ai-copilot
cd finance-ai-copilot
git init
```

## Step 3

Tạo:

```text
data/raw/
scripts/
backend/
eval/
```

## Step 4

Viết:

```text
scripts/01_profile_source.py
```

Chưa dùng LLM.

## Step 5

Thiết kế:

```text
fact_finance
fact_driver
fact_assumption
```

## Step 6

Generate:

```text
Actual
OPEX
Budget
Forecast
```

## Step 7

Viết unit tests cho:

```text
Gross Profit
Gross Margin
OPEX
EBITDA
Variance
```

## Step 8

Khi tất cả đúng mới bắt đầu:

```text
Semantic Layer
→ LangGraph
→ RAG
→ Recommendation
→ Anaplan
```

---

# 37. Quyết định cuối cùng về dataset

Cho version đầu tiên:

```text
PRIMARY DATASET
Microsoft Financial Sample
        +
Synthetic FP&A augmentation
```

Trong đó:

```text
REAL SOURCE DATA
Sales
COGS
Units
Product
Country
Segment
Time

SYNTHETIC BUT DETERMINISTIC
OPEX
Department
Budget
Forecast
Planning Assumptions
Business Events
Scenarios
```

Sau đó:

```text
V2
Contoso Retail DW

V3
SimFin external benchmark

V4
Anaplan adapter / real tenant
```

Đây là hướng cân bằng tốt nhất giữa:

```text
Realism
Development effort
AI research value
Evaluation quality
Anaplan compatibility
CV value
```

---

## References

Microsoft Financial Sample:

https://learn.microsoft.com/en-us/power-bi/create-reports/sample-financial-download

Microsoft Power BI samples:

https://learn.microsoft.com/en-us/power-bi/create-reports/sample-datasets

Microsoft Contoso Retail:

https://www.microsoft.com/en-us/download/details.aspx?id=18279

Microsoft SQL Server samples:

https://github.com/microsoft/sql-server-samples

SimFin:

https://www.simfin.com/en/fundamental-data-download/

WrenAI:

https://github.com/Canner/WrenAI

LangGraph:

https://github.com/langchain-ai/langgraph

Anaplan Python SDK:

https://github.com/VinzenzKlass/anaplan-sdk

Docling:

https://github.com/docling-project/docling

pgvector:

https://github.com/pgvector/pgvector
