from __future__ import annotations

import asyncio
import json
import os
from typing import Any, Callable

import aiohttp

from krim_sdk.tools import Tool
from kiraclaw_agentd.settings import KiraClawSettings


DiscordRequester = Callable[[str, int | str, dict[str, Any], str | None], dict[str, Any]]


def _build_result(success: bool, **payload: Any) -> str:
    body = {"success": success, **payload}
    return json.dumps(body, ensure_ascii=False, indent=2)


def _make_requester(bot_token: str) -> DiscordRequester:
    base_url = "https://discord.com/api/v10/channels"
    headers = {"Authorization": f"Bot {bot_token}"}

    async def _request_async(
        method: str,
        channel_id: int | str,
        payload: dict[str, Any],
        file_path: str | None = None,
    ) -> dict[str, Any]:
        async with aiohttp.ClientSession(headers=headers) as session:
            target_url = f"{base_url}/{channel_id}/messages"
            if file_path:
                form = aiohttp.FormData()
                form.add_field("payload_json", json.dumps(payload, ensure_ascii=False))
                with open(file_path, "rb") as handle:
                    form.add_field(
                        "files[0]",
                        handle,
                        filename=os.path.basename(file_path),
                        content_type="application/octet-stream",
                    )
                    async with session.request(method, target_url, data=form) as response:
                        return {"status": response.status, "body": await response.json()}

            async with session.request(method, target_url, json=payload) as response:
                return {"status": response.status, "body": await response.json()}

    def _request(
        method: str,
        channel_id: int | str,
        payload: dict[str, Any],
        file_path: str | None = None,
    ) -> dict[str, Any]:
        return asyncio.run(_request_async(method, channel_id, payload, file_path))

    return _request


class _DiscordToolBase(Tool):
    def __init__(self, requester: DiscordRequester) -> None:
        self._requester = requester

    def _run_with_error_boundary(self, fn: Callable[[], str]) -> str:
        try:
            return fn()
        except Exception as exc:
            return _build_result(False, error=str(exc))


class DiscordSendMessageTool(_DiscordToolBase):
    name = "discord_send_message"
    description = "Send a message to any Discord channel or DM when Discord is enabled as an allowed channel."
    parameters = {
        "channel_id": {
            "type": "string",
            "description": "Discord channel ID to send to.",
        },
        "text": {
            "type": "string",
            "description": "Message text to send.",
        },
        "reply_to_message_id": {
            "type": "integer",
            "description": "Optional Discord message ID to reply to.",
            "optional": True,
        },
    }

    def run(self, channel_id: str, text: str, reply_to_message_id: int | None = None) -> str:
        def _send() -> str:
            payload: dict[str, Any] = {"content": text}
            if reply_to_message_id is not None:
                payload["message_reference"] = {"message_id": str(reply_to_message_id)}
                payload["allowed_mentions"] = {"replied_user": False}
            response = self._requester("POST", channel_id, payload, None)
            if response.get("status", 500) >= 400:
                return _build_result(False, error=str(response.get("body")))
            body = response.get("body", {})
            return _build_result(True, channel_id=channel_id, message_id=body.get("id"))

        return self._run_with_error_boundary(_send)


class DiscordUploadFileTool(_DiscordToolBase):
    name = "discord_upload_file"
    description = (
        "Upload a local file to a Discord channel or DM when the file already exists on disk and the user wants it sent."
    )
    parameters = {
        "channel_id": {
            "type": "string",
            "description": "Discord channel ID to upload into.",
        },
        "file_path": {
            "type": "string",
            "description": "Absolute local file path to upload.",
        },
        "caption": {
            "type": "string",
            "description": "Optional text to send with the file.",
            "optional": True,
        },
        "reply_to_message_id": {
            "type": "integer",
            "description": "Optional Discord message ID to reply to.",
            "optional": True,
        },
    }

    def run(
        self,
        channel_id: str,
        file_path: str,
        caption: str | None = None,
        reply_to_message_id: int | None = None,
    ) -> str:
        def _upload() -> str:
            if not os.path.isfile(file_path):
                return _build_result(False, error=f"file_not_found: {file_path}")

            payload: dict[str, Any] = {}
            if caption:
                payload["content"] = caption
            if reply_to_message_id is not None:
                payload["message_reference"] = {"message_id": str(reply_to_message_id)}
                payload["allowed_mentions"] = {"replied_user": False}
            response = self._requester("POST", channel_id, payload, file_path)
            if response.get("status", 500) >= 400:
                return _build_result(False, error=str(response.get("body")))
            body = response.get("body", {})
            attachments = body.get("attachments", [])
            attachment = attachments[0] if attachments else {}
            return _build_result(
                True,
                channel_id=channel_id,
                message_id=body.get("id"),
                file_name=attachment.get("filename") or os.path.basename(file_path),
                url=attachment.get("url"),
            )

        return self._run_with_error_boundary(_upload)


def build_discord_tools(
    settings: KiraClawSettings,
    *,
    requester: DiscordRequester | None = None,
) -> list[Tool]:
    if not settings.discord_enabled or not settings.discord_bot_token:
        return []

    request_fn = requester or _make_requester(settings.discord_bot_token)
    return [
        DiscordSendMessageTool(request_fn),
        DiscordUploadFileTool(request_fn),
    ]
