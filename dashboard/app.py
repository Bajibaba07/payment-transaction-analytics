"""Interactive dashboard for the synthetic payment analytics project."""

from pathlib import Path

import pandas as pd
import streamlit as st


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "processed"


st.set_page_config(
    page_title="Payment Analytics",
    page_icon="P",
    layout="wide",
    initial_sidebar_state="expanded",
)


st.markdown(
    """
    <style>
    .block-container { padding-top: 2rem; }
    [data-testid="stMetricValue"] { color: #0f766e; }
    </style>
    """,
    unsafe_allow_html=True,
)


def data_version():
    data_files = (
        "transactions_clean.csv",
        "customers_clean.csv",
        "merchants_clean.csv",
        "cards_public.csv",
    )

    return tuple(
        (
            name,
            (DATA_DIR / name).stat().st_mtime_ns,
            (DATA_DIR / name).stat().st_size,
        )
        for name in data_files
    )


@st.cache_data
def load_data(data_version_token):
    transactions = pd.read_csv(
        DATA_DIR / "transactions_clean.csv"
    )
    customers = pd.read_csv(
        DATA_DIR / "customers_clean.csv"
    )
    merchants = pd.read_csv(
        DATA_DIR / "merchants_clean.csv"
    )
    cards = pd.read_csv(
        DATA_DIR / "cards_public.csv"
    )

    transactions["transaction_date"] = pd.to_datetime(
        transactions["transaction_date"]
    )

    return transactions, customers, merchants, cards


try:
    transactions, customers, merchants, cards = load_data(
        data_version()
    )
except FileNotFoundError:
    st.error(
        "Processed data is missing. Run src/clean_data.py first."
    )
    st.stop()


st.title("Payment Transaction Analytics")
st.caption(
    "Synthetic data only | Dashboard-safe fields | INR"
)


# ============================================================
# SIDEBAR FILTERS
# ============================================================

with st.sidebar:
    st.header("Filters")

    categories = st.multiselect(
        "Merchant category",
        sorted(
            transactions["merchant_category"].unique()
        ),
        default=[],
    )

    statuses = st.multiselect(
        "Transaction status",
        sorted(
            transactions["transaction_status"].unique()
        ),
        default=[],
    )

    banks = st.multiselect(
        "Bank",
        sorted(
            transactions["bank_name"].unique()
        ),
        default=[],
    )


# ============================================================
# FILTER DATA
# ============================================================

filtered = transactions.copy()

if categories:
    filtered = filtered[
        filtered["merchant_category"].isin(categories)
    ]

if statuses:
    filtered = filtered[
        filtered["transaction_status"].isin(statuses)
    ]

if banks:
    filtered = filtered[
        filtered["bank_name"].isin(banks)
    ]


completed = filtered[
    filtered["is_successful"]
]


# ============================================================
# EXECUTIVE OVERVIEW
# ============================================================

st.subheader("Executive overview")

metric_columns = st.columns(4)

if not categories:

    metric_columns[0].metric(
        "Completed amount",
        "INR 0"
    )

    metric_columns[1].metric(
        "Transactions",
        "0"
    )

    metric_columns[2].metric(
        "Active customers",
        "0"
    )

    metric_columns[3].metric(
        "Success rate",
        "0%"
    )

else:

    metric_columns[0].metric(
        "Completed amount",
        f"INR {completed['amount'].sum():,.0f}"
    )

    metric_columns[1].metric(
        "Transactions",
        f"{len(filtered):,}"
    )

    metric_columns[2].metric(
        "Active customers",
        f"{filtered['customer_id'].nunique():,}"
    )

    success_rate = (
        filtered["is_successful"].mean()
        if len(filtered)
        else 0
    )

    metric_columns[3].metric(
        "Success rate",
        f"{success_rate:.1%}"
    )


# ============================================================
# CHARTS
# ============================================================

