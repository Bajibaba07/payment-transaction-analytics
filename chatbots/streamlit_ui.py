"""Reusable Streamlit views for the existing payment chatbots."""

import os
from collections.abc import Callable

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
    AnalyticsSnapshot,
    answer_analytics,
    analytics_visualization,
)
from chatbots.support import answer_support


def _secret_value(name: str):
    try:
        return st.secrets.get(name)
    except StreamlitSecretNotFoundError:
        return None


def configured_provider() -> OpenAIProvider | None:
    """Create the optional provider from runtime configuration."""
    api_key = configured_api_key(
        {"OPENAI_API_KEY": _secret_value("OPENAI_API_KEY")}
    )
    if api_key is None:
        return None

    configured_model = (
        _secret_value("OPENAI_MODEL")
        or os.environ.get("OPENAI_MODEL")
    )
    model = configured_model if isinstance(configured_model, str) else None
    return OpenAIProvider(api_key, model=model or "gpt-4o-mini")


def _render_visualization(visualization: dict | None) -> None:
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


def render_analytics_chat(
    snapshot: AnalyticsSnapshot,
    provider: OpenAIProvider | None = None,
) -> None:
    """Render analytics chat over the supplied, verified aggregate snapshot."""
    st.title("Transaction Analytics Chatbot")
    st.caption(
        "Answers use the full processed transaction dataset, independently "
        "of the Dashboard filters. Individual payment records are not looked "
        "up or sent to the optional AI provider."
    )
    if provider is None:
        st.info(
            "Optional AI is not configured. Verified local calculations "
            "remain available."
        )

    suggestions = (
        "What are the transaction totals?",
        "What is the success rate?",
        "How many payments failed?",
        "Show monthly transaction trends",
        "Compare banks",
        "Show category totals",
    )
    columns = st.columns(3)
    selected_suggestion = None
    for index, suggestion in enumerate(suggestions):
        if columns[index % 3].button(
            suggestion, key=f"integrated_analytics_suggestion_{index}"
        ):
            selected_suggestion = suggestion

    messages = st.session_state.setdefault("analytics_messages", [])
    if st.button(
        "Clear analytics chat",
        key="integrated_clear_analytics_chat",
        disabled=not messages,
    ):
        st.session_state.analytics_messages = []
        messages = st.session_state.analytics_messages

    for message in messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message["role"] == "assistant":
                _render_visualization(message.get("visualization"))

    prompt = st.chat_input(
        "Ask about totals, success rates, trends, merchants, or banks",
        key="integrated_analytics_prompt",
    ) or selected_suggestion
    if not prompt:
        return

    safe_prompt = redact_sensitive_input(prompt)
    history = list(messages)
    messages.append({"role": "user", "content": safe_prompt})
    with st.chat_message("user"):
        st.markdown(safe_prompt)

    visualization = None
    with st.chat_message("assistant"):
        try:
            responder: Callable | None = (
                provider.answer if provider is not None else None
            )
            response = answer_analytics(
                safe_prompt,
                snapshot,
                provider=responder,
                history=history,
            )
            raw_visualization = analytics_visualization(
                safe_prompt, snapshot, history=history
            )
            if raw_visualization:
                kind, table, chart = raw_visualization
                visualization = {
                    "kind": kind,
                    "table": table,
                    "chart": chart,
                }
        except AIProviderError as error:
            response = answer_analytics(safe_prompt, snapshot, history=history)
            st.warning(
                f"The AI provider is unavailable ({error}); showing the "
                "verified local calculation instead."
            )
            raw_visualization = analytics_visualization(
                safe_prompt, snapshot, history=history
            )
            if raw_visualization:
                kind, table, chart = raw_visualization
                visualization = {
                    "kind": kind,
                    "table": table,
                    "chart": chart,
                }
        except (AnalyticsDataError, ValueError) as error:
            response = f"Unable to answer this question: {error}"
            st.warning(response)

        st.markdown(response)
        _render_visualization(visualization)

    messages.append(
        {
            "role": "assistant",
            "content": response,
            "visualization": visualization,
        }
    )


def render_support_chat(
    provider: OpenAIProvider | None = None,
) -> None:
    """Render FAQ-grounded payment support chat without account access."""
    st.title("Payment Support Chatbot")
    st.caption(
        "General FAQ guidance only. This app cannot inspect individual "
        "payments, file complaints, or issue refunds."
    )
    if provider is None:
        st.info(
            "Optional AI is not configured. The local payment FAQ remains "
            "available."
        )

    suggestions = (
        "My payment failed",
        "Why is my payment pending?",
        "How do refunds work?",
        "How do I troubleshoot a payment?",
        "How do I make a complaint?",
    )
    columns = st.columns(3)
    selected_suggestion = None
    for index, suggestion in enumerate(suggestions):
        if columns[index % 3].button(
            suggestion, key=f"integrated_support_suggestion_{index}"
        ):
            selected_suggestion = suggestion

    messages = st.session_state.setdefault("support_messages", [])
    if st.button(
        "Clear support chat",
        key="integrated_clear_support_chat",
        disabled=not messages,
    ):
        st.session_state.support_messages = []
        messages = st.session_state.support_messages

    for message in messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    prompt = st.chat_input(
        "Ask about failed or pending payments, refunds, or troubleshooting",
        key="integrated_support_prompt",
    ) or selected_suggestion
    if not prompt:
        return

    safe_prompt = redact_sensitive_input(prompt)
    history = list(messages)
    messages.append({"role": "user", "content": safe_prompt})
    with st.chat_message("user"):
        st.markdown(safe_prompt)

    with st.chat_message("assistant"):
        try:
            responder: Callable | None = (
                provider.answer if provider is not None else None
            )
            response = answer_support(
                safe_prompt,
                provider=responder,
                history=history,
            )
        except AIProviderError as error:
            response = answer_support(safe_prompt, history=history)
            st.warning(
                f"The AI provider is unavailable ({error}); showing local "
                "FAQ guidance instead."
            )
        except ValueError as error:
            response = f"Unable to load support guidance: {error}"
            st.error(response)
        st.markdown(response)

    messages.append({"role": "assistant", "content": response})
