# Payment Transaction Analytics and Business Intelligence Platform

A Python project for generating synthetic payment data, validating and preparing it for analysis, exploring business metrics, and presenting results through a Streamlit dashboard and a read-only FastAPI service.

> **Synthetic data only:** Every record in this project is generated for demonstration. It does not contain real Visa, bank, customer, merchant, or payment data. Do not use the sample data or applications for real payment processing or fraud decisions.

## Project overview

The project demonstrates an analytics workflow from data generation through reporting:

- Generate related customer, card, merchant, and transaction CSV datasets with Faker and configured random seeds.
- Validate required fields, unique identifiers, relationships, customer/card ownership, valid dates, allowed statuses and categories, age ranges, and positive finite transaction amounts.
- Clean transaction data, derive month and status flags, and create dashboard-ready datasets and customer/merchant summaries.
- Produce monthly and category performance reports, transaction-status summaries, and amount-anomaly review output.
- Explore metrics using an interactive Streamlit dashboard and read-only FastAPI endpoints.
- Find MySQL schema, load, quality-check, and business-query examples, plus optional MongoDB aggregation and Power BI guides.

The amount-anomaly script uses a simple z-score threshold to flag unusual amounts for **review**. It is an educational heuristic, not a fraud-detection model or a fraud verdict.

## Data flow

```text
Faker-based Python generators
    -> data/raw/
        -> validate_data.py
        -> clean_data.py -> data/processed/ -> Streamlit / FastAPI / SQL / BI
        -> eda.py --------------------------> reports/
        -> anomaly_detection.py ------------> reports/

```

The generators use configured random seeds and a fixed reference date. Faker is pinned in the API/runtime dependency file to improve repeatability across environments. Generator repeatability tests pass in the current environment; byte-for-byte parity with a historical Render environment has not been independently established. Raw CSVs are ignored by Git and are not checked in. The cleaning step removes duplicate transaction IDs and transactions with non-positive or non-finite amounts. It also writes a public card dataset without sensitive card fields.

## Repository structure

```text
api/                      FastAPI application
dashboard/                Streamlit dashboard
data/raw/                 Generated source CSV datasets (not tracked by Git)
data/processed/           Cleaned datasets and summary tables
docs/                     Table design and optional BI guides
reports/                  Generated analysis CSV outputs
sql/                       MySQL schema, import, checks, and queries
src/                       Generators, validation, cleaning, and analysis
tests/                     Pipeline, API, and dashboard-data tests
.github/workflows/ci.yml  GitHub Actions validation workflow
render.yaml               Render blueprint for the API
requirements*.txt         Project and app-specific Python dependencies
```

Generated raw CSV files are ignored by Git via `.gitignore`. Run the generators before running the cleaning, analysis, dashboard, or API steps when their expected data files are not present. The six dashboard-safe processed CSVs are tracked by Git according to the latest repository audit. Raw card-number/CVV data must not be committed or exposed through the API or dashboard.

## Technology

- **Python** for generation, validation, cleaning, and analysis
- **Faker**, **pandas**, and **NumPy** for synthetic data and data processing
- **Streamlit** for the interactive dashboard
- **FastAPI** and **Uvicorn** for the read-only API
- **MySQL** for the relational schema and query examples
- **MongoDB** aggregation and **Power BI** are documented as optional analysis integrations

CI and Render are configured for Python 3.12.8. The local audit environment used Python 3.14.4, so Python 3.12.8 was not tested locally. The root `requirements.txt` contains the project's pipeline and dashboard dependencies and includes FastAPI. Render installs pinned direct API and generation dependencies from `requirements-api.txt`; transitive dependencies are resolved by pip and are not individually pinned.

## Quick start

From the repository root, create a virtual environment and install the project dependencies.

### Windows PowerShell

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt -r requirements-api.txt
```

### macOS or Linux

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt -r requirements-api.txt
```

Generate, validate, and prepare the datasets:

```bash
python src/generate_customers.py
python src/generate_cards.py
python src/generate_merchants.py
python src/generate_transactions.py
python src/validate_data.py
python src/clean_data.py
```

The transaction generator depends on the customer, card, and merchant source files, so run those generators first. The pipeline writes cleaned tables and summaries to `data/processed/`.

Generate the analysis reports when needed:

```bash
python src/eda.py
python src/anomaly_detection.py
```

## Run the applications

### Streamlit dashboard

```bash
python -m streamlit run dashboard/app.py
```

Open `http://localhost:8501`. The dashboard reads the processed CSV files. Select at least one merchant category in the sidebar to display the KPIs, charts, and filtered tables; status and bank filters can further narrow the results.

