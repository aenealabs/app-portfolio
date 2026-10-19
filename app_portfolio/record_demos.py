"""Read the demo contracts with the live model and save the responses for offline replay.

Usage: python -m app_portfolio.record_demos
Credentials come from the environment (API key, `ant auth login`, or workload identity
federation in CI).
"""

import sys
from dataclasses import replace

from app_portfolio.config import load_settings
from app_portfolio.llm import LLMError
from app_portfolio.llm.anthropic_provider import AnthropicProvider
from app_portfolio.llm.replay import record
from app_portfolio.portfolio import Contract, check_terms, reading_input


def demo_contracts(settings) -> list[Contract]:
    return [Contract(name=p.name, text=p.read_text())
            for p in sorted((settings.dataset_dir / "contracts").glob("*.md"))]


def main() -> int:
    settings = replace(load_settings(), llm_provider="anthropic")
    provider = AnthropicProvider(settings.model)
    failures = 0
    for c in demo_contracts(settings):
        text = reading_input(c)
        try:
            terms = provider.read_contract(text)
        except LLMError as e:
            failures += 1
            print(f"FAIL {c.name}: {e}", file=sys.stderr)
            continue
        path = record(settings.replay_dir, text, terms)
        checked = check_terms(terms, c.text)
        flagged = [x.name for x in checked if x.term and not x.ok]
        print(f"ok   {c.name}: {sum(x.ok for x in checked)} checked, flagged {flagged} "
              f"-> {path.name}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
