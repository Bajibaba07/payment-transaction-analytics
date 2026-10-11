"""Optional, privacy-limited client for OpenAI chat completions."""

import json
import os
import re
from collections.abc import Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


API_URL = "https://api.openai.com/v1/chat/completions"
DEFAULT_MODEL = "gpt-4o-mini"
REQUEST_TIMEOUT_SECONDS = 20
_SENSITIVE_VALUE = re.compile(
    r"\b(?:cvv|cvc|security code|pin|otp|password|one[- ]time password)\b"
    r"\s*(?:is|:|=)?\s*[A-Za-z0-9-]+",
    re.IGNORECASE,
)
_PRIVATE_LABEL_VALUE = re.compile(
    r"\b(?:my name|name|address|account number|transaction id|"
    r"transaction reference|reference number)\s*(?:is|:|=)\s*[^,;]+",
    re.IGNORECASE,
)
_EMAIL = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
_CARD_NUMBER = re.compile(r"\b(?:\d[ -]?){11,18}\d\b")
_PHONE_NUMBER = re.compile(r"\b(?:\+?\d[ ().-]*){10,15}\b")
_SENSITIVE_REQUEST = re.compile(
    r"(?<!never )(?<!not )(?<!don't )\b(?:share|send|provide|enter|"
    r"tell me|give me|confirm)\s+(?:your\s+)?"
    r"(?:card number|card details|cvv|cvc|pin|otp|password)\b",
    re.IGNORECASE,
)


class AIProviderError(RuntimeError):
    """Raised when the configured AI provider cannot return a safe response."""


def validate_chat_input(text: str) -> str:
    """Validate and normalize a user question before local or AI processing."""
    if not isinstance(text, str):
        raise ValueError("The question must be text.")
    question = text.strip()
    if not question:
        raise ValueError("Enter a question to continue.")
    if len(question) > 500:
        raise ValueError("Keep the question to 500 characters or fewer.")
    return question


def _sanitize_context(value: object) -> object:
    if isinstance(value, Mapping):
        return {
            str(key): _sanitize_context(item)
            for key, item in value.items()
            if str(key).casefold()
            not in {
                "card",
                "card_id",
                "card_number",
                "cardholder_name",
                "cvv",
                "customer",
                "customer_id",
                "customer_address",
                "customer_email",
                "customer_name",
                "email",
                "email_address",
                "first_name",
                "last_name",
                "mobile",
                "history",
                "phone_number",
                "pan",
                "password",
                "pin",
                "phone",
                "question",
                "otp",
                "account_number",
                "account_id",
                "bank_account",
                "transaction_id",
                "transaction_reference",
                "token",
                "secret",
                "cvv2",
            }
        }
    if isinstance(value, (list, tuple)):
        return [_sanitize_context(item) for item in value]
    if isinstance(value, str):
        return redact_sensitive_input(value)
    return value


def configured_api_key(secrets: Mapping | None = None) -> str | None:
    key = os.environ.get("OPENAI_API_KEY")
    if key and key.strip():
        return key.strip()

    if secrets is not None:
        key = secrets.get("OPENAI_API_KEY")
        if isinstance(key, str) and key.strip():
            return key.strip()

    return None


def redact_sensitive_input(text: str) -> str:
    """Redact common payment credentials and direct contact data from chat."""
    redacted = _PRIVATE_LABEL_VALUE.sub("[REDACTED]", text)
    redacted = _SENSITIVE_VALUE.sub("[REDACTED]", redacted)
    redacted = _EMAIL.sub("[REDACTED EMAIL]", redacted)
    redacted = _CARD_NUMBER.sub("[REDACTED NUMBER]", redacted)
    return _PHONE_NUMBER.sub("[REDACTED PHONE]", redacted)


def requests_sensitive_information(text: str) -> bool:
    return _SENSITIVE_REQUEST.search(text) is not None


class OpenAIProvider:
    """Generate an answer from curated facts, never raw transaction rows."""

    def __init__(self, api_key: str, model: str = DEFAULT_MODEL):
        if not api_key.strip():
            raise ValueError("An OpenAI API key is required.")
        self._api_key = api_key.strip()
        self._model = model.strip() or DEFAULT_MODEL

    def answer(
        self,
        topic: str,
        verified_context: Mapping,
        question: str | None = None,
        history: list[Mapping] | None = None,
    ) -> str:
        question = question or str(verified_context.get("question", topic))
        if history is None:
            candidate_history = verified_context.get("history", [])
            history = (
                candidate_history if isinstance(candidate_history, list) else []
            )
        safe_history = [
            {
                "role": message["role"],
                "content": redact_sensitive_input(
                    str(message["content"])
                )[:500],
            }
            for message in (history or [])[-4:]
            if isinstance(message, Mapping)
            and message.get("role") in {"user", "assistant"}
            and isinstance(message.get("content"), str)
        ]
        messages = [
            {
                "role": "system",
                "content": (
                    "Answer the user's current question briefly and naturally. "
                    "Use only supplied verified context; do not invent payment "
                    "policies, transaction facts, or metrics. Treat prior "
                    "messages only as conversational context. The context "
                    "contains aggregate synthetic demo data or public FAQ "
                    "guidance, never customer records. Never ask for or reveal "
                    "card numbers, CVVs, PINs, passwords, or OTPs. If the "
                    "context cannot answer the question, say what is missing."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "topic": topic,
                        "question": redact_sensitive_input(
                            (question or topic)[:500]
                        ),
                        "history": safe_history,
                        "verified_context": _sanitize_context(
                            verified_context
                        ),
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                ),
            },
        ]
        body = json.dumps(
            {
                "model": self._model,
                "messages": messages,
                "temperature": 0,
                "max_tokens": 250,
            }
        ).encode("utf-8")
        request = Request(
            API_URL,
            data=body,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            raise AIProviderError(
                f"The AI provider returned HTTP {error.code}."
            ) from error
        except (URLError, TimeoutError) as error:
            raise AIProviderError("The AI provider request failed.") from error
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise AIProviderError(
                "The AI provider returned an invalid response."
            ) from error

        try:
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as error:
            raise AIProviderError(
                "The AI provider response did not contain an answer."
            ) from error

        if not isinstance(content, str) or not content.strip():
            raise AIProviderError(
                "The AI provider returned an empty answer."
            )
        safe_content = redact_sensitive_input(content.strip())
        if (
            safe_content != content.strip()
            or requests_sensitive_information(safe_content)
        ):
            raise AIProviderError(
                "The AI provider returned unsafe payment guidance."
            )
        return safe_content
