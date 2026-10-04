import pytest

from youtube_transcript_mcp.config import Settings
from youtube_transcript_mcp.models import TranscriptError


def test_environment(monkeypatch):
    monkeypatch.setenv("YTMCP_WHISPER_ENABLED", "false")
    monkeypatch.setenv("YTMCP_WHISPER_MODEL", "tiny")
    monkeypatch.setenv("YTMCP_MAX_DURATION_SECONDS", "120")
    monkeypatch.setenv("YTMCP_PROXY", "http://private-secret@proxy.example")
    settings = Settings.from_env()
    assert settings.whisper_enabled is False
    assert settings.whisper_model == "tiny"
    assert settings.max_duration_seconds == 120
    assert "private-secret" not in repr(settings)


@pytest.mark.parametrize("value", ["0", "-1", "nan", ""])
def test_invalid_limit(monkeypatch, value):
    monkeypatch.setenv("YTMCP_MAX_DOWNLOAD_MB", value)
    with pytest.raises(TranscriptError, match="positive integer"):
        Settings.from_env()


def test_invalid_boolean(monkeypatch):
    monkeypatch.setenv("YTMCP_WHISPER_ENABLED", "invalid")
    with pytest.raises(TranscriptError, match="true or false"):
        Settings.from_env()


@pytest.mark.parametrize(
    "value,expected", [(None, None), ("", None), ("  ", None), ("hi", "hi"), (" EN ", "en")]
)
def test_whisper_language_env(monkeypatch, value, expected):
    if value is None:
        monkeypatch.delenv("YTMCP_WHISPER_LANGUAGE", raising=False)
    else:
        monkeypatch.setenv("YTMCP_WHISPER_LANGUAGE", value)
    assert Settings.from_env().whisper_language == expected


def test_debug_env(monkeypatch):
    monkeypatch.setenv("YTMCP_DEBUG", "true")
    assert Settings.from_env().debug
    monkeypatch.setenv("YTMCP_DEBUG", "false")
    assert not Settings.from_env().debug
    monkeypatch.setenv("YTMCP_DEBUG", "invalid")
    with pytest.raises(TranscriptError, match="YTMCP_DEBUG"):
        Settings.from_env()


def test_invalid_whisper_language(monkeypatch):
    monkeypatch.setenv("YTMCP_WHISPER_LANGUAGE", "../private-cookie-path")
    with pytest.raises(TranscriptError) as caught:
        Settings.from_env()
    assert "private-cookie-path" not in str(caught.value)
