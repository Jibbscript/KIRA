from __future__ import annotations

import pytest

from kiraclaw_agentd.engine import KiraClawEngine
from kiraclaw_agentd.settings import KiraClawSettings


def test_engine_requires_claude_credentials(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)

    settings = KiraClawSettings(
        data_dir=tmp_path / "data",
        workspace_dir=tmp_path / "workspace",
        home_mode="modern",
        slack_enabled=False,
        provider="claude",
    )
    settings.ensure_directories()

    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        KiraClawEngine(settings).run("Say hi.")
