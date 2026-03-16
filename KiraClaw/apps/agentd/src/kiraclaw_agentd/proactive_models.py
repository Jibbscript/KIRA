from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from pydantic import BaseModel, Field


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class CheckerEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    source: str
    title: str
    summary: str
    suggestion_text: str
    execution_prompt: str | None = None
    channel_id: str | None = None
    user_id: str | None = None
    thread_ts: str | None = None
    dedupe_key: str | None = None
    created_at: str = Field(default_factory=utc_now)
    metadata: dict[str, str] = Field(default_factory=dict)


class SuggestionRecord(BaseModel):
    suggestion_id: str = Field(default_factory=lambda: str(uuid4()))
    event_id: str
    source: str
    title: str
    summary: str
    suggestion_text: str
    execution_prompt: str | None = None
    channel_id: str | None = None
    user_id: str | None = None
    thread_ts: str | None = None
    dedupe_key: str
    created_at: str = Field(default_factory=utc_now)
    state: str
    dispatch_error: str | None = None
    metadata: dict[str, str] = Field(default_factory=dict)

    @classmethod
    def from_event(
        cls,
        event: CheckerEvent,
        *,
        dedupe_key: str,
        state: str,
        dispatch_error: str | None = None,
    ) -> "SuggestionRecord":
        return cls(
            event_id=event.event_id,
            source=event.source,
            title=event.title,
            summary=event.summary,
            suggestion_text=event.suggestion_text,
            execution_prompt=event.execution_prompt,
            channel_id=event.channel_id,
            user_id=event.user_id,
            thread_ts=event.thread_ts,
            dedupe_key=dedupe_key,
            state=state,
            dispatch_error=dispatch_error,
            metadata=event.metadata,
        )


class ProactiveState(BaseModel):
    processed_keys: dict[str, str] = Field(default_factory=dict)
    suggestions: list[SuggestionRecord] = Field(default_factory=list)
