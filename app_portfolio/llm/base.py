"""Provider interface shared by the live and replay LLM backends."""

import hashlib
from typing import Protocol

from app_portfolio.models import ContractTerms


class LLMError(Exception):
    """A provider could not produce a usable result; the message is user-facing."""


class LLMProvider(Protocol):
    name: str

    def read_contract(self, input_text: str) -> ContractTerms: ...


def input_key(text: str) -> str:
    """Stable key for an input, insensitive to whitespace and case differences."""
    normalized = " ".join(text.split()).lower()
    return hashlib.sha256(normalized.encode()).hexdigest()[:16]
