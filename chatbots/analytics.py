"""Privacy-preserving analytics over aggregate payment transaction data."""

from collections.abc import Mapping
from dataclasses import dataclass
import math
from pathlib import Path
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import urlopen
import json
import re

import pandas as pd

from chatbots.ai_provider import redact_sensitive_input, validate_chat_input

ROOT = Path(__file__).resolve().parents[1]
TRANSACTIONS_PATH = ROOT / "data" / "processed" / "transactions_clean.csv"
SAFE_COLUMNS = (
    "merchant_category",
    "merchant_name",
    "transaction_status",
    "transaction_month",
    "amount",
    "currency",
    "bank_name",
    "is_successful",
    "is_failure",
)
API_TIMEOUT_SECONDS = 10


class AnalyticsDataError(RuntimeError):
    """Raised when processed or API analytics data is invalid or unavailable."""


@dataclass(frozen=True)
class BankMetrics:
    name: str
    transaction_count: int
    completed_transactions: int
    completed_amount: float
    success_rate: float
    failed_transactions: int | None = None


@dataclass(frozen=True)
class MerchantMetrics:
    name: str
    category: str
    transaction_count: int
    failure_rate: float
    completed_amount: float
    failed_transactions: int | None = None


@dataclass(frozen=True)
class CategoryMetrics:
    name: str
    transaction_count: int
    completed_amount: float
    failed_transactions: int | None = None
    failure_rate: float | None = None


@dataclass(frozen=True)
class MonthlyMetrics:
    month: str
    transaction_count: int
    completed_transactions: int
    failed_transactions: int
    completed_amount: float


@dataclass(frozen=True)
class AnalyticsSnapshot:
    total_transactions: int
    completed_transactions: int
    completed_amount: float
    success_rate: float
    currency: str
    banks: tuple[BankMetrics, ...]
    merchants: tuple[MerchantMetrics, ...]
    categories: tuple[CategoryMetrics, ...]
    failed_transactions: int | None
    monthly_trends: tuple[MonthlyMetrics, ...] | None


