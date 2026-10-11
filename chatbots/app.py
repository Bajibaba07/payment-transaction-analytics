"""Standalone Streamlit UI for the analytics and support chatbots."""

import os
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st
from streamlit.errors import StreamlitSecretNotFoundError

from chatbots.ai_provider import (
    AIProviderError,
    OpenAIProvider,
    configured_api_key,
    redact_sensitive_input,
)
from chatbots.analytics import (
    AnalyticsDataError,
    answer_analytics,
    analytics_visualization,
    load_snapshot,
)
from chatbots.support import answer_support


st.set_page_config(
    page_title="Payment Analytics Chatbots",
    page_icon="P",
    layout="centered",
)
st.title("Payment Analytics Chatbots")
st.caption(
    "Synthetic demonstration data only. This app cannot look up individual "
    "payments or customer accounts. Never enter card details, CVVs, PINs, "
    "passwords, or OTPs."
)


def _secret_value(name: str):
    try:
        return st.secrets.get(name)
    except StreamlitSecretNotFoundError:
        return None


def _render_analytics_visualization(visualization):
    if not visualization:
        return
    st.dataframe(
        visualization["table"],
        hide_index=True,
        width="stretch",
    )
    if visualization["kind"] == "line":
        st.line_chart(visualization["chart"])
    else:
        st.bar_chart(visualization["chart"])


api_key = configured_api_key(
    {"OPENAI_API_KEY": _secret_value("OPENAI_API_KEY")}
)
model = (
    _secret_value("OPENAI_MODEL")
    or os.environ.get("OPENAI_MODEL")
    or "gpt-4o-mini"
)
provider = OpenAIProvider(api_key, str(model)) if api_key else None
api_base_url = (
    _secret_value("PAYMENT_ANALYTICS_API_URL")
    or os.environ.get("PAYMENT_ANALYTICS_API_URL")
)

if provider is None:
    st.info(
        "AI provider is not configured. Both chatbots are using their "
        "deterministic local answers."
    )

analytics_tab, support_tab = st.tabs(
    ["Transaction analytics", "Customer support"]
)

with analytics_tab:
    st.subheader("Transaction analytics")
    st.caption("Suggested questions")
    analytics_suggestions = (
        "What are the transaction totals?",
        "What is the success rate?",
        "How many payments failed?",
        "Show monthly transaction trends",
        "Compare banks",
        "Show category totals",
    )
    suggestion_columns = st.columns(3)
    selected_analytics_suggestion = None
    for index, suggestion in enumerate(analytics_suggestions):
        if suggestion_columns[index % 3].button(
            suggestion, key=f"analytics_suggestion_{index}"
        ):
            selected_analytics_suggestion = suggestion

    if "analytics_messages" not in st.session_state:
        st.session_state.analytics_messages = []

    if st.button(
        "Clear analytics chat",
        key="clear_analytics_chat",
        disabled=not st.session_state.analytics_messages,
    ):
        st.session_state.analytics_messages = []
        st.rerun()

    for message in st.session_state.analytics_messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message["role"] == "assistant":
                _render_analytics_visualization(
                    message.get("visualization")
                )

    analytics_prompt = st.chat_input(
        "Ask about transaction totals, banks, merchants, or success rates",
        key="analytics_prompt",
    ) or selected_analytics_suggestion
    if analytics_prompt:
        safe_prompt = redact_sensitive_input(analytics_prompt)
        st.session_state.analytics_messages.append(
            {"role": "user", "content": safe_prompt}
        )
        with st.chat_message("user"):
            st.markdown(safe_prompt)
        with st.chat_message("assistant"):
            stored_visualization = None
            try:
                snapshot = load_snapshot(api_base_url=api_base_url)
                responder = provider.answer if provider else None
                response = answer_analytics(
                    safe_prompt,
                    snapshot,
                    provider=responder,
                    history=st.session_state.analytics_messages[:-1],
                )
                st.markdown(response)
                visualization = analytics_visualization(
                    safe_prompt,
                    snapshot,
                    history=st.session_state.analytics_messages[:-1],
                )
                if visualization:
                    kind, table, chart = visualization
                    stored_visualization = {
                        "kind": kind,
                        "table": table,
                        "chart": chart,
                    }
                    _render_analytics_visualization(stored_visualization)
            except AIProviderError as error:
                response = answer_analytics(safe_prompt, snapshot)
                visualization = analytics_visualization(
                    safe_prompt, snapshot
                )
                if visualization:
                    kind, table, chart = visualization
                    stored_visualization = {
                        "kind": kind,
                        "table": table,
                        "chart": chart,
                    }
                st.warning(
                    f"The AI provider is unavailable ({error}); showing the "
                    "verified local calculation instead."
                )
                st.markdown(response)
                _render_analytics_visualization(stored_visualization)
            except AnalyticsDataError as error:
                response = f"Unable to answer this question: {error}"
                st.error(response)
            except ValueError as error:
                response = f"Unable to answer this question: {error}"
                st.warning(response)
        st.session_state.analytics_messages.append(
            {
                "role": "assistant",
                "content": response,
                "visualization": stored_visualization,
            }
        )

with support_tab:
    st.subheader("Customer support")
    st.caption(
        "General FAQ guidance only; account-specific payment status is not "
        "available in this demo."
    )
    st.caption("Suggested questions")
    support_suggestions = (
        "My payment failed",
        "Why is my payment pending?",
        "How do refunds work?",
        "How do I troubleshoot a payment?",
        "How do I make a complaint?",
    )
    suggestion_columns = st.columns(3)
    selected_support_suggestion = None
    for index, suggestion in enumerate(support_suggestions):
        if suggestion_columns[index % 3].button(
            suggestion, key=f"support_suggestion_{index}"
        ):
            selected_support_suggestion = suggestion

    if "support_messages" not in st.session_state:
        st.session_state.support_messages = []

    if st.button(
        "Clear support chat",
        key="clear_support_chat",
        disabled=not st.session_state.support_messages,
    ):
        st.session_state.support_messages = []
        st.rerun()

    for message in st.session_state.support_messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    support_prompt = st.chat_input(
        "Ask about a failed payment, pending payment, or refund",
        key="support_prompt",
    ) or selected_support_suggestion
    if support_prompt:
        safe_prompt = redact_sensitive_input(support_prompt)
        st.session_state.support_messages.append(
            {"role": "user", "content": safe_prompt}
        )
        with st.chat_message("user"):
            st.markdown(safe_prompt)
        with st.chat_message("assistant"):
            try:
                responder = provider.answer if provider else None
                response = answer_support(
                    safe_prompt,
                    provider=responder,
                    history=st.session_state.support_messages[:-1],
                )
                st.markdown(response)
            except AIProviderError as error:
                response = answer_support(
                    safe_prompt,
                    history=st.session_state.support_messages[:-1],
                )
                st.warning(
                    f"The AI provider is unavailable ({error}); showing "
                    "local FAQ guidance instead."
                )
                st.markdown(response)
            except ValueError as error:
                response = f"Unable to load support guidance: {error}"
                st.error(response)
        st.session_state.support_messages.append(
            {"role": "assistant", "content": response}
        )
