"""Offline provider: serves recorded responses so demos never depend on the network."""

import json
from pathlib import Path

from app_portfolio.llm.base import LLMError, input_key
from app_portfolio.models import ContractTerms


class ReplayProvider:
    name = "replay"

    def __init__(self, replay_dir: Path):
        self.replay_dir = replay_dir

    def read_contract(self, input_text: str) -> ContractTerms:
        path = replay_path(self.replay_dir, input_text)
        if not path.exists():
            raise LLMError("Offline demo mode has recorded readings for the demo contracts "
                           "only. Switch to live AI mode for other contracts.")
        return ContractTerms.model_validate(json.loads(path.read_text())["output"])


def replay_path(replay_dir: Path, input_text: str) -> Path:
    return replay_dir / "contracts" / f"{input_key(input_text)}.json"


def record(replay_dir: Path, input_text: str, output: ContractTerms) -> Path:
    path = replay_path(replay_dir, input_text)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"input": input_text, "output": output.model_dump()},
                               indent=2) + "\n")
    return path
