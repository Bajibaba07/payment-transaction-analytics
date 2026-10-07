# Final Submission Guide

## Project summary

The Payment Transaction Analytics and Business Intelligence Platform demonstrates an end-to-end analytics workflow using synthetic payment data. Python generates and validates related customer, card, merchant, and transaction datasets; pandas produces dashboard-safe tables and analysis reports; MySQL examples provide relational storage and business queries; Streamlit presents interactive analytics; and a read-only FastAPI service makes selected analytics available to other applications.

The data is synthetic and does not represent Visa, a bank, a merchant, or real customers. Amount-based anomaly flags are exploratory review signals, not fraud findings.

## Objectives

- Create reproducible synthetic datasets with referential integrity.
- Validate keys, completeness, customer/card ownership, age ranges, and transaction amounts.
- Clean and publish card-safe analytical datasets.
- Produce monthly, category, status, and amount-anomaly reports.
- Present filtered KPI and merchant/customer analyses in a browser dashboard.
- Provide documented, paginated read-only API endpoints for integration.
- Demonstrate relational analytics and deployment/automation practices.

## Architecture and data flow

```text
Faker + Python generators
          |
          v
     data/raw/
          |
          +--> validate_data.py
          |
          v
      clean_data.py
          |
          +--> data/processed/ --> Streamlit dashboard
          |                    --> FastAPI read-only API
          |                    --> Power BI / optional MongoDB
          +--> src/eda.py ------> reports/
          +--> anomaly_detection.py --> reports/
          |
          +--> sql/ ------------> MySQL schema, load, quality checks, queries
```

The generator uses fixed random seeds and a fixed synthetic reference date. Card numbers and CVVs are not generated. The processed card table also strips those columns from older input files. The API response model deliberately excludes customer identifiers, card identifiers, card numbers, CVVs, and merchant contact details.

## Main deliverables

- `src/`: data generation, validation, cleaning, EDA, and anomaly analysis.
- `data/processed/`: cleaned datasets for the dashboard and integrations.
- `reports/`: generated analytical CSV reports.
- `dashboard/app.py`: locally runnable Streamlit application.
- `api/app.py`: read-only FastAPI application and OpenAPI documentation.
- `sql/`: MySQL schema, load script, quality checks, and analysis queries.
- `docs/`: Power BI, MongoDB, and table-design documentation.
- `.github/workflows/ci.yml`: automated pipeline and test checks on GitHub.
- `render.yaml`: Render blueprint for the API service.

## Reproduce and test

From the repository root, install dependencies and run the full pipeline:

```powershell
pip install -r requirements.txt
python src/generate_customers.py
python src/generate_cards.py
python src/generate_merchants.py
python src/generate_transactions.py
python src/validate_data.py
python src/clean_data.py
python src/eda.py
python src/anomaly_detection.py
python -m unittest discover -s tests -v
```

The tested dataset contains 100 customers, 187 cards, 100 merchants, and 964 transactions. The run passed data validation and all 13 automated tests. The amount anomaly report flagged zero transactions in this run; that does not establish that the data is fraud-free.

## Run the applications

- Dashboard: `python -m streamlit run dashboard/app.py` then open `http://localhost:8501`.
- API: `python -m uvicorn api.app:app --reload` then open `http://localhost:8000/docs`.
- VS Code tasks for both applications are available from **Terminal > Run Task**.

## Limitations and interpretation

- All records are generated examples; metrics must not be interpreted as real payment-industry findings.
- A global z-score on transaction amount is a simple demonstration, not a production fraud-detection model.
- The API is read-only and has no authentication because its intended dataset is synthetic. Do not expose real customer or payment data through it.
- MySQL import and query scripts are documented examples. A MySQL server is required to execute them.
- MongoDB and Power BI are optional integration examples, not application runtime dependencies.
- Public cloud URLs do not exist until the repository is published and the hosting services are configured.

## Publication and deployment checklist

- Confirm `.venv/`, temporary files, credentials, and any older raw card exports are not staged.
- Publish the project to a GitHub repository and enable the included Actions workflow.
- Deploy `dashboard/app.py` to Streamlit Community Cloud using the root `requirements.txt`.
- Deploy the API using the included `render.yaml`; verify `/health` and `/api/v1/summary` on the resulting service URL.
- Re-run the data pipeline and tests before each final submission or dataset refresh.
- Record the repository and public service URLs in the final academic submission after deployment.