### FastAPI

In a separate terminal, with the virtual environment activated:

```bash
python -m uvicorn api.app:app --reload
```

The local API is available at `http://localhost:8000`. FastAPI serves interactive documentation at `/docs` and the OpenAPI document at `/openapi.json`. The API needs `data/processed/transactions_clean.csv`; run the data pipeline first.

The repository also includes VS Code tasks for starting the dashboard and API.

## API reference

All application endpoints are read-only `GET` routes.

| Route | Purpose |
|---|---|
| `/` | Service name and documentation links |
| `/health` | Checks that processed transaction data is available |
| `/api/v1/summary` | Transaction, completion, amount, success-rate, and active-customer summary |
| `/api/v1/transactions` | Paginated transaction records; supports `category`, `status`, and `bank` filters |
| `/api/v1/categories` | Transaction counts and completed amount by category |
| `/api/v1/banks` | Transaction counts and completed amount by bank |
| `/api/v1/merchants` | Merchant transaction, failure-rate, and completed-amount summaries |

The transaction route defaults to `limit=50` and `offset=0`; `limit` must be between 1 and 100 and `offset` must be non-negative. The merchant route defaults to `limit=20`, with a maximum of 100.

The transaction response model omits customer and card identifiers and sensitive card fields. The API is not an authenticated payment service; keep it limited to synthetic demonstration data.

## SQL and optional analytics

- `sql/01_schema.sql` creates the MySQL database and tables.
- `sql/02_business_queries.sql` contains KPI, trend, category, customer, merchant, and bank analysis queries.
- `sql/03_load_processed_data.sql` loads the generated processed CSV files.
- `sql/04_quality_checks.sql` checks row counts, relationships, ownership consistency, and sensitive-column presence.
- `docs/mongodb_analytics.md` contains optional MongoDB import and aggregation examples.
- `docs/power_bi_guide.md` describes a Power BI model, suggested report pages, and example DAX measures.

MySQL must be installed and configured separately to execute the SQL scripts. **The data-load script deletes existing rows in its target tables before loading the generated data.** Use it only with the dedicated synthetic project database after confirming it contains no user-owned data.

## Tests and continuous integration

Run the repository's tests with:

```bash
python -m unittest discover -s tests -v
```

The latest reported local test run passed **20 tests**. The following compilation check also completed successfully:

```bash
python -m compileall src api dashboard tests
```

The test suite covers transaction cleaning and validation, API summaries/filtering/pagination and response fields, generator repeatability, and availability of the dashboard's processed data. The GitHub Actions workflow compiles the project, rebuilds the synthetic datasets and reports, validates the data, and runs the test suite for pushes and pull requests. Local testing was performed with Python 3.14.4; the configured Python 3.12.8 runtime remains to be verified by CI/hosted execution.

## Deployment

### Streamlit Community Cloud

[Public dashboard](https://payment-transaction-analytics.streamlit.app/)

The app entry point is `dashboard/app.py`. It uses the six dashboard-safe processed CSV files under `data/processed/`. The public dashboard has been verified to load and display KPIs, charts, tables, and interactive filters.

### Render API

- API base URL: [https://payment-transaction-analytics.onrender.com](https://payment-transaction-analytics.onrender.com/)
- API documentation: [https://payment-transaction-analytics.onrender.com/docs](https://payment-transaction-analytics.onrender.com/docs)
- Health check: [https://payment-transaction-analytics.onrender.com/health](https://payment-transaction-analytics.onrender.com/health)
- Summary endpoint: [https://payment-transaction-analytics.onrender.com/api/v1/summary](https://payment-transaction-analytics.onrender.com/api/v1/summary)

The health check returned `{"status":"ok","data_available":true}`. The summary endpoint returned 964 total transactions, 681 completed transactions, INR 2,332,474.66 in completed amounts, a success rate of approximately 70.64%, and 90 active customers.

### Deployment and data safety

- The project uses synthetic demonstration data only.
- Raw source CSV files are excluded from Git.
- Raw card numbers and CVVs must never be exposed through the public dashboard, API, or repository.
- MySQL, MongoDB, and Power BI are optional integrations requiring separate configuration.

## Limitations and safe use

- Generated values are examples; dashboard totals and trends are not evidence about real payment activity, banks, customers, or merchants.
- Amount-based anomaly flags are review signals only. No model, ground truth, or fraud determination is provided.
- The API and dashboard are demonstration applications, not production payment systems.
- MySQL SQL scripts, MongoDB examples, and the Power BI guide are optional integrations; they were not executed or validated against those products during the latest reported audit.