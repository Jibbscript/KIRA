from kiraclaw_agentd.slack_adapter import (
    _clean_prompt_text,
    _is_authorized_user_name,
    _parse_allowed_names,
    _reply_thread_ts_from_event,
    _session_id_from_event,
    _should_handle_message,
)


def test_clean_prompt_text_strips_app_mentions_and_normalizes_whitespace() -> None:
    text = "  <@U123ABC>   please   summarize   this thread  "
    assert _clean_prompt_text(text, mention=True) == "please summarize this thread"


def test_clean_prompt_text_keeps_dm_text_intact() -> None:
    assert _clean_prompt_text("  hello   from   dm  ", mention=False) == "hello from dm"


def test_should_handle_message_only_accepts_human_dms() -> None:
    assert _should_handle_message({"channel_type": "im"}) is True
    assert _should_handle_message({"channel_type": "channel"}) is False
    assert _should_handle_message({"channel_type": "im", "subtype": "message_changed"}) is False
    assert _should_handle_message({"channel_type": "im", "bot_id": "B123"}) is False


def test_dm_messages_use_channel_session_and_main_channel_reply() -> None:
    event = {"channel": "D123", "channel_type": "im", "ts": "111.222"}
    assert _session_id_from_event(event) == "slack:dm:D123"
    assert _reply_thread_ts_from_event(event) is None


def test_channel_messages_reply_in_thread() -> None:
    event = {"channel": "C123", "channel_type": "channel", "ts": "111.222"}
    assert _session_id_from_event(event) == "slack:C123:111.222"
    assert _reply_thread_ts_from_event(event) == "111.222"


def test_parse_allowed_names_splits_and_trims_commas() -> None:
    assert _parse_allowed_names(" Jiho, 전지호 , Kris ") == ["Jiho", "전지호", "Kris"]


def test_authorized_user_name_uses_case_insensitive_substring_match() -> None:
    assert _is_authorized_user_name("Jiho Jeon", "Jiho, Kris") is True
    assert _is_authorized_user_name("전지호", "Jiho, 전지호") is True
    assert _is_authorized_user_name("Someone Else", "Jiho, 전지호") is False
    assert _is_authorized_user_name("Anyone", "") is True
