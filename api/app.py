"""Read-only API for the project's synthetic payment analytics."""

import os
from functools import lru_cache
from pathlib import Path

import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel


ROOT = Path(__file__).resolve().parents[1]
TRANSACTIONS_PATH = ROOT / "data" / "processed" / "transactions_clean.csv"
REQUIRED_COLUMNS = {
    "transaction_id",
    "customer_id",
    "merchant_id",
    "merchant_name",
    "merchant_category",
    "transaction_date",
    "amount",
    "currency",
    "transaction_type",
    "transaction_status",
    "payment_method",
    "merchant_city",
    "merchant_state",
    "bank_name",
    "card_type",
    "is_successful",
    "is_failure",
}

app = FastAPI(
    title="Payment Analytics API",
    description="Read-only analytics from synthetic payment transactions.",
    version="1.0.0",
)

allowed_origins = [
    origin.strip()
    for origin in os.getenv("API_ALLOWED_ORIGINS", "*").split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_methods=["GET"],
    allow_headers=["*"],
)


class TransactionRecord(BaseModel):
    transaction_id: str
    merchant_id: str
    merchant_name: str
    merchant_category: str
    transaction_date: str
    amount: float
    currency: str
    transaction_type: str
    transaction_status: str
    payment_method: str
    merchant_city: str
    merchant_state: str
    bank_name: str
    card_type: str


class TransactionPage(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[TransactionRecord]


class Summary(BaseModel):
    total_transactions: int
    completed_transactions: int
    completed_amount: float
    success_rate: float
    active_customers: int
    currency: str


class CategorySummary(BaseModel):
    category: str
    transaction_count: int
    completed_amount: float


class BankSummary(BaseModel):
    bank_name: str
    transaction_count: int
    completed_transactions: int
    completed_amount: float


class MerchantSummary(BaseModel):
    merchant_id: str
    merchant_name: str
    merchant_category: str
    transaction_count: int
    failure_rate: float
    completed_amount: float


@lru_cache(maxsize=1)
def _load_transactions(_modified_ns: int, _file_size: int) -> pd.DataFrame:
    if not TRANSACTIONS_PATH.is_file():
        raise HTTPException(
            status_code=503,
            detail="Processed transaction data is missing. Run src/clean_data.py first.",
        )

    transactions = pd.read_csv(TRANSACTIONS_PATH)
    missing_columns = REQUIRED_COLUMNS.difference(transactions.columns)
    if missing_columns:
        raise HTTPException(
            status_code=503,
            detail=(
                "Processed transaction data is incomplete. "
                f"Missing columns: {', '.join(sorted(missing_columns))}."
            ),
        )
    return transactions


def load_transactions() -> pd.DataFrame:
    try:
        file_stats = TRANSACTIONS_PATH.stat()
    except FileNotFoundError as error:
        raise HTTPException(
            status_code=503,
            detail="Processed transaction data is missing. Run src/clean_data.py first.",
        ) from error
    return _load_transactions(file_stats.st_mtime_ns, file_stats.st_size)


def completed_amount(transactions: pd.DataFrame) -> float:
    amount = transactions.loc[transactions["is_successful"], "amount"].sum()
    return round(float(amount), 2)


@app.get("/", tags=["info"])
def root():
    return {
        "name": "Payment Analytics API",
        "docs": "/docs",
        "openapi": "/openapi.json",
        "synthetic_data_only": True,
    }


@app.get("/health", tags=["info"])
def health():
    load_transactions()
    return {"status": "ok", "data_available": True}


@app.get("/api/v1/summary", response_model=Summary, tags=["analytics"])
def get_summary():
    transactions = load_transactions()
    total = len(transactions)
    successful = int(transactions["is_successful"].sum())
    return Summary(
        total_transactions=total,
        completed_transactions=successful,
        completed_amount=completed_amount(transactions),
        success_rate=successful / total if total else 0.0,
        active_customers=int(transactions["customer_id"].nunique()),
        currency=str(transactions["currency"].mode().iloc[0])
        if total
        else "INR",
    )


@app.get(
    "/api/v1/transactions",
    response_model=TransactionPage,
    tags=["transactions"],
)
def get_transactions(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    category: str | None = None,
    status: str | None = None,
    bank: str | None = None,
):
    transactions = load_transactions()
    filtered = transactions
    for column, value in (
        ("merchant_category", category),
        ("transaction_status", status),
        ("bank_name", bank),
    ):
        if value:
            filtered = filtered[
                filtered[column].astype("string").str.lower() == value.strip().lower()
            ]

    rows = filtered.iloc[offset : offset + limit]
    items = [
        TransactionRecord(
            transaction_id=str(row["transaction_id"]),
            merchant_id=str(row["merchant_id"]),
            merchant_name=str(row["merchant_name"]),
            merchant_category=str(row["merchant_category"]),
            transaction_date=str(row["transaction_date"]),
            amount=float(row["amount"]),
            currency=str(row["currency"]),
            transaction_type=str(row["transaction_type"]),
            transaction_status=str(row["transaction_status"]),
            payment_method=str(row["payment_method"]),
            merchant_city=str(row["merchant_city"]),
            merchant_state=str(row["merchant_state"]),
            bank_name=str(row["bank_name"]),
            card_type=str(row["card_type"]),
        )
        for _, row in rows.iterrows()
    ]
    return TransactionPage(
        total=len(filtered),
        limit=limit,
        offset=offset,
        items=items,
    )


@app.get(
    "/api/v1/categories",
    response_model=list[CategorySummary],
    tags=["analytics"],
)
def get_categories():
    transactions = load_transactions()
    grouped = transactions.groupby("merchant_category", sort=True)
    return [
        CategorySummary(
            category=str(category),
            transaction_count=len(group),
            completed_amount=completed_amount(group),
        )
        for category, group in grouped
    ]


@app.get("/api/v1/banks", response_model=list[BankSummary], tags=["analytics"])
def get_banks():
    transactions = load_transactions()
    grouped = transactions.groupby("bank_name", sort=True)
    return [
        BankSummary(
            bank_name=str(bank),
            transaction_count=len(group),
            completed_transactions=int(group["is_successful"].sum()),
            completed_amount=completed_amount(group),
        )
        for bank, group in grouped
    ]


@app.get(
    "/api/v1/merchants",
    response_model=list[MerchantSummary],
    tags=["analytics"],
)
def get_merchants(limit: int = Query(default=20, ge=1, le=100)):
    transactions = load_transactions()
    grouped = transactions.groupby(
        ["merchant_id", "merchant_name", "merchant_category"], sort=True
    )
    merchants = [
        MerchantSummary(
            merchant_id=str(merchant_id),
            merchant_name=str(merchant_name),
            merchant_category=str(category),
            transaction_count=len(group),
            failure_rate=float(group["is_failure"].mean()),
            completed_amount=completed_amount(group),
        )
        for (merchant_id, merchant_name, category), group in grouped
    ]
    return sorted(
        merchants,
        key=lambda merchant: merchant.completed_amount,
        reverse=True,
    )[:limit]
