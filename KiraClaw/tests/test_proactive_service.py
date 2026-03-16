from __future__ import annotations

import asyncio

from kiraclaw_agentd.proactive_models import CheckerEvent
from kiraclaw_agentd.proactive_service import ProactiveService
from kiraclaw_agentd.settings import KiraClawSettings


class DummySlackGateway:
    def __init__(self) -> None:
        self.configured = True
        self.messages: list[dict[str, str | None]] = []

    async def send_message(self, channel: str, text: str, thread_ts: str | None = None) -> None:
        self.messages.append(
            {
                "channel": channel,
                "text": text,
                "thread_ts": thread_ts,
            }
        )


def _make_settings(tmp_path, **overrides) -> KiraClawSettings:
    settings = KiraClawSettings(
        data_dir=tmp_path / "data",
        workspace_dir=tmp_path / "workspace",
        home_mode="modern",
        slack_enabled=False,
        **overrides,
    )
    settings.ensure_directories()
    return settings


def test_proactive_service_records_queued_suggestion(tmp_path) -> None:
    settings = _make_settings(tmp_path)
    service = ProactiveService(settings)
    event = CheckerEvent(
        source="jira",
        title="Assigned issue updated",
        summary="PROJ-123 moved to In Review.",
        suggestion_text="I can summarize the review impact for PROJ-123.",
        dedupe_key="jira:PROJ-123",
    )

    service.enqueue_event(event)
    processed = asyncio.run(service.process_now())

    assert len(processed) == 1
    assert processed[0].state == "queued"
    assert service.list_suggestions(limit=5)[0].state == "queued"


def test_proactive_service_marks_duplicate_events(tmp_path) -> None:
    settings = _make_settings(tmp_path)
    service = ProactiveService(settings)

    first = CheckerEvent(
        source="jira",
        title="Assigned issue updated",
        summary="PROJ-123 moved to In Review.",
        suggestion_text="I can summarize the review impact for PROJ-123.",
        dedupe_key="jira:PROJ-123",
    )
    duplicate = CheckerEvent(
        source="jira",
        title="Assigned issue updated",
        summary="PROJ-123 moved to In Review.",
        suggestion_text="I can summarize the review impact for PROJ-123.",
        dedupe_key="jira:PROJ-123",
    )

    service.enqueue_event(first)
    asyncio.run(service.process_now())
    service.enqueue_event(duplicate)
    processed = asyncio.run(service.process_now())

    assert len(processed) == 1
    assert processed[0].state == "skipped_duplicate"
    suggestions = service.list_suggestions(limit=5)
    assert suggestions[0].state == "skipped_duplicate"
    assert suggestions[1].state == "queued"


def test_proactive_service_auto_dispatches_when_enabled(tmp_path) -> None:
    settings = _make_settings(
        tmp_path,
        proactive_auto_dispatch=True,
        proactive_default_channel_id="D123456",
    )
    slack_gateway = DummySlackGateway()
    service = ProactiveService(settings, slack_gateway)
    event = CheckerEvent(
        source="confluence",
        title="Page changed",
        summary="Roadmap page was updated.",
        suggestion_text="I saw the roadmap page changed. I can summarize what moved.",
    )

    service.enqueue_event(event)
    processed = asyncio.run(service.process_now())

    assert processed[0].state == "dispatched"
    assert slack_gateway.messages == [
        {
            "channel": "D123456",
            "text": "I saw the roadmap page changed. I can summarize what moved.",
            "thread_ts": None,
        }
    ]
