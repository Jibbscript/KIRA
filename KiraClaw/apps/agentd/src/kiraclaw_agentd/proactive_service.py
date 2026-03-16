from __future__ import annotations

import asyncio
import logging

from kiraclaw_agentd.checker_inbox import FileInboxChecker
from kiraclaw_agentd.proactive_models import CheckerEvent, SuggestionRecord
from kiraclaw_agentd.proactive_store import ProactiveStore
from kiraclaw_agentd.settings import KiraClawSettings

logger = logging.getLogger(__name__)


class ProactiveService:
    def __init__(self, settings: KiraClawSettings, slack_gateway=None) -> None:
        if not settings.checker_inbox_dir or not settings.checker_processed_dir or not settings.checker_failed_dir:
            raise ValueError("checker directories must be configured")
        if not settings.proactive_state_file:
            raise ValueError("proactive state file must be configured")

        self.settings = settings
        self.slack_gateway = slack_gateway
        self.inbox = FileInboxChecker(
            settings.checker_inbox_dir,
            settings.checker_processed_dir,
            settings.checker_failed_dir,
        )
        self.store = ProactiveStore(settings.proactive_state_file, settings.proactive_history_limit)
        self._loop_task: asyncio.Task[None] | None = None
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        if not self.settings.proactive_enabled:
            logger.info("Proactive service disabled; skipping startup")
            return
        if self._loop_task is None or self._loop_task.done():
            self._loop_task = asyncio.create_task(self._run_loop(), name="kiraclaw-proactive-loop")
            logger.info("Proactive service started")

    async def stop(self) -> None:
        if self._loop_task and not self._loop_task.done():
            self._loop_task.cancel()
            try:
                await self._loop_task
            except asyncio.CancelledError:
                pass

    def enqueue_event(self, event: CheckerEvent) -> None:
        self.inbox.enqueue(event)

    async def process_now(self) -> list[SuggestionRecord]:
        async with self._lock:
            events = self.inbox.poll()
            suggestions: list[SuggestionRecord] = []
            for event in events:
                suggestions.append(await self._process_event(event))
            return suggestions

    def list_suggestions(self, limit: int = 50) -> list[SuggestionRecord]:
        return self.store.list_suggestions(limit=limit)

    async def _run_loop(self) -> None:
        while True:
            try:
                await self.process_now()
            except Exception as exc:
                logger.exception("Proactive loop failed: %s", exc)
            await asyncio.sleep(self.settings.proactive_interval_seconds)

    async def _process_event(self, event: CheckerEvent) -> SuggestionRecord:
        dedupe_key = event.dedupe_key or f"{event.source}:{event.event_id}"

        if self.store.has_processed(dedupe_key):
            suggestion = SuggestionRecord.from_event(
                event,
                dedupe_key=dedupe_key,
                state="skipped_duplicate",
            )
            self.store.record(suggestion)
            return suggestion

        suggestion = SuggestionRecord.from_event(
            event,
            dedupe_key=dedupe_key,
            state="queued",
        )

        channel_id = event.channel_id or self.settings.proactive_default_channel_id or None
        if self.settings.proactive_auto_dispatch and channel_id and self.slack_gateway and self.slack_gateway.configured:
            try:
                await self.slack_gateway.send_message(
                    channel=channel_id,
                    text=event.suggestion_text,
                    thread_ts=event.thread_ts,
                )
                suggestion.state = "dispatched"
            except Exception as exc:
                suggestion.state = "failed"
                suggestion.dispatch_error = str(exc)

        self.store.record(suggestion)
        return suggestion
