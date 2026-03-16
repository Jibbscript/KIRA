from __future__ import annotations

import logging
import sys
import threading
from pathlib import Path

from krim.mcp import McpServer, McpServerConfig

from kiraclaw_agentd.settings import KiraClawSettings

logger = logging.getLogger(__name__)

_MODULE_DIR = Path(__file__).resolve().parent
TIME_MCP_COMMAND = ["npx", "-y", "@theo.foobar/mcp-time"]
FILES_MCP_COMMAND = [sys.executable, str(_MODULE_DIR / "files_mcp_server.py")]
SCHEDULER_MCP_COMMAND = [sys.executable, str(_MODULE_DIR / "scheduler_mcp_server.py")]
CONTEXT7_MCP_COMMAND = ["npx", "-y", "@upstash/context7-mcp"]
ARXIV_MCP_COMMAND = ["npx", "-y", "@langgpt/arxiv-paper-mcp@latest"]
YOUTUBE_INFO_MCP_COMMAND = ["npx", "-y", "@limecooler/yt-info-mcp"]
PERPLEXITY_MCP_COMMAND = ["npx", "-y", "server-perplexity-ask"]
GITLAB_MCP_COMMAND = ["npx", "-y", "@zereight/mcp-gitlab"]
MS365_MCP_COMMAND = ["npx", "-y", "@batteryho/lokka-cached"]
ATLASSIAN_MCP_COMMAND = ["npx", "-y", "mcp-remote", "https://mcp.atlassian.com/v1/sse"]
TABLEAU_MCP_COMMAND = ["npx", "-y", "@tableau/mcp-server@latest"]
DEFERRED_STARTUP_SERVER_NAMES = {"perplexity", "gitlab", "ms365"}


def _is_present(value: str | None) -> bool:
    return bool(value and value.strip())


def _normalize_gitlab_api_url(url: str) -> str:
    normalized = url.strip().rstrip("/")
    if not normalized:
        return "https://gitlab.com/api/v4"
    if normalized.endswith("/api/v4"):
        return normalized
    if normalized == "https://gitlab.com":
        return "https://gitlab.com/api/v4"
    return f"{normalized}/api/v4" if "/api/" not in normalized else normalized


def _external_mcp_configs(settings: KiraClawSettings) -> list[McpServerConfig]:
    configs: list[McpServerConfig] = []

    if settings.perplexity_enabled and _is_present(settings.perplexity_api_key):
        configs.append(
            McpServerConfig(
                name="perplexity",
                command=PERPLEXITY_MCP_COMMAND,
                env={"PERPLEXITY_API_KEY": settings.perplexity_api_key},
            )
        )

    if settings.gitlab_enabled and _is_present(settings.gitlab_personal_access_token):
        configs.append(
            McpServerConfig(
                name="gitlab",
                command=GITLAB_MCP_COMMAND,
                env={
                    "GITLAB_PERSONAL_ACCESS_TOKEN": settings.gitlab_personal_access_token,
                    "GITLAB_API_URL": _normalize_gitlab_api_url(settings.gitlab_api_url),
                    "GITLAB_READ_ONLY_MODE": "false",
                    "USE_GITLAB_WIKI": "false",
                    "USE_MILESTONE": "false",
                    "USE_PIPELINE": "false",
                },
            )
        )

    if settings.ms365_enabled and _is_present(settings.ms365_client_id) and _is_present(settings.ms365_tenant_id):
        configs.append(
            McpServerConfig(
                name="ms365",
                command=MS365_MCP_COMMAND,
                env={
                    "TENANT_ID": settings.ms365_tenant_id,
                    "CLIENT_ID": settings.ms365_client_id,
                    "USE_INTERACTIVE": "true",
                },
            )
        )

    if settings.atlassian_enabled:
        resource = settings.atlassian_confluence_site_url.strip() or settings.atlassian_jira_site_url.strip()
        command = list(ATLASSIAN_MCP_COMMAND)
        if resource:
            command.extend(["--resource", resource.rstrip("/") + "/"])
        configs.append(
            McpServerConfig(
                name="atlassian",
                command=command,
                wire_format="line",
            )
        )

    if (
        settings.tableau_enabled
        and _is_present(settings.tableau_server)
        and _is_present(settings.tableau_site_name)
        and _is_present(settings.tableau_pat_name)
        and _is_present(settings.tableau_pat_value)
    ):
        configs.append(
            McpServerConfig(
                name="tableau",
                command=TABLEAU_MCP_COMMAND,
                env={
                    "SERVER": settings.tableau_server,
                    "SITE_NAME": settings.tableau_site_name,
                    "PAT_NAME": settings.tableau_pat_name,
                    "PAT_VALUE": settings.tableau_pat_value,
                },
            )
        )

    return configs


