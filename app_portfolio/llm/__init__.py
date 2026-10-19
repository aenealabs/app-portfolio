from app_portfolio.config import Settings
from app_portfolio.llm.base import LLMError, LLMProvider
from app_portfolio.llm.replay import ReplayProvider, record


class RecordingProvider:
    """Wraps a live provider and saves each response for later offline replay."""

    def __init__(self, inner: LLMProvider, settings: Settings):
        self.inner = inner
        self.settings = settings
        self.name = f"{inner.name} (recording)"

    def read_contract(self, input_text: str):
        result = self.inner.read_contract(input_text)
        record(self.settings.replay_dir, input_text, result)
        return result


def build_provider(settings: Settings) -> LLMProvider:
    if settings.llm_provider == "replay":
        return ReplayProvider(settings.replay_dir)
    if settings.llm_provider in ("anthropic", "foundry"):
        if settings.llm_provider == "anthropic":
            from app_portfolio.llm.anthropic_provider import AnthropicProvider

            provider = AnthropicProvider(settings.model)
        else:
            from app_portfolio.llm.foundry import foundry_provider

            provider = foundry_provider(settings.model)
        return RecordingProvider(provider, settings) if settings.record else provider
    raise ValueError(f"Unknown AP_LLM_PROVIDER: {settings.llm_provider!r}")


__all__ = ["LLMError", "LLMProvider", "build_provider"]
