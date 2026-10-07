# Payment Transaction Analytics and Business Intelligence Platform

This portfolio project demonstrates a complete workflow using synthetic payment data: generation, validation, Python cleaning and EDA, SQL analytics, optional MongoDB aggregations, Power BI modeling, and explainable business insights. It does not represent real Visa, bank, or customer data.

## Data model

The relationship chain is `Customer -> Card -> Transaction -> Merchant`.

- `data/raw/` contains generated source CSV files.
- `data/processed/` contains typed, deduplicated, dashboard-safe files.
- `reports/` contains reproducible summary tables and anomaly flags.
- `sql/` contains the MySQL schema and business queries.
- `docs/` contains table, MongoDB, and Power BI documentation.

The card generator produces dashboard-safe card data and does not create card numbers or CVVs. The cleaner also removes those columns if they appear in an older raw file. The API, SQL schema, MongoDB export, and Power BI model use only dashboard-safe fields.

## Setup

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Reproduce the pipeline

Run from the project root. The generation order preserves foreign keys.

```powershell
python src/generate_customers.py
python src/generate_cards.py
python src/generate_merchants.py
python src/generate_transactions.py
python src/validate_data.py
python src/clean_data.py
python src/eda.py
python src/anomaly_detection.py
```

`validate_data.py` exits with status 1 when keys, completeness, relationships, customer ages, or amounts are invalid. All data generators use fixed random seeds and a fixed synthetic reference date so repeated runs produce the same datasets, including globally unique transaction IDs. Run the validation suite with `python -m unittest discover -s tests -v`; it covers data cleaning and validation, API response privacy and behavior, and dashboard data readiness.

GitHub Actions runs the full data-generation and report pipeline and the same automated tests on every push and pull request.

## MySQL

1. From PowerShell, run `Get-Content -Raw sql/01_schema.sql | mysql -u root -p`.
2. From the project root, run `Get-Content -Raw sql/03_load_processed_data.sql | mysql --local-infile=1 -u root -p`. This intentionally replaces data in the dedicated `payment_analytics` tables; do not run it against a database containing user-owned data.
3. Run `Get-Content -Raw sql/04_quality_checks.sql | mysql -u root -p` and confirm the loaded row counts match `src/validate_data.py` and all relationship checks report zero invalid links.
4. Run `Get-Content -Raw sql/02_business_queries.sql | mysql -u root -p` for KPI, trend, category, customer, merchant-risk, and bank analysis.

MySQL is the relational layer because foreign keys and repeatable joins are central to this project.

## MongoDB

MongoDB is optional and limited to flexible transaction exploration. Follow `docs/mongodb_analytics.md` to create a dashboard-safe JSON export and run aggregation pipelines. It is not used as a replacement for the relational model.

## Power BI

Import the processed CSV files and follow `docs/power_bi_guide.md` for relationships, page design, privacy boundaries, and DAX measures. Suggested pages are Executive Overview, Product and Bank, and Customer and Merchant.

## Runnable dashboard

The project also includes a Streamlit dashboard in `dashboard/app.py`. It reads only the processed files, supports category/status/bank filters, and displays KPI cards, trends, category performance, status analysis, bank/card analysis, top customers, and merchant failure rates.

Install the project dependencies and run locally from the project root:

```powershell
pip install -r requirements.txt
python -m streamlit run dashboard/app.py
```

Open `http://localhost:8501`. The local dashboard has been smoke-tested successfully on port 8501.

In VS Code, use **Terminal > Run Task > Run Payment Analytics Dashboard** to start the dashboard, or **Run Payment Analytics API** to start the API. The tasks use the workspace virtual environment and bind to localhost.

To deploy on Streamlit Community Cloud, push this repository to GitHub and choose `dashboard/app.py` as the main file. The root `requirements.txt` includes the dashboard dependencies. The app expects the processed CSVs to be in the repository; rerun the pipeline and publish regenerated processed data when you want to refresh the dashboard.

## Read-only API for other applications

The project includes a public, read-only FastAPI service backed by the processed synthetic transactions. It does not load raw card data or merchant contact details, and it never returns card numbers, CVVs, or customer IDs. Generate processed data using the pipeline above, then start the API from the project root:

```powershell
pip install -r requirements.txt
python -m uvicorn api.app:app --reload
```

Open `http://localhost:8000/docs` for interactive API documentation. Available endpoints:

- `GET /api/v1/summary`
- `GET /api/v1/transactions?limit=50&offset=0&category=Retail&status=Completed&bank=HDFC%20Bank`
- `GET /api/v1/categories`
- `GET /api/v1/banks`
- `GET /api/v1/merchants?limit=20`
- `GET /health`

The transactions endpoint defaults to 50 records per page and caps pages at 100. Filters are optional and case-insensitive. All endpoints are GET-only. Browser-based clients are allowed by default; set `API_ALLOWED_ORIGINS` to a comma-separated list of trusted origins when deploying the API for a specific frontend.

To make the API reachable by other people, push the project to GitHub and create a Render Web Service from that repository. The included `render.yaml` installs the API dependencies, generates and validates fresh synthetic data during the build, cleans it into the dashboard-safe dataset, and starts the API. Once deployed, use the Render service URL in clients (for example, `<service-url>/api/v1/summary`). Older versions of `data/raw/cards.csv` are ignored by Git as a precaution; the current generator no longer creates card numbers or CVVs.

## How to explain the project

The analysis answers four practical questions: how payment activity changes over time, which categories and banks drive completed amount, where failures concentrate, and which customers or merchants require attention. The anomaly script uses a transparent amount z-score as a review signal; it is not a fraud verdict. Business claims should be calculated from the current generated files or database outputs rather than hard-coded in documentation.

See [docs/final_submission.md](docs/final_submission.md) for the project summary, architecture, reproducible checks, limitations, and final publication checklist.

## Technology roles

- Python, Pandas, and Faker generate and prepare synthetic data.
- MySQL enforces relational structure and answers repeatable business questions.
- MongoDB demonstrates document aggregations where flexible grouping is useful.
- Power BI and DAX turn processed fact and dimension tables into interactive KPIs.
- Reports are analyst-facing outputs and do not expose sensitive-looking card fields.