def build_mcp_server_configs(settings: KiraClawSettings) -> list[McpServerConfig]:
    if not settings.mcp_enabled:
        return []

    configs: list[McpServerConfig] = []
    if settings.mcp_time_enabled:
        configs.append(
            McpServerConfig(
                name="time",
                command=TIME_MCP_COMMAND,
            )
        )
    if settings.mcp_files_enabled:
        configs.append(
            McpServerConfig(
                name="files",
                command=FILES_MCP_COMMAND,
                env={"KIRACLAW_WORKSPACE_DIR": str(settings.workspace_dir)},
            )
        )
    if settings.mcp_scheduler_enabled and settings.schedule_file is not None:
        configs.append(
            McpServerConfig(
                name="scheduler",
                command=SCHEDULER_MCP_COMMAND,
                env={"KIRACLAW_SCHEDULE_FILE": str(settings.schedule_file)},
            )
        )
    if settings.mcp_context7_enabled:
        configs.append(
            McpServerConfig(
                name="context7",
                command=CONTEXT7_MCP_COMMAND,
                wire_format="line",
            )
        )
    if settings.mcp_arxiv_enabled:
        configs.append(
            McpServerConfig(
                name="arxiv",
                command=ARXIV_MCP_COMMAND,
                wire_format="line",
            )
        )
    if settings.mcp_youtube_info_enabled:
        configs.append(
            McpServerConfig(
                name="youtube-info",
                command=YOUTUBE_INFO_MCP_COMMAND,
                wire_format="line",
            )
        )
    configs.extend(_external_mcp_configs(settings))
    return configs


def split_startup_mcp_server_configs(configs: list[McpServerConfig]) -> tuple[list[McpServerConfig], list[McpServerConfig]]:
    eager: list[McpServerConfig] = []
    deferred: list[McpServerConfig] = []
    for config in configs:
        if config.name in DEFERRED_STARTUP_SERVER_NAMES:
            deferred.append(config)
        else:
            eager.append(config)
    return eager, deferred


class McpRuntime:
    def __init__(self, settings: KiraClawSettings) -> None:
        self.settings = settings
        self.state: str = "disabled"
        self.last_error: str | None = None
        self.failed_server_names: list[str] = []
        self._servers: list[McpServer] = []
        self._deferred_configs: list[McpServerConfig] = []
        self.tools = []
        self.loaded_server_names: list[str] = []
        self.deferred_server_names: list[str] = []
        self._lock = threading.RLock()

    def _start_server(self, config: McpServerConfig) -> tuple[McpServer | None, str | None]:
        try:
            server = McpServer(config)
            server.start()
            logger.info("MCP server started: %s (%s tools)", config.name, len(server.tools))
            return server, None
        except Exception as exc:
            logger.exception("Failed to start MCP server %s", config.name)
            return None, str(exc)

    def _refresh_state_locked(self) -> None:
        if self._servers:
            self.state = "running"
        elif self.last_error:
            self.state = "failed"
        elif self._deferred_configs:
            self.state = "configured"
        else:
            self.state = "disabled"

    def _activate_configs(self, configs: list[McpServerConfig]) -> list[str]:
        loaded_names: list[str] = []
        failed_names: list[str] = []

        for config in configs:
            with self._lock:
                if config.name in self.loaded_server_names or config.name in self.failed_server_names:
                    continue

            if config.name in loaded_names or config.name in failed_names:
                continue

            server, error = self._start_server(config)
            if server is None:
                self.last_error = f"{config.name}: {error}"
                failed_names.append(config.name)
                continue

            with self._lock:
                self._servers.append(server)
                self.tools.extend(server.tools)
                self.loaded_server_names.append(config.name)
                loaded_names.append(config.name)

        with self._lock:
            if failed_names:
                for name in failed_names:
                    if name not in self.failed_server_names:
                        self.failed_server_names.append(name)
            attempted = {config.name for config in configs}
            self._deferred_configs = [config for config in self._deferred_configs if config.name not in attempted]
            self.deferred_server_names = [config.name for config in self._deferred_configs]
            self._refresh_state_locked()

        return loaded_names

    async def start(self) -> None:
        await self.stop()

        configs = build_mcp_server_configs(self.settings)
        if not configs:
            with self._lock:
                self.state = "disabled"
                self.last_error = None
                self.failed_server_names = []
            return

        eager_configs, deferred_configs = split_startup_mcp_server_configs(configs)
        with self._lock:
            self.state = "starting"
            self.last_error = None
            self.failed_server_names = []
            self._deferred_configs = list(deferred_configs)
            self.deferred_server_names = [config.name for config in deferred_configs]

        for config in deferred_configs:
            logger.info("Deferring MCP server startup until later: %s", config.name)

        self._activate_configs(eager_configs)

    def activate_deferred_servers(self) -> list[str]:
        with self._lock:
            pending = list(self._deferred_configs)
            if not pending:
                return []
            self._deferred_configs = []
            self.deferred_server_names = []
            self.state = "starting" if not self._servers else self.state

        return self._activate_configs(pending)

    async def stop(self) -> None:
        for server in list(self._servers):
            try:
                server.stop()
            except Exception:
                logger.exception("Failed to stop MCP server %s", server.config.name)

        with self._lock:
            self._servers = []
            self._deferred_configs = []
            self.tools = []
            self.loaded_server_names = []
            self.deferred_server_names = []
            self.failed_server_names = []
            self.last_error = None
            self.state = "disabled" if not self.settings.mcp_enabled else "configured"

    @property
    def tool_names(self) -> list[str]:
        return [tool.name for tool in self.tools]