def _successful_values(values: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(values.dtype):
        return values.fillna(False)

    parsed = values.astype("string").str.strip().str.lower()
    valid = parsed.isin({"true", "false", "1", "0"})
    if not valid.all():
        raise AnalyticsDataError(
            "Processed data contains invalid is_successful values."
        )
    return parsed.isin({"true", "1"})


def _boolean_values(values: pd.Series, column: str) -> pd.Series:
    try:
        return _successful_values(values)
    except AnalyticsDataError as error:
        raise AnalyticsDataError(
            f"Processed data contains invalid {column} values."
        ) from error


def _group_amount(group: pd.DataFrame) -> float:
    return round(
        float(group.loc[group["_successful"], "amount"].sum()),
        2,
    )


def snapshot_from_dataframe(transactions: pd.DataFrame) -> AnalyticsSnapshot:
    missing = set(SAFE_COLUMNS).difference(transactions.columns)
    if missing:
        raise AnalyticsDataError(
            "Processed transaction data is missing required analytics fields: "
            + ", ".join(sorted(missing))
        )

    safe = transactions.loc[:, SAFE_COLUMNS].copy()
    safe["amount"] = pd.to_numeric(safe["amount"], errors="coerce")
    amounts = safe["amount"].tolist()
    if any(
        pd.isna(amount) or not math.isfinite(float(amount)) or amount <= 0
        for amount in amounts
    ):
        raise AnalyticsDataError(
            "Processed transaction data contains invalid amounts."
        )
    safe["_successful"] = _boolean_values(safe["is_successful"], "is_successful")
    safe["_failure"] = _boolean_values(safe["is_failure"], "is_failure")
    statuses = safe["transaction_status"].astype("string").str.strip()
    if statuses.isna().any() or statuses.eq("").any():
        raise AnalyticsDataError(
            "Processed transaction data contains invalid statuses."
        )
    safe["_failed"] = statuses.str.casefold().eq("failed")
    months = safe["transaction_month"].astype("string").str.strip()
    if months.isna().any() or not months.str.fullmatch(r"\d{4}-\d{2}").all():
        raise AnalyticsDataError(
            "Processed transaction data contains invalid transaction months."
        )
    safe["_month"] = months
    safe["_amount"] = safe["amount"].astype(float)
    total = len(safe)
    completed = int(safe["_successful"].sum())
    currency = (
        str(safe["currency"].mode().iloc[0])
        if total and not safe["currency"].mode().empty
        else "INR"
    )

    banks = tuple(
        BankMetrics(
            name=str(name),
            transaction_count=len(group),
            completed_transactions=int(group["_successful"].sum()),
            completed_amount=_group_amount(group),
            success_rate=(
                float(group["_successful"].mean()) if len(group) else 0.0
            ),
            failed_transactions=int(group["_failed"].sum()),
        )
        for name, group in safe.groupby("bank_name", sort=True, dropna=False)
    )
    merchants = tuple(
        MerchantMetrics(
            name=str(name),
            category=str(category),
            transaction_count=len(group),
            failure_rate=float(group["_failure"].mean()),
            completed_amount=_group_amount(group),
            failed_transactions=int(group["_failure"].sum()),
        )
        for (name, category), group in safe.groupby(
            ["merchant_name", "merchant_category"],
            sort=True,
            dropna=False,
        )
    )
    categories = tuple(
        CategoryMetrics(
            name=str(name),
            transaction_count=len(group),
            completed_amount=_group_amount(group),
            failed_transactions=int(group["_failure"].sum()),
            failure_rate=float(group["_failure"].mean()),
        )
        for name, group in safe.groupby(
            "merchant_category", sort=True, dropna=False
        )
    )
    monthly_trends = tuple(
        MonthlyMetrics(
            month=str(month),
            transaction_count=len(group),
            completed_transactions=int(group["_successful"].sum()),
            failed_transactions=int(group["_failed"].sum()),
            completed_amount=_group_amount(group),
        )
        for month, group in safe.groupby("_month", sort=True)
    )

    return AnalyticsSnapshot(
        total_transactions=total,
        completed_transactions=completed,
        completed_amount=_group_amount(safe),
        success_rate=float(completed / total) if total else 0.0,
        currency=currency,
        banks=banks,
        merchants=merchants,
        categories=categories,
        failed_transactions=int(safe["_failed"].sum()),
        monthly_trends=monthly_trends,
    )


def _get_json(api_base_url: str, path: str) -> object:
    parsed = urlsplit(api_base_url)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.netloc
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise AnalyticsDataError(
            "PAYMENT_ANALYTICS_API_URL must be an HTTP(S) base URL."
        )
    url = api_base_url.rstrip("/") + path
    try:
        with urlopen(url, timeout=API_TIMEOUT_SECONDS) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        raise AnalyticsDataError(
            f"The analytics API returned HTTP {error.code}."
        ) from error
    except (URLError, TimeoutError) as error:
        raise AnalyticsDataError("The analytics API request failed.") from error
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise AnalyticsDataError(
            "The analytics API returned invalid JSON."
        ) from error


def _read_object(payload: object, required: set[str], endpoint: str) -> dict:
    if not isinstance(payload, dict) or not required.issubset(payload):
        raise AnalyticsDataError(
            f"The analytics API returned an invalid {endpoint} response."
        )
    return payload


def _read_list(payload: object, endpoint: str) -> list[dict]:
    if not isinstance(payload, list) or any(
        not isinstance(item, dict) for item in payload
    ):
        raise AnalyticsDataError(
            f"The analytics API returned an invalid {endpoint} response."
        )
    return payload


def snapshot_from_api(api_base_url: str) -> AnalyticsSnapshot:
    summary = _read_object(
        _get_json(api_base_url, "/api/v1/summary"),
        {
            "total_transactions",
            "completed_transactions",
            "completed_amount",
            "success_rate",
            "currency",
        },
        "summary",
    )
    raw_banks = _read_list(
        _get_json(api_base_url, "/api/v1/banks"), "banks"
    )
    raw_merchants = _read_list(
        _get_json(api_base_url, "/api/v1/merchants?limit=100"), "merchants"
    )
    raw_categories = _read_list(
        _get_json(api_base_url, "/api/v1/categories"), "categories"
    )

    try:
        banks = tuple(
            BankMetrics(
                name=str(item["bank_name"]),
                transaction_count=int(item["transaction_count"]),
                completed_transactions=int(item["completed_transactions"]),
                completed_amount=round(float(item["completed_amount"]), 2),
                success_rate=(
                    int(item["completed_transactions"])
                    / int(item["transaction_count"])
                    if int(item["transaction_count"])
                    else 0.0
                ),
            )
            for item in raw_banks
        )
        merchants = tuple(
            MerchantMetrics(
                name=str(item["merchant_name"]),
                category=str(item["merchant_category"]),
                transaction_count=int(item["transaction_count"]),
                failure_rate=float(item["failure_rate"]),
                completed_amount=round(float(item["completed_amount"]), 2),
            )
            for item in raw_merchants
        )
        categories = tuple(
            CategoryMetrics(
                name=str(item["category"]),
                transaction_count=int(item["transaction_count"]),
                completed_amount=round(float(item["completed_amount"]), 2),
            )
            for item in raw_categories
        )
        return AnalyticsSnapshot(
            total_transactions=int(summary["total_transactions"]),
            completed_transactions=int(summary["completed_transactions"]),
            completed_amount=round(float(summary["completed_amount"]), 2),
            success_rate=float(summary["success_rate"]),
            currency=str(summary["currency"]),
            banks=banks,
            merchants=merchants,
            categories=categories,
            failed_transactions=None,
            monthly_trends=None,
        )
    except (KeyError, TypeError, ValueError, ZeroDivisionError) as error:
        raise AnalyticsDataError(
            "The analytics API returned invalid aggregate values."
        ) from error


def load_snapshot(
    data_path: Path = TRANSACTIONS_PATH,
    api_base_url: str | None = None,
) -> AnalyticsSnapshot:
    if api_base_url and api_base_url.strip():
        return snapshot_from_api(api_base_url.strip())

    try:
        transactions = pd.read_csv(data_path, usecols=list(SAFE_COLUMNS))
    except FileNotFoundError as error:
        raise AnalyticsDataError(
            "Processed transaction data is missing."
        ) from error
    except (OSError, ValueError, pd.errors.ParserError) as error:
        raise AnalyticsDataError(
            "Processed transaction data could not be read."
        ) from error
    return snapshot_from_dataframe(transactions)


def _verified_answer(
    question: str,
    snapshot: AnalyticsSnapshot,
    history: tuple[dict, ...] = (),
) -> tuple[str, str, dict] | None:
    lower = re.sub(r"[^\w%]+", " ", question.casefold()).strip()
    if re.search(
        r"\b(?:my|mine|individual|specific)\b.*\b(?:payment|transaction)\b",
        lower,
    ) or re.search(r"\b(?:payment|transaction)\s+(?:id|reference)\b", lower):
        return None

    failed_question = re.search(
        r"\b(?:fail(?:ed|ure|ures)?|declined|unsuccessful)\b", lower
    ) is not None
    failed_rate_question = failed_question and re.search(
        r"\b(?:rate|percentage|percent)\b", lower
    ) is not None
    if failed_question and any(
        word in lower.split()
        for word in (
            "amount",
            "value",
            "money",
            "debit",
            "debited",
            "cost",
            "costs",
            "charged",
        )
    ):
        return (
            "failed_payment_amount_unavailable",
            "The available analytics can count failed transactions, but they "
            "do not verify how much money was actually debited. No debited "
            "amount can be inferred from failed transaction amounts.",
            {},
        )

    compare_requested = re.search(
        r"\b(?:compare|versus|vs|difference between)\b", lower
    ) is not None
    mentioned_banks = [
        item for item in snapshot.banks if item.name.casefold() in lower
    ]
    mentioned_merchants = [
        item for item in snapshot.merchants if item.name.casefold() in lower
    ]
    mentioned_categories = [
        item for item in snapshot.categories if item.name.casefold() in lower
    ]
    if compare_requested:
        if "bank" in lower or len(mentioned_banks) > 1:
            banks = mentioned_banks or list(snapshot.banks)
            if failed_question and any(
                item.failed_transactions is None for item in banks
            ):
                return (
                    "bank_failures_unavailable",
                    "The configured aggregate analytics API does not provide "
                    "failed-payment totals by bank. No comparison has been "
                    "inferred.",
                    {},
                )
            rows = [
                {
                    "bank": item.name,
                    "transaction_count": item.transaction_count,
                    "completed_transactions": item.completed_transactions,
                    "completed_amount": item.completed_amount,
                    "success_rate": item.success_rate,
                    "failed_transactions": item.failed_transactions,
                    "failure_rate": (
                        item.failed_transactions / item.transaction_count
                        if item.transaction_count
                        else 0.0
                    )
                    if item.failed_transactions is not None
                    else None,
                    "currency": snapshot.currency,
                }
                for item in banks
            ]
            if rows:
                if failed_question:
                    if failed_rate_question:
                        answer = "Bank failure-rate comparison: " + "; ".join(
                            f"{item['bank']}: {item['failure_rate']:.2%}"
                            for item in rows
                        )
                    else:
                        answer = "Failed-payment comparison: " + "; ".join(
                            f"{item['bank']}: "
                            f"{item['failed_transactions']:,} of "
                            f"{item['transaction_count']:,} failed"
                            for item in rows
                        )
                else:
                    answer = "Bank comparison: " + "; ".join(
                        f"{item['bank']}: {item['success_rate']:.2%} success, "
                        f"{item['transaction_count']:,} transactions, "
                        f"completed amount {snapshot.currency} "
                        f"{item['completed_amount']:,.2f}"
                        for item in rows
                    )
                return "bank_comparison", answer, {"banks": rows}

        if "merchant" in lower or len(mentioned_merchants) > 1:
            if failed_question and not failed_rate_question and any(
                item.failed_transactions is None
                for item in (mentioned_merchants or snapshot.merchants)
            ):
                return (
                    "merchant_failures_unavailable",
                    "The configured aggregate analytics API does not provide "
                    "failed-payment totals by merchant. No comparison has "
                    "been inferred.",
                    {},
                )
            rows = [
                {
                    "merchant": item.name,
                    "category": item.category,
                    "transaction_count": item.transaction_count,
                    "failure_rate": item.failure_rate,
                    "completed_amount": item.completed_amount,
                    "failed_transactions": item.failed_transactions,
                    "currency": snapshot.currency,
                }
                for item in (mentioned_merchants or list(snapshot.merchants))
            ]
            if rows:
                if failed_question and not failed_rate_question:
                    answer = "Failed-payment comparison: " + "; ".join(
                        f"{item['merchant']}: "
                        f"{item['failed_transactions']:,} failed"
                        for item in rows
                    )
                else:
                    answer = "Merchant comparison: " + "; ".join(
                        f"{item['merchant']}: {item['transaction_count']:,} "
                        f"transactions, {item['failure_rate']:.2%} "
                        f"failure rate, completed amount {snapshot.currency} "
                        f"{item['completed_amount']:,.2f}"
                        for item in rows
                    )
                return "merchant_comparison", answer, {"merchants": rows}

        if "categor" in lower or len(mentioned_categories) > 1:
            comparison_categories = (
                mentioned_categories or list(snapshot.categories)
            )
            if failed_rate_question and any(
                item.failure_rate is None for item in comparison_categories
            ):
                return (
                    "category_failure_rate_unavailable",
                    "The configured aggregate analytics API does not provide "
                    "failed-payment rates by category. No comparison has "
                    "been inferred.",
                    {},
                )
            if failed_question and not failed_rate_question and any(
                item.failed_transactions is None for item in comparison_categories
            ):
                return (
                    "category_failures_unavailable",
                    "The configured aggregate analytics API does not provide "
                    "failed-payment totals by category. No comparison has "
                    "been inferred.",
                    {},
                )
            rows = [
                {
                    "category": item.name,
                    "transaction_count": item.transaction_count,
                    "completed_amount": item.completed_amount,
                    "failed_transactions": item.failed_transactions,
                    "failure_rate": item.failure_rate,
                    "currency": snapshot.currency,
                }
                for item in comparison_categories
            ]
            if rows:
                if failed_question and not failed_rate_question:
                    answer = "Failed-payment comparison: " + "; ".join(
                        f"{item['category']}: "
                        f"{item['failed_transactions']:,} failed"
                        for item in rows
                    )
                elif failed_rate_question:
                    answer = "Category failure-rate comparison: " + "; ".join(
                        f"{item['category']}: {item['failure_rate']:.2%}"
                        for item in rows
                    )
                else:
                    answer = "Category comparison: " + "; ".join(
                        f"{item['category']}: {item['transaction_count']:,} "
                        f"transactions, completed amount {snapshot.currency} "
                        f"{item['completed_amount']:,.2f}"
                        for item in rows
                    )
                return "category_comparison", answer, {"categories": rows}

    if any(
        word in lower for word in ("trend", "over time", "monthly", "month")
    ):
        if snapshot.monthly_trends is None:
            return (
                "monthly_trends_unavailable",
                "The configured aggregate analytics API does not provide "
                "monthly trend data. No trend has been inferred.",
                {},
            )
        trend_rows = [
            {
                "month": item.month,
                "transaction_count": item.transaction_count,
                "completed_transactions": item.completed_transactions,
                "failed_transactions": item.failed_transactions,
                "completed_amount": item.completed_amount,
                "currency": snapshot.currency,
            }
            for item in snapshot.monthly_trends
        ]
        answer = "Monthly transaction trends: " + "; ".join(
            f"{item.month}: {item.transaction_count:,} transactions, "
            f"{item.completed_transactions:,} completed, "
            f"{item.failed_transactions:,} failed, completed amount "
            f"{snapshot.currency} {item.completed_amount:,.2f}"
            for item in snapshot.monthly_trends
        )
        return "monthly_trends", answer, {"months": trend_rows}

    bank = next(
        (item for item in snapshot.banks if item.name.casefold() in lower),
        None,
    )
    if bank is None and re.search(
        r"\b(?:there|that bank|same bank|its|it)\b", lower
    ):
        bank = next(
            (
                item
                for message in reversed(history)
                if isinstance(message.get("content"), str)
                for item in snapshot.banks
                if item.name.casefold() in message["content"].casefold()
            ),
            None,
        )
    if bank is None and re.search(
        r"\b(?:there|that one|same one|it|its|they|those)\b", lower
    ):
        for message in reversed(history):
            content = message.get("content")
            if not isinstance(content, str):
                continue
            prior_banks = [
                item
                for item in snapshot.banks
                if item.name.casefold() in content.casefold()
            ]
            if len(prior_banks) == 1:
                bank = prior_banks[0]
                break
            if prior_banks:
                break
    if bank is not None and failed_question:
        if bank.failed_transactions is None:
            return (
                "bank_failures_unavailable",
                f"The configured aggregate analytics API does not provide "
                f"an exact failed-payment count for {bank.name}. No count "
                "has been inferred.",
                {},
            )
        failure_rate = (
            bank.failed_transactions / bank.transaction_count
            if bank.transaction_count
            else 0.0
        )
        answer = (
            f"{bank.name} had {bank.failed_transactions:,} failed of "
            f"{bank.transaction_count:,} transactions "
            f"({failure_rate:.2%})."
        )
        return "bank_failures", answer, {
            "bank": bank.name,
            "failed_transactions": bank.failed_transactions,
            "transaction_count": bank.transaction_count,
            "failure_rate": failure_rate,
        }

    if bank is not None:
        answer = (
            f"{bank.name}: {bank.completed_transactions:,} of "
            f"{bank.transaction_count:,} transactions completed "
            f"({bank.success_rate:.2%}); completed amount "
            f"{snapshot.currency} {bank.completed_amount:,.2f}."
        )
        return "bank_metrics", answer, {
            "bank": bank.name,
            "transaction_count": bank.transaction_count,
            "completed_transactions": bank.completed_transactions,
            "completed_amount": bank.completed_amount,
            "success_rate": bank.success_rate,
            "failed_transactions": bank.failed_transactions,
            "currency": snapshot.currency,
        }

    if any(word in lower.split() for word in ("most", "highest", "top", "best")):
        if "bank" in lower:
            if failed_question:
                if any(
                    item.failed_transactions is None
                    for item in snapshot.banks
                ):
                    return (
                        "bank_failures_unavailable",
                        "The configured aggregate analytics API does not "
                        "provide failed-payment totals by bank. No ranking "
                        "has been inferred.",
                        {},
                    )
                ranked_failures = sorted(
                    snapshot.banks,
                    key=lambda item: (
                        item.failed_transactions or 0,
                        item.name,
                    ),
                    reverse=True,
                )
                if ranked_failures:
                    best = ranked_failures[0]
                    answer = (
                        f"{best.name} has the most failed transactions "
                        f"({best.failed_transactions:,})."
                    )
                    return "top_bank_failures", answer, {
                        "bank": best.name,
                        "failed_transactions": best.failed_transactions,
                    }
            if any(
                word in lower.split()
                for word in ("rate", "percentage", "best")
            ):
                metric = "success_rate"
            elif any(
                word in lower.split()
                for word in ("amount", "value", "spend", "revenue", "volume")
            ):
                metric = "completed_amount"
            elif any(
                word in lower.split()
                for word in ("success", "successful", "completed")
            ):
                metric = "completed_transactions"
            else:
                metric = "transaction_count"
            ranked = sorted(
                snapshot.banks,
                key=lambda item: (
                    getattr(item, metric),
                    item.transaction_count,
                    item.name,
                ),
                reverse=True,
            )
            if ranked:
                best = ranked[0]
                if metric == "success_rate":
                    answer = (
                        f"{best.name} has the highest success rate at "
                        f"{best.success_rate:.2%} "
                        f"({best.completed_transactions:,} of "
                        f"{best.transaction_count:,} transactions)."
                    )
                elif metric == "completed_amount":
                    answer = (
                        f"{best.name} has the highest completed amount "
                        f"({snapshot.currency} {best.completed_amount:,.2f})."
                    )
                elif metric == "completed_transactions":
                    answer = (
                        f"{best.name} has the most successful transactions "
                        f"({best.completed_transactions:,})."
                    )
                else:
                    answer = (
                        f"{best.name} has the most transactions "
                        f"({best.transaction_count:,})."
                    )
                return "top_bank", answer, {
                    "bank": best.name,
                    "transaction_count": best.transaction_count,
                    "success_rate": best.success_rate,
                    "completed_transactions": best.completed_transactions,
                }

        if "merchant" in lower:
            if failed_question:
                if failed_rate_question:
                    ranked_rates = sorted(
                        snapshot.merchants,
                        key=lambda item: (
                            item.failure_rate,
                            item.name,
                        ),
                        reverse=True,
                    )
                    if ranked_rates:
                        best = ranked_rates[0]
                        return (
                            "top_merchant_failure_rate",
                            f"{best.name} has the highest failure rate at "
                            f"{best.failure_rate:.2%}.",
                            {
                                "merchant": best.name,
                                "failure_rate": best.failure_rate,
                            },
                        )
                if any(
                    item.failed_transactions is None
                    for item in snapshot.merchants
                ):
                    return (
                        "merchant_failures_unavailable",
                        "The configured aggregate analytics API does not "
                        "provide failed-payment totals by merchant. No "
                        "ranking has been inferred.",
                        {},
                    )
                ranked_failures = sorted(
                    snapshot.merchants,
                    key=lambda item: (
                        item.failed_transactions or 0,
                        item.name,
                    ),
                    reverse=True,
                )
                if ranked_failures:
                    best = ranked_failures[0]
                    return (
                        "top_merchant_failures",
                        f"{best.name} has the most failed transactions "
                        f"({best.failed_transactions:,}).",
                        {
                            "merchant": best.name,
                            "failed_transactions": best.failed_transactions,
                        },
                    )
            amount_ranking = any(
                word in lower.split()
                for word in ("amount", "value", "spend", "revenue")
            )
            ranked_merchants = sorted(
                snapshot.merchants,
                key=lambda item: (
                    item.completed_amount
                    if amount_ranking
                    else item.transaction_count,
                    item.name,
                ),
                reverse=True,
            )
            if ranked_merchants:
                best = ranked_merchants[0]
                if amount_ranking:
                    answer = (
                        f"{best.name} ({best.category}) has the highest "
                        f"completed amount ({snapshot.currency} "
                        f"{best.completed_amount:,.2f})."
                    )
                else:
                    answer = (
                        f"{best.name} ({best.category}) has the most "
                        f"transactions ({best.transaction_count:,}) and a "
                        f"{best.failure_rate:.2%} failure rate."
                    )
                return "top_merchant", answer, {
                    "merchant": best.name,
                    "category": best.category,
                    "transaction_count": best.transaction_count,
                    "failure_rate": best.failure_rate,
                }

        if "categor" in lower:
            if failed_question:
                if failed_rate_question:
                    if any(
                        item.failure_rate is None
                        for item in snapshot.categories
                    ):
                        return (
                            "category_failure_rate_unavailable",
                            "The configured aggregate analytics API does not "
                            "provide failed-payment rates by category. No "
                            "ranking has been inferred.",
                            {},
                        )
                    ranked_categories = sorted(
                        snapshot.categories,
                        key=lambda item: (
                            item.failure_rate or 0,
                            item.name,
                        ),
                        reverse=True,
                    )
                    if ranked_categories:
                        best = ranked_categories[0]
                        return (
                            "top_category_failure_rate",
                            f"{best.name} has the highest failure rate at "
                            f"{best.failure_rate:.2%}.",
                            {
                                "category": best.name,
                                "failure_rate": best.failure_rate,
                            },
                        )
                if any(
                    item.failed_transactions is None
                    for item in snapshot.categories
                ):
                    return (
                        "category_failures_unavailable",
                        "The configured aggregate analytics API does not "
                        "provide failed-payment totals by category. No "
                        "ranking has been inferred.",
                        {},
                    )
                ranked_categories = sorted(
                    snapshot.categories,
                    key=lambda item: (
                        item.failed_transactions or 0,
                        item.name,
                    ),
                    reverse=True,
                )
                if ranked_categories:
                    best = ranked_categories[0]
                    return (
                        "top_category_failures",
                        f"{best.name} has the most failed transactions "
                        f"({best.failed_transactions:,}).",
                        {
                            "category": best.name,
                            "failed_transactions": best.failed_transactions,
                        },
                    )
            ranked_categories = sorted(
                snapshot.categories,
                key=lambda item: (
                    item.completed_amount
                    if any(word in lower for word in ("amount", "value", "spend"))
                    else item.transaction_count,
                    item.name,
                ),
                reverse=True,
            )
            if ranked_categories:
                best = ranked_categories[0]
                answer = (
                    f"{best.name} leads with {best.transaction_count:,} "
                    f"transactions and completed amount "
                    f"{snapshot.currency} {best.completed_amount:,.2f}."
                )
                return "top_category", answer, {
                    "category": best.name,
                    "transaction_count": best.transaction_count,
                    "completed_amount": best.completed_amount,
                    "currency": snapshot.currency,
                }

    merchant = next(
        (item for item in snapshot.merchants if item.name.casefold() in lower),
        None,
    )
    if merchant is not None:
        if failed_question and not failed_rate_question:
            if merchant.failed_transactions is None:
                return (
                    "merchant_failures_unavailable",
                    "The configured aggregate analytics API does not provide "
                    f"failed-payment totals for {merchant.name}. No count has "
                    "been inferred.",
                    {},
                )
            answer = (
                f"{merchant.name} had {merchant.failed_transactions:,} failed "
                f"of {merchant.transaction_count:,} transactions "
                f"({merchant.failure_rate:.2%} failure rate)."
            )
            return "merchant_metrics", answer, {
                "merchant": merchant.name,
                "transaction_count": merchant.transaction_count,
                "failed_transactions": merchant.failed_transactions,
                "failure_rate": merchant.failure_rate,
            }
        answer = (
            f"{merchant.name} ({merchant.category}): "
            f"{merchant.transaction_count:,} transactions, "
            f"{merchant.failure_rate:.2%} failure rate, completed amount "
            f"{snapshot.currency} {merchant.completed_amount:,.2f}."
        )
        return "merchant_metrics", answer, {
            "merchant": merchant.name,
            "category": merchant.category,
            "transaction_count": merchant.transaction_count,
            "failure_rate": merchant.failure_rate,
            "completed_amount": merchant.completed_amount,
            "currency": snapshot.currency,
        }

    if failed_question and mentioned_categories:
        category = mentioned_categories[0]
        if failed_rate_question and category.failure_rate is None:
            return (
                "category_failure_rate_unavailable",
                "The configured aggregate analytics API does not provide "
                f"failed-payment rates for {category.name}. No rate has been "
                "inferred.",
                {},
            )
        if not failed_rate_question and category.failed_transactions is None:
            return (
                "category_failures_unavailable",
                "The configured aggregate analytics API does not provide "
                f"failed-payment totals for {category.name}. No count has "
                "been inferred.",
                {},
            )
        if failed_rate_question:
            answer = (
                f"{category.name} had a {category.failure_rate:.2%} "
                "transaction failure rate."
            )
        else:
            answer = (
                f"{category.name} had {category.failed_transactions:,} "
                f"failed of {category.transaction_count:,} transactions "
                f"({category.failure_rate:.2%} failure rate)."
            )
        return "category_metrics", answer, {
            "categories": [
                {
                    "category": category.name,
                    "transaction_count": category.transaction_count,
                    "failed_transactions": category.failed_transactions,
                    "failure_rate": category.failure_rate,
                    "currency": snapshot.currency,
                }
            ]
        }

    if failed_question and "merchant" in lower:
        if failed_rate_question:
            rows = [
                {
                    "merchant": item.name,
                    "category": item.category,
                    "transaction_count": item.transaction_count,
                    "failure_rate": item.failure_rate,
                    "currency": snapshot.currency,
                }
                for item in snapshot.merchants
            ]
            answer = "Merchant failure rates: " + "; ".join(
                f"{item['merchant']}: {item['failure_rate']:.2%}"
                for item in rows
            )
        else:
            if any(
                item.failed_transactions is None
                for item in snapshot.merchants
            ):
                return (
                    "merchant_failures_unavailable",
                    "The configured aggregate analytics API does not provide "
                    "failed-payment totals by merchant. No counts have been "
                    "inferred.",
                    {},
                )
            rows = [
                {
                    "merchant": item.name,
                    "category": item.category,
                    "transaction_count": item.transaction_count,
                    "failed_transactions": item.failed_transactions,
                    "failure_rate": item.failure_rate,
                    "currency": snapshot.currency,
                }
                for item in snapshot.merchants
            ]
            answer = "Failed payments by merchant: " + "; ".join(
                f"{item['merchant']}: {item['failed_transactions']:,} of "
                f"{item['transaction_count']:,}"
                for item in rows
            )
        return "merchant_comparison", answer, {"merchants": rows}

    if failed_question and "categor" in lower:
        if failed_rate_question and any(
            item.failure_rate is None for item in snapshot.categories
        ):
            return (
                "category_failure_rate_unavailable",
                "The configured aggregate analytics API does not provide "
                "failed-payment rates by category. No rates have been "
                "inferred.",
                {},
            )
        if not failed_rate_question and any(
            item.failed_transactions is None for item in snapshot.categories
        ):
            return (
                "category_failures_unavailable",
                "The configured aggregate analytics API does not provide "
                "failed-payment totals by category. No counts have been "
                "inferred.",
                {},
            )
        rows = [
            {
                "category": item.name,
                "transaction_count": item.transaction_count,
                "failed_transactions": item.failed_transactions,
                "failure_rate": item.failure_rate,
                "currency": snapshot.currency,
            }
            for item in snapshot.categories
        ]
        if failed_rate_question:
            answer = "Category failure rates: " + "; ".join(
                f"{item['category']}: {item['failure_rate']:.2%}"
                for item in rows
            )
        else:
            answer = "Failed payments by category: " + "; ".join(
                f"{item['category']}: {item['failed_transactions']:,} of "
                f"{item['transaction_count']:,}"
                for item in rows
            )
        return "category_comparison", answer, {"categories": rows}

    if failed_question:
        if snapshot.failed_transactions is None:
            return (
                "failed_transactions_unavailable",
                "The configured aggregate analytics API does not provide "
                "an exact failed-payment count. No count has been inferred.",
                {},
            )
        failed_rate = (
            snapshot.failed_transactions / snapshot.total_transactions
            if snapshot.total_transactions
            else 0.0
        )
        answer = (
            f"Failed transactions: {snapshot.failed_transactions:,} of "
            f"{snapshot.total_transactions:,} "
            f"({failed_rate:.2%} of all transactions)."
        )
        return "failed_transactions", answer, {
            "failed_transactions": snapshot.failed_transactions,
            "total_transactions": snapshot.total_transactions,
            "failure_rate": failed_rate,
        }

    if "categor" in lower:
        rows = [
            {
                "category": item.name,
                "transaction_count": item.transaction_count,
                "completed_amount": item.completed_amount,
                "currency": snapshot.currency,
            }
            for item in snapshot.categories
        ]
        answer = "Category totals (completed amount): " + "; ".join(
            f"{item.name}: {item.transaction_count:,} transactions, "
            f"{snapshot.currency} {item.completed_amount:,.2f}"
            for item in snapshot.categories
        )
        return "category_metrics", answer, {"categories": rows}

    if mentioned_categories:
        category = mentioned_categories[0]
        answer = (
            f"{category.name}: {category.transaction_count:,} transactions, "
            f"completed amount {snapshot.currency} "
            f"{category.completed_amount:,.2f}."
        )
        return "category_metrics", answer, {
            "categories": [
                {
                    "category": category.name,
                    "transaction_count": category.transaction_count,
                    "completed_amount": category.completed_amount,
                    "currency": snapshot.currency,
                }
            ]
        }

    if "merchant" in lower:
        items = sorted(
            snapshot.merchants,
            key=lambda item: item.transaction_count,
            reverse=True,
        )[:10]
        answer = "Merchant transaction and failure metrics: " + "; ".join(
            f"{item.name}: {item.transaction_count:,} transactions, "
            f"{item.failure_rate:.2%} failure rate, completed amount "
            f"{snapshot.currency} {item.completed_amount:,.2f}"
            for item in items
        )
        return "merchant_list", answer, {
            "merchants": [
                {
                    "merchant": item.name,
                    "category": item.category,
                    "transaction_count": item.transaction_count,
                    "failure_rate": item.failure_rate,
                    "completed_amount": item.completed_amount,
                    "currency": snapshot.currency,
                }
                for item in items
            ]
        }

    if "bank" in lower:
        if failed_question:
            if any(item.failed_transactions is None for item in snapshot.banks):
                return (
                    "bank_failures_unavailable",
                    "The configured aggregate analytics API does not provide "
                    "failed-payment totals by bank. No comparison has been "
                    "inferred.",
                    {},
                )
            rows = [
                {
                    "bank": item.name,
                    "transaction_count": item.transaction_count,
                    "failed_transactions": item.failed_transactions,
                    "failure_rate": (
                        item.failed_transactions / item.transaction_count
                        if item.transaction_count
                        else 0.0
                    ),
                }
                for item in snapshot.banks
            ]
            answer = "Failed payments by bank: " + "; ".join(
                f"{item['bank']}: {item['failed_transactions']:,} of "
                f"{item['transaction_count']:,}"
                for item in rows
            )
            return "bank_comparison", answer, {"banks": rows}
        answer = "Bank success rates: " + "; ".join(
            f"{item.name}: {item.success_rate:.2%} "
            f"({item.completed_transactions:,}/{item.transaction_count:,} "
            f"completed), completed amount {snapshot.currency} "
            f"{item.completed_amount:,.2f}"
            for item in snapshot.banks
        )
        return "bank_list", answer, {
            "banks": [
                {
                    "bank": item.name,
                    "transaction_count": item.transaction_count,
                    "completed_transactions": item.completed_transactions,
                    "completed_amount": item.completed_amount,
                    "success_rate": item.success_rate,
                    "currency": snapshot.currency,
                }
                for item in snapshot.banks
            ]
        }

    if any(
        word in lower.split()
        for word in ("amount", "value", "spend", "revenue", "volume", "money")
    ) or "how much" in lower:
        answer = (
            f"Completed transaction amount: {snapshot.currency} "
            f"{snapshot.completed_amount:,.2f} across "
            f"{snapshot.completed_transactions:,} successful "
            f"transactions. Failed transaction amounts are not counted "
            "as money actually debited."
        )
        return "completed_amount", answer, {
            "completed_amount": snapshot.completed_amount,
            "completed_transactions": snapshot.completed_transactions,
            "currency": snapshot.currency,
        }

    if any(
        phrase in lower
        for phrase in (
            "went through",
            "successfully paid",
            "successful payments",
            "completed payments",
        )
    ):
        answer = (
            f"{snapshot.completed_transactions:,} of "
            f"{snapshot.total_transactions:,} transactions completed "
            f"successfully ({snapshot.success_rate:.2%})."
        )
        return "completed_transactions", answer, {
            "completed_transactions": snapshot.completed_transactions,
            "total_transactions": snapshot.total_transactions,
            "success_rate": snapshot.success_rate,
        }

    if any(
        phrase in lower
        for phrase in (
            "success rate",
            "success percentage",
            "successful rate",
            "completion rate",
        )
    ):
        answer = (
            f"Overall success rate: {snapshot.success_rate:.2%} "
            f"({snapshot.completed_transactions:,} of "
            f"{snapshot.total_transactions:,} transactions completed)."
        )
        return "overall_success_rate", answer, {
            "total_transactions": snapshot.total_transactions,
            "completed_transactions": snapshot.completed_transactions,
            "success_rate": snapshot.success_rate,
        }

    if any(
        phrase in lower
        for phrase in (
            "how many",
            "total",
            "number of",
            "count of",
            "went through",
            "successful",
        )
    ) or (
        ("transaction" in lower or "payment" in lower)
        and any(word in lower for word in ("overall", "all", "completed"))
    ):
        answer = (
            f"{snapshot.total_transactions:,} total transactions; "
            f"{snapshot.completed_transactions:,} completed; completed "
            f"amount {snapshot.currency} {snapshot.completed_amount:,.2f}; "
            f"success rate {snapshot.success_rate:.2%}."
        )
        return "overall_summary", answer, {
            "total_transactions": snapshot.total_transactions,
            "completed_transactions": snapshot.completed_transactions,
            "completed_amount": snapshot.completed_amount,
            "success_rate": snapshot.success_rate,
            "currency": snapshot.currency,
        }
    return None


def answer_analytics(
    question: str,
    snapshot: AnalyticsSnapshot,
    provider: Callable[[str, dict], str] | None = None,
    history: list[dict] | None = None,
) -> str:
    safe_question = validate_chat_input(question)
    safe_history = tuple(
        message
        for message in (history or [])[-10:]
        if isinstance(message, Mapping)
        and message.get("role") in {"user", "assistant"}
        and isinstance(message.get("content"), str)
    )
    verified = _verified_answer(
        safe_question,
        snapshot,
        safe_history,
    )
    if verified is None:
        return (
            "I can answer aggregate questions about transaction totals, "
            "success or failure rates, banks, merchants, categories, and "
            "trends. Which of those would you like to explore? I cannot look "
            "up an individual customer's payment."
        )

    topic, answer, context = verified
    if provider is None:
        return answer

    provider_context = {
        **context,
        "question": redact_sensitive_input(safe_question),
        "history": [
            {
                "role": message["role"],
                "content": redact_sensitive_input(
                    str(message["content"])
                )[:500],
            }
            for message in safe_history[-4:]
        ],
    }
    explanation = provider(topic, provider_context)
    if any(character.isdigit() for character in explanation):
        return answer
    return f"{explanation}\n\nVerified calculation: {answer}"


def analytics_visualization(
    question: str,
    snapshot: AnalyticsSnapshot,
    history: list[dict] | None = None,
) -> tuple[str, pd.DataFrame, pd.DataFrame] | None:
    """Return an aggregate table and single-metric chart when useful."""
    question = validate_chat_input(question)
    safe_history = tuple(
        message
        for message in (history or [])[-10:]
        if isinstance(message, Mapping)
        and message.get("role") in {"user", "assistant"}
        and isinstance(message.get("content"), str)
    )
    verified = _verified_answer(question, snapshot, safe_history)
    if verified is None:
        return None
    topic, _, context = verified
    lower = question.casefold()

    if topic == "monthly_trends":
        table = pd.DataFrame(context["months"])
        if table.empty:
            return None
        metric_columns = (
            ["completed_amount"]
            if any(
                word in lower
                for word in ("amount", "spend", "revenue", "value")
            )
            else [
                "transaction_count",
                "completed_transactions",
                "failed_transactions",
            ]
        )
        return "line", table, table.set_index("month")[metric_columns]

    if topic in {"bank_list", "bank_comparison"}:
        table = pd.DataFrame(context["banks"])
        if table.empty:
            return None
        if "failed_transactions" in table and any(
            word in lower for word in ("fail", "declin")
        ) and re.search(r"\b(?:rate|percentage|percent)\b", lower):
            metric = "failure_rate"
        elif "failed_transactions" in table and any(
            word in lower for word in ("fail", "declin")
        ):
            metric = "failed_transactions"
        elif "success_rate" in table and any(
            word in lower for word in ("success", "rate", "percentage")
        ):
            metric = "success_rate"
        elif "completed_amount" in table and any(
            word in lower
            for word in ("amount", "spend", "revenue", "value", "volume")
        ):
            metric = "completed_amount"
        elif "completed_transactions" in table and any(
            word in lower for word in ("successful", "completed")
        ):
            metric = "completed_transactions"
        else:
            metric = "transaction_count"
        return "bar", table, table.set_index("bank")[[metric]]

    if topic in {"merchant_list", "merchant_comparison"}:
        table = pd.DataFrame(context["merchants"])
        if table.empty:
            return None
        if "failed_transactions" in table and any(
            word in lower for word in ("fail", "declin")
        ) and not re.search(r"\b(?:rate|percentage|percent)\b", lower):
            metric = "failed_transactions"
        elif any(
            word in lower
            for word in ("amount", "spend", "revenue", "value")
        ):
            metric = "completed_amount"
        elif "failure_rate" in table and any(
            word in lower for word in ("fail", "declin")
        ):
            metric = "failure_rate"
        else:
            metric = "transaction_count"
        return "bar", table, table.set_index("merchant")[[metric]]

    if topic in {"category_metrics", "category_comparison"}:
        table = pd.DataFrame(context["categories"])
        if table.empty:
            return None
        if "failed_transactions" in table and any(
            word in lower for word in ("fail", "declin")
        ) and not re.search(r"\b(?:rate|percentage|percent)\b", lower):
            metric = "failed_transactions"
        elif "failure_rate" in table and any(
            word in lower for word in ("fail", "declin")
        ):
            metric = "failure_rate"
        elif any(
            word in lower
            for word in ("amount", "spend", "revenue", "value")
        ):
            metric = "completed_amount"
        else:
            metric = "transaction_count"
        return "bar", table, table.set_index("category")[[metric]]
    return None
