"""FAQ-grounded customer support responses without individual payment lookup."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Callable

from chatbots.ai_provider import (
    AIProviderError,
    redact_sensitive_input,
    requests_sensitive_information,
    validate_chat_input,
)

KNOWLEDGE_BASE_PATH = Path(__file__).with_name(
    "support_knowledge_base.json"
)
FALLBACK_ANSWER = (
    "I can help with general payment FAQs, failed or pending payments, and "
    "refund guidance. I cannot inspect an individual payment. Do not share "
    "card numbers, CVVs, PINs, passwords, or OTPs in chat."
)


@dataclass(frozen=True)
class SupportArticle:
    topic: str
    answer: str


def load_knowledge_base(path: Path = KNOWLEDGE_BASE_PATH) -> dict:
    try:
        with path.open(encoding="utf-8") as knowledge_file:
            articles = json.load(knowledge_file)
    except FileNotFoundError as error:
        raise ValueError("The support knowledge base is missing.") from error
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("The support knowledge base is invalid.") from error

    if not isinstance(articles, dict) or not articles:
        raise ValueError("The support knowledge base must contain articles.")
    for topic, article in articles.items():
        if (
            not isinstance(topic, str)
            or not isinstance(article, dict)
            or not isinstance(article.get("answer"), str)
            or not isinstance(article.get("keywords"), list)
        ):
            raise ValueError("The support knowledge base has an invalid article.")
    return articles


def find_article(
    question: str, knowledge_base: dict | None = None
) -> SupportArticle | None:
    base = (
        knowledge_base if knowledge_base is not None else load_knowledge_base()
    )
    lower = question.casefold()
    matches = []
    for topic, article in base.items():
        score = sum(
            max(1, len(str(keyword).split()))
            for keyword in article["keywords"]
            if re.search(
                rf"\b{re.escape(str(keyword).casefold())}\b",
                lower,
            )
        )
        if score:
            matches.append((score, topic, article["answer"]))
    if not matches:
        return None
    topic_priority = {
        "debited_without_success": 6,
        "failed_payment": 5,
        "pending_payment": 4,
        "refund": 3,
        "complaint": 2,
        "troubleshooting": 1,
        "payment_faq": 0,
    }
    _, topic, answer = max(
        matches,
        key=lambda item: (
            item[0],
            topic_priority.get(item[1], 0),
        ),
    )
    return SupportArticle(topic=topic, answer=answer)


def answer_support(
    question: str,
    provider: Callable[[str, dict], str] | None = None,
    knowledge_base: dict | None = None,
    history: Sequence[Mapping] | None = None,
) -> str:
    safe_question = redact_sensitive_input(validate_chat_input(question))
    prior_user_questions = [
        str(message["content"])
        for message in (history or [])[-10:]
        if isinstance(message, Mapping)
        and message.get("role") == "user"
        and isinstance(message.get("content"), str)
    ]
    article = find_article(safe_question, knowledge_base)
    lower_question = safe_question.casefold()
    follow_up = bool(
        re.fullmatch(
            r"(?:and\s+)?(?:what|how)\s+"
            r"(?:about|should|do|does|long|soon|when)\b.*",
            lower_question,
        )
        or re.fullmatch(
            r"(?:and\s+)?(?:it|that|there|then|those|them)\b.*",
            lower_question,
        )
        or re.fullmatch(
            r"(?:and\s+)?(?:should|can|could|do|will)\s+"
            r"(?:i|we|they|it|that)\b.*",
            lower_question,
        )
    )
    if article is None and follow_up:
        article = next(
            (
                candidate
                for prior_question in reversed(prior_user_questions)
                if (candidate := find_article(prior_question, knowledge_base))
            ),
            None,
        )
    if article is None:
        return (
            "I can help with failed or pending payments, debits without a "
            "successful payment, refunds, and complaints. Which of these "
            "best describes your question? I cannot look up individual "
            "payments or process refunds."
        )

    openings = {
        "failed_payment": "I understand a failed payment can be worrying. ",
        "pending_payment": "A pending status can be confusing. ",
        "refund": "Refund timing can vary. ",
        "complaint": "I'm sorry you ran into this. ",
        "troubleshooting": "Let's start with the safest checks. ",
    }
    answer = openings.get(article.topic, "") + article.answer
    if article.topic == "failed_payment" and re.search(
        r"\b(?:debit|deduct|charged|taken)\w*\b", lower_question
    ):
        answer = (
            "If your account was debited but the payment failed, avoid "
            "repeating the payment until you check its final status. Any "
            "reversal and timing depend on the bank and payment method. "
            "Contact the merchant or payment provider through its official "
            "support channel with the transaction reference."
        )
    elif article.topic == "failed_payment" and re.search(
        r"\b(?:why|reason|cause)\b", lower_question
    ):
        answer = (
            "A failed status alone does not reveal why the bank or payment "
            "provider declined it, and this demo cannot see an individual "
            "decline reason. Check the final status in your bank or payment "
            "app, then contact the merchant or provider through an official "
            "support channel for account-specific details."
        )
    elif article.topic == "pending_payment" and re.search(
        r"\b(?:retry|again|pay again|duplicate)\b", lower_question
    ):
        answer = (
            "Because the payment is still pending, check its status in your "
            "bank or payment app before retrying; a second attempt could "
            "duplicate the payment. If it does not reach a final status, "
            "contact the merchant or payment provider through its official "
            "support channel."
        )
    elif article.topic == "pending_payment" and re.search(
        r"\b(?:how long|when|time)\b", lower_question
    ):
        answer = (
            "A pending payment has not reached a final status, and this demo "
            "cannot check its live progress or promise a completion time. "
            "Check your bank or payment app and contact the merchant or "
            "provider through its official support channel if it remains "
            "pending."
        )
    elif article.topic == "refund" and re.search(
        r"\b(?:when|how long|time|status|where)\b", lower_question
    ):
        answer = (
            "Refund timing depends on the merchant, bank, and payment method. "
            "Confirm that the merchant approved it and ask for the refund "
            "reference and expected timeframe; if it does not arrive within "
            "that timeframe, contact the merchant or bank through an official "
            "channel."
        )
    elif article.topic == "refund" and re.search(
        r"\b(?:process|issue|initiate|give me)\b", lower_question
    ):
        answer = (
            "I cannot initiate or issue a refund. Ask the merchant whether "
            "the refund was approved and request its reference and expected "
            "timeframe; contact the merchant or bank through an official "
            "channel if it does not arrive."
        )
    if not re.search(r"\b(?:do not|never) share\b", answer, re.IGNORECASE):
        answer += (
            " Do not share card numbers, CVVs, PINs, passwords, or OTPs."
        )
    if any(
        message.get("role") == "user"
        and message.get("content", "").casefold() == safe_question.casefold()
        for message in (history or [])
    ):
        answer = "As a reminder, " + answer[:1].lower() + answer[1:]

    if provider is None:
        return answer

    generated = provider(
        f"support_{article.topic}",
        {
            "approved_guidance": answer,
            "question": safe_question[:500],
            "history": [
                {
                    "role": message["role"],
                    "content": redact_sensitive_input(
                        str(message["content"])
                    )[:500],
                }
                for message in (history or [])[-4:]
                if message.get("role") in {"user", "assistant"}
                and isinstance(message.get("content"), str)
            ],
        },
    )
    if not isinstance(generated, str) or any(
        character.isdigit() for character in generated
    ):
        raise AIProviderError(
            "The AI provider returned unsupported support details."
        )
    safe_generated = redact_sensitive_input(generated)
    if (
        safe_generated != generated
        or requests_sensitive_information(safe_generated)
    ):
        raise AIProviderError(
            "The AI provider returned unsafe payment guidance."
        )
    return f"{safe_generated}\n\nReference guidance: {answer}"
