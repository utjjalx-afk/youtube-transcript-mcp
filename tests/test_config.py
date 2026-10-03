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
