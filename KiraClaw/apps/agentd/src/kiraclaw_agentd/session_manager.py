from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
import time
from typing import Any, Callable
from uuid import uuid4

from kiraclaw_agentd.engine import KiraClawEngine, RunResult


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class RunRequest:
    prompt: str
    provider: str | None = None
    model: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RunRecord:
    run_id: str
    session_id: str
    state: str
    prompt: str
    created_at: str
    started_at: str | None = None
    finished_at: str | None = None
    result: RunResult | None = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class SessionLane:
    def __init__(
        self,
        session_id: str,
        engine: KiraClawEngine,
        idle_timeout_seconds: float,
        on_idle: Callable[[str, "SessionLane"], None],
    ) -> None:
        self.session_id = session_id
        self.engine = engine
        self.idle_timeout_seconds = max(0.05, idle_timeout_seconds)
        self._on_idle = on_idle
        self.queue: asyncio.Queue[tuple[RunRecord, asyncio.Future[RunRecord], RunRequest]] = asyncio.Queue()
        self.worker_task: asyncio.Task[None] | None = None
        self.last_activity_monotonic = time.monotonic()

    @property
    def active(self) -> bool:
        return self.worker_task is not None and not self.worker_task.done()

    def touch(self) -> None:
        self.last_activity_monotonic = time.monotonic()

    def ensure_worker(self) -> None:
        if self.worker_task is None or self.worker_task.done():
            self.worker_task = asyncio.create_task(self._worker(), name=f"session-lane:{self.session_id}")

    async def enqueue(self, request: RunRequest, record: RunRecord) -> RunRecord:
        self.touch()
        self.ensure_worker()
        future: asyncio.Future[RunRecord] = asyncio.get_running_loop().create_future()
        await self.queue.put((record, future, request))
        return await future

    async def _worker(self) -> None:
        try:
            while True:
                try:
                    record, future, request = await asyncio.wait_for(
                        self.queue.get(),
                        timeout=self.idle_timeout_seconds,
                    )
                except asyncio.TimeoutError:
                    if self.queue.empty():
                        break
                    continue

                self.touch()
                try:
                    record.state = "running"
                    record.started_at = utc_now()
                    result = await asyncio.to_thread(
                        self.engine.run,
                        request.prompt,
                        request.provider,
                        request.model,
                    )
                    record.result = result
                    record.state = "completed"
                    record.finished_at = utc_now()
                    if not future.done():
                        future.set_result(record)
                except Exception as exc:
                    record.error = str(exc)
                    record.state = "failed"
                    record.finished_at = utc_now()
                    if not future.done():
                        future.set_result(record)
                finally:
                    self.touch()
                    self.queue.task_done()
        except asyncio.CancelledError:
            while not self.queue.empty():
                try:
                    record, future, _request = self.queue.get_nowait()
                except asyncio.QueueEmpty:
                    break
                record.error = "Session lane was stopped before the run could start."
                record.state = "failed"
                record.finished_at = utc_now()
                if not future.done():
                    future.set_result(record)
                self.queue.task_done()
            raise
        finally:
            self.worker_task = None
            self.touch()
            self._on_idle(self.session_id, self)

    async def stop(self) -> None:
        task = self.worker_task
        if task is None or task.done():
            self.worker_task = None
            return
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


class SessionManager:
    def __init__(self, engine: KiraClawEngine) -> None:
        self.engine = engine
        self.record_limit = max(1, engine.settings.session_record_limit)
        self.idle_timeout_seconds = max(0.05, engine.settings.session_idle_seconds)
        self._lanes: dict[str, SessionLane] = {}
        self._records: dict[str, list[RunRecord]] = {}

    def _append_record(self, session_id: str, record: RunRecord) -> None:
        records = self._records.setdefault(session_id, [])
        records.append(record)
        if len(records) > self.record_limit:
            self._records[session_id] = records[-self.record_limit:]

    def _release_lane(self, session_id: str, lane: SessionLane) -> None:
        current_lane = self._lanes.get(session_id)
        if current_lane is lane and lane.queue.empty() and not lane.active:
            self._lanes.pop(session_id, None)

    def _get_lane(self, session_id: str) -> SessionLane:
        lane = self._lanes.get(session_id)
        if lane is None:
            lane = SessionLane(
                session_id=session_id,
                engine=self.engine,
                idle_timeout_seconds=self.idle_timeout_seconds,
                on_idle=self._release_lane,
            )
            self._lanes[session_id] = lane
        return lane

    async def run(
        self,
        session_id: str,
        prompt: str,
        provider: str | None = None,
        model: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> RunRecord:
        lane = self._get_lane(session_id)
        record = RunRecord(
            run_id=str(uuid4()),
            session_id=session_id,
            state="queued",
            prompt=prompt,
            created_at=utc_now(),
            metadata=metadata or {},
        )
        self._append_record(session_id, record)
        return await lane.enqueue(
            RunRequest(
                prompt=prompt,
                provider=provider,
                model=model,
                metadata=metadata or {},
            ),
            record,
        )

    def list_sessions(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        session_ids = sorted(set(self._records.keys()) | set(self._lanes.keys()))
        for session_id in session_ids:
            lane = self._lanes.get(session_id)
            records = self._records.get(session_id, [])
            latest = records[-1] if records else None
            rows.append(
                {
                    "session_id": session_id,
                    "queued_runs": lane.queue.qsize() if lane is not None else 0,
                    "active": lane.active if lane is not None else False,
                    "latest_state": latest.state if latest else None,
                    "latest_run_id": latest.run_id if latest else None,
                    "latest_finished_at": latest.finished_at if latest else None,
                }
            )
        return rows

    def get_session_records(self, session_id: str) -> list[RunRecord]:
        return list(self._records.get(session_id, []))

    async def stop(self) -> None:
        lanes = list(self._lanes.values())
        for lane in lanes:
            await lane.stop()
        self._lanes.clear()
