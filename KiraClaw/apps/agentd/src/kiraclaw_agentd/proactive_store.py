from __future__ import annotations

import json
from pathlib import Path

from kiraclaw_agentd.proactive_models import ProactiveState, SuggestionRecord, utc_now


class ProactiveStore:
    def __init__(self, state_file: Path, history_limit: int = 200) -> None:
        self.state_file = state_file
        self.history_limit = history_limit

    def load(self) -> ProactiveState:
        if not self.state_file.exists():
            return ProactiveState()
        payload = json.loads(self.state_file.read_text(encoding="utf-8"))
        return ProactiveState.model_validate(payload)

    def save(self, state: ProactiveState) -> None:
        self.state_file.write_text(state.model_dump_json(indent=2), encoding="utf-8")

    def has_processed(self, dedupe_key: str) -> bool:
        state = self.load()
        return dedupe_key in state.processed_keys

    def record(self, suggestion: SuggestionRecord) -> None:
        state = self.load()
        if suggestion.state != "skipped_duplicate":
            state.processed_keys[suggestion.dedupe_key] = utc_now()
        state.suggestions.append(suggestion)
        if len(state.suggestions) > self.history_limit:
            state.suggestions = state.suggestions[-self.history_limit :]
        self.save(state)

    def list_suggestions(self, limit: int = 50) -> list[SuggestionRecord]:
        state = self.load()
        if limit <= 0:
            return []
        return list(reversed(state.suggestions[-limit:]))
