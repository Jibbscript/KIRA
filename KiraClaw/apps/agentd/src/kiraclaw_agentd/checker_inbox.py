from __future__ import annotations

import json
from pathlib import Path

from kiraclaw_agentd.proactive_models import CheckerEvent


class FileInboxChecker:
    def __init__(self, inbox_dir: Path, processed_dir: Path, failed_dir: Path) -> None:
        self.inbox_dir = inbox_dir
        self.processed_dir = processed_dir
        self.failed_dir = failed_dir

    def enqueue(self, event: CheckerEvent) -> Path:
        path = self.inbox_dir / f"{event.event_id}.json"
        path.write_text(event.model_dump_json(indent=2), encoding="utf-8")
        return path

    def poll(self) -> list[CheckerEvent]:
        events: list[CheckerEvent] = []
        for path in sorted(self.inbox_dir.glob("*.json")):
            target_dir = self.processed_dir
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                events.append(CheckerEvent.model_validate(payload))
            except Exception:
                target_dir = self.failed_dir
            finally:
                path.rename(target_dir / path.name)
        return events