if categories:

    # --------------------------------------------------------
    # Monthly trend + Category amount
    # --------------------------------------------------------

    left, right = st.columns(2)

    with left:

        st.subheader(
            "Monthly transaction trend"
        )

        monthly = (
            filtered.assign(
                transaction_month=(
                    filtered["transaction_date"]
                    .dt.to_period("M")
                    .astype(str)
                )
            )
            .groupby("transaction_month")
            .agg(
                completed_amount=(
                    "amount",
                    lambda values: values[
                        filtered.loc[
                            values.index,
                            "is_successful"
                        ]
                    ].sum(),
                ),
                transactions=(
                    "transaction_id",
                    "count"
                ),
            )
        )

        st.line_chart(
            monthly,
            y=[
                "completed_amount",
                "transactions",
            ],
        )

    with right:

        st.subheader(
            "Completed amount by category"
        )

        category = (
            completed
            .groupby("merchant_category")["amount"]
            .sum()
            .sort_values(ascending=True)
        )

        st.bar_chart(category)


    # --------------------------------------------------------
    # Transaction status + Bank/card
    # --------------------------------------------------------

    left, right = st.columns(2)

    with left:

        st.subheader(
            "Transaction status"
        )

        st.bar_chart(
            filtered[
                "transaction_status"
            ].value_counts()
        )

    with right:

        st.subheader(
            "Bank and card type"
        )

        bank_mix = (
            completed
            .groupby(
                [
                    "bank_name",
                    "card_type",
                ]
            )["amount"]
            .sum()
            .unstack(fill_value=0)
        )

        st.bar_chart(bank_mix)


    # ========================================================
    # CUSTOMER AND MERCHANT INSIGHTS
    # ========================================================

    st.subheader(
        "Customer and merchant insights"
    )

    customer_table, merchant_table = st.columns(2)

    with customer_table:

        st.markdown(
            "**Top customers by completed spend**"
        )

        top_customers = (
            completed
            .groupby(
                "customer_id",
                as_index=False
            )
            .agg(
                completed_spend=(
                    "amount",
                    "sum"
                ),
                transactions=(
                    "transaction_id",
                    "count"
                ),
            )
            .sort_values(
                "completed_spend",
                ascending=False
            )
            .head(10)
        )

        st.dataframe(
            top_customers,
            width="stretch",
            hide_index=True,
        )

    with merchant_table:

        st.markdown(
            "**Merchants with highest failure rate**"
        )

        merchant_table_data = (
            filtered
            .groupby(
                [
                    "merchant_id",
                    "merchant_name",
                    "merchant_category",
                ],
                as_index=False,
            )
            .agg(
                transactions=(
                    "transaction_id",
                    "count"
                ),
                failure_rate=(
                    "is_failure",
                    "mean"
                ),
                total_amount=(
                    "amount",
                    "sum"
                ),
            )
            .query("transactions >= 5")
            .sort_values(
                "failure_rate",
                ascending=False
            )
            .head(10)
        )

        merchant_table_data[
            "failure_rate"
        ] = merchant_table_data[
            "failure_rate"
        ].map(
            lambda value: f"{value:.1%}"
        )

        st.dataframe(
            merchant_table_data,
            width="stretch",
            hide_index=True,
        )


    # ========================================================
    # FILTERED TRANSACTIONS
    # ========================================================

    st.subheader(
        "Filtered Transactions"
    )

    display_columns = [
        "transaction_id",
        "merchant_name",
        "merchant_category",
        "transaction_date",
        "amount",
        "transaction_status",
        "payment_method",
        "merchant_city",
        "merchant_state",
        "bank_name",
        "card_type",
    ]

    filtered_display = filtered[
        display_columns
    ].copy()

    st.dataframe(
        filtered_display.sort_values(
            "transaction_date",
            ascending=False,
        ),
        width="stretch",
        hide_index=True,
    )

    st.caption(
        f"Showing {len(filtered):,} "
        f"of {len(transactions):,} transactions. "
        "Card numbers and CVVs are intentionally excluded."
    )

else:

    # ========================================================
    # NO CATEGORY SELECTED
    # ========================================================

    st.info(
        "Select at least one merchant category "
        "from the sidebar to view analytics."
    )