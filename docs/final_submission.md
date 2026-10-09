# Final Submission Guide

## Project Summary

The Payment Transaction Analytics and Business Intelligence Platform is an end-to-end analytics project built using synthetic payment data.

The project demonstrates:

- Synthetic data generation using Python and Faker
- Data validation and cleaning using Python and pandas
- Relational data analysis using MySQL
- Exploratory data analysis and anomaly analysis
- Interactive analytics using Streamlit
- Read-only REST APIs using FastAPI
- Automated testing using GitHub Actions
- Cloud deployment using Streamlit Community Cloud and Render

All data is synthetic and does not represent Visa, any bank, real merchants, or real customers.

## Objectives

- Generate reproducible customer, card, merchant, and transaction datasets.
- Maintain relationships between customers, cards, merchants, and transactions.
- Validate data quality, keys, ownership, dates, and transaction amounts.
- Remove sensitive card information from analytical datasets.
- Generate business reports for transactions, categories, banks, merchants, and anomalies.
- Provide interactive dashboard-based analytics.
- Provide paginated read-only API endpoints.
- Demonstrate an end-to-end data analytics and deployment workflow.

## Architecture

```text
Python + Faker
      |
      v
  Synthetic Data
      |
      v
  data/raw/
      |
      +----> Data Validation
      |
      v
  Data Cleaning
      |
      v
data/processed/
      |
      +----> Streamlit Dashboard
      |
      +----> FastAPI
      |
      +----> Power BI
      |
      +----> MongoDB
      |
      +----> EDA Reports
      |
      +----> Anomaly Reports

MySQL
  |
  +----> Relational Storage
  +----> Data Quality Checks
  +----> Business Queries

GitHub
  |
  +----> Version Control
  +----> GitHub Actions

Cloud
  |
  +----> Streamlit Community Cloud
  +----> Render
```

## Technology Stack

| Technology | Purpose |
|---|---|
| Python | Data generation and processing |
| Faker | Synthetic payment data generation |
| pandas | Data cleaning and analysis |
| NumPy | Numerical processing |
| MySQL | Relational database and SQL analysis |
| MongoDB | Optional flexible transaction analysis |
| Streamlit | Interactive dashboard |
| FastAPI | Read-only REST API |
| Power BI | Business intelligence visualization |
| GitHub | Source control |
| GitHub Actions | Automated testing |
| Render | FastAPI deployment |
| Streamlit Community Cloud | Dashboard deployment |

## Data Model

```text
Customer
   |
   v
Card
   |
   v
Transaction
   |
   v
Merchant
```

The main datasets are:

- `customers.csv`
- `cards.csv`
- `merchants.csv`
- `transactions.csv`

The processed datasets are designed for analytical use and exclude sensitive card information.

Card numbers and CVVs are not exposed through the dashboard, API, reports, or published processed datasets.

## Project Structure

```text
payment-transaction-analytics/
|
+-- api/
|   +-- app.py
|
+-- dashboard/
|   +-- app.py
|
+-- data/
|   +-- raw/
|   +-- processed/
|
+-- docs/
|   +-- final_submission.md
|   +-- mongodb_analytics.md
|   +-- power_bi_guide.md
|
+-- reports/
|
+-- sql/
|
+-- src/
|   +-- generate_customers.py
|   +-- generate_cards.py
|   +-- generate_merchants.py
|   +-- generate_transactions.py
|   +-- validate_data.py
|   +-- clean_data.py
|   +-- eda.py
|   +-- anomaly_detection.py
|
+-- tests/
|
+-- .github/
|   +-- workflows/
|       +-- ci.yml
|
+-- requirements.txt
+-- requirements-api.txt
+-- requirements-dashboard.txt
+-- render.yaml
+-- README.md
```

## Setup

Open PowerShell in the project root.

Create and activate the virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

Install the main dependencies:

```powershell
pip install -r requirements.txt
```

For the API:

```powershell
pip install -r requirements-api.txt
```

For the dashboard:

```powershell
pip install -r requirements-dashboard.txt
```

## Generate and Process the Data

Run the following commands from the project root:

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

The pipeline generates the synthetic datasets, validates them, creates dashboard-safe processed files, and produces analytical reports.

## Run Tests

Run all automated tests:

```powershell
python -m unittest discover -s tests -v
```

A successful run should complete without test failures.

## Run the Streamlit Dashboard

Start the dashboard:

```powershell
python -m streamlit run dashboard/app.py
```

Open:

```text
http://localhost:8501
```

The dashboard provides:

- Transaction KPIs
- Transaction trends
- Completed amount by category
- Transaction status analysis
- Bank and card analysis
- Top customers
- Merchant failure analysis
- Filtered transaction records

Select a merchant category from the sidebar to display the analytics.

## Run the FastAPI Service

Start the API:

```powershell
python -m uvicorn api.app:app --reload
```

Open the API documentation:

```text
http://localhost:8000/docs
```

Available endpoints include:

```text
GET /
GET /health
GET /api/v1/summary
GET /api/v1/categories
GET /api/v1/banks
GET /api/v1/merchants
GET /api/v1/transactions
```

The API is read-only and provides analytical information without exposing sensitive card data.

## MySQL

The repository includes MySQL schema, loading, quality-check, and query examples. These are optional and were not executed as part of this audit.

The SQL directory contains:

- Database schema
- Table definitions
- Data loading scripts
- Data quality checks
- Business analysis queries

A MySQL server is required to execute the SQL scripts. The scripts were reviewed but not run against a MySQL server during this audit.

## Power BI

The processed analytical datasets can be connected to Power BI to create business intelligence reports. The Power BI guide is documentation only; no Power BI model, connection, or report was validated during this audit.

Recommended analysis includes:

- Transaction volume
- Completed transaction amount
- Success rate
- Category performance
- Bank performance
- Merchant performance
- Monthly trends

## MongoDB

MongoDB is an optional integration for flexible transaction exploration.

It is not required for the Streamlit dashboard or FastAPI application.

## Anomaly Detection

The project includes amount-based anomaly detection using a statistical z-score approach.

The anomaly result is intended as a review signal for unusually large transaction amounts.

It is not a production fraud-detection system and must not be interpreted as proof of fraud.

## Deployment

### Streamlit

For Streamlit Community Cloud, deploy the existing `master` branch and use this application file as the entrypoint:

```text
dashboard/app.py
```

The root `requirements.txt` declares the Streamlit and pandas dependencies; Streamlit Community Cloud supports this root-level dependency file. The dashboard's required safe CSVs are tracked under `data/processed/`. Do not configure `requirements-api.txt` as the dashboard's only dependency file.

### FastAPI

The Render deployment configuration is defined in the existing blueprint:

```text
render.yaml
```

The build command creates `data/raw/` and `data/processed/`, installs `requirements-api.txt`, then runs the customer, card, merchant, and transaction generators in order, followed by validation and cleaning. The service targets Python 3.12.8.

The Render service starts the API using:

```text
uvicorn api.app:app --host 0.0.0.0 --port $PORT
```

After deployment, verify:

```text
/health
/api/v1/summary
/api/v1/categories
/api/v1/banks
/api/v1/merchants
/api/v1/transactions
```

Render regenerates the synthetic datasets during each build. The direct generator/runtime dependencies are pinned in `requirements-api.txt`; redeploy after dependency changes, then compare record-level data with the local generated CSVs. Aggregate parity alone does not prove exact dataset parity.

The Render health endpoint returned HTTP 503 during this audit. The Streamlit URL redirected to an authentication page, so public dashboard availability could not be confirmed. No live deployment URL is claimed; manually check service logs, redeploy if needed, and verify `/health` and all documented routes before publishing links.

## Testing Checklist

Before final submission, verify:

```text
[ ] Python environment works
[ ] Dependencies are installed
[ ] Data generation completes
[ ] Data validation passes
[ ] Data cleaning completes
[ ] EDA reports are generated
[ ] Anomaly report is generated
[ ] All automated tests pass
[ ] Streamlit dashboard opens
[ ] Dashboard filters work
[ ] FastAPI starts successfully
[ ] /health returns status OK
[ ] API endpoints return data
[ ] GitHub repository is updated
[ ] GitHub Actions passes
[ ] Streamlit deployment works
[ ] Render deployment works
[ ] No credentials are committed
[ ] Raw sensitive card data is not published
```

## Final Data Snapshot

The validated local dataset currently contains:

- 100 customers
- 187 cards
- 100 merchants
- 964 transactions

The current processed dataset is synthetic and intended only for demonstration and academic purposes.

## Project Limitations

- The payment data is synthetic.
- The anomaly detector is a statistical demonstration, not a production fraud model.
- The API is read-only.
- The API does not use authentication because the project uses synthetic data.
- MySQL requires a separately installed and running MySQL server.
- MongoDB and Power BI are optional integrations.
- Cloud deployments depend on the latest successfully deployed project version.
- This audit used local Python 3.14.4; CI and Render target Python 3.12.8, so that exact runtime was not tested locally.
- No MySQL client/server was available during this audit, so the SQL scripts were not executed.
- The live Render API returned HTTP 503 and the Streamlit public page could not be confirmed during this audit.

## Final Verification Commands

Run these commands before submitting the project:

```powershell
python src/generate_customers.py
python src/generate_cards.py
python src/generate_merchants.py
python src/generate_transactions.py
python src/validate_data.py
python src/clean_data.py
python src/eda.py
python src/anomaly_detection.py
python -m compileall src api dashboard tests
python -m unittest discover -s tests -v
```

Then start the applications:

```powershell
python -m streamlit run dashboard/app.py
```

In another terminal:

```powershell
python -m uvicorn api.app:app --reload
```

The raw datasets passed validation at the expected counts, and the local unit tests and compilation checks passed. The hosted deployments remain unverified; the Render 503 and Streamlit access state require manual follow-up. MySQL execution and Power BI validation were not performed.