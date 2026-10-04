import json
import sys

import pytest

from youtube_transcript_mcp.cli import main
from youtube_transcript_mcp.models import TranscriptError


def test_doctor(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["youtube-transcript-mcp", "doctor"])
    main()
    assert json.loads(capsys.readouterr().out)["transport"] == "stdio"


def test_export(monkeypatch, tmp_path, transcript):
    output = tmp_path / "transcript.srt"
    monkeypatch.setattr(
        "youtube_transcript_mcp.cli.TranscriptService.get_transcript",
        lambda *args: transcript,
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "youtube-transcript-mcp",
            "fetch",
            transcript.video_id,
            "--format",
            "srt",
            "--output",
            str(output),
        ],
    )
    main()
    assert "00:00:00,500 --> 00:00:01,750" in output.read_text(encoding="utf-8")


def test_cli_safe_error(monkeypatch, capsys):
    def fail(*args):
        raise TranscriptError("Captions unavailable")

    monkeypatch.setattr("youtube_transcript_mcp.cli.TranscriptService.get_transcript", fail)
    monkeypatch.setattr(sys, "argv", ["youtube-transcript-mcp", "fetch", "dQw4w9WgXcQ"])
    with pytest.raises(SystemExit) as caught:
        main()
    captured = capsys.readouterr()
    assert caught.value.code == 1
    assert captured.out == ""
    assert "Error: Captions unavailable" in captured.err


def test_cli_whisper_language_forwarded(monkeypatch, capsys, transcript):
    from unittest.mock import Mock

    fetch = Mock(return_value=transcript)
    monkeypatch.setattr("youtube_transcript_mcp.cli.TranscriptService.get_transcript", fetch)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "youtube-transcript-mcp",
            "fetch",
            transcript.video_id,
            "--languages",
            "en",
            "--whisper-language",
            "hi",
            "--source",
            "whisper",
            "--format",
            "txt",
        ],
    )
    main()
    fetch.assert_called_once_with(transcript.video_id, ["en"], "whisper", "hi")
    assert capsys.readouterr().out.strip() == transcript.text


def test_cli_debug_does_not_swallow_oserror(monkeypatch):
    monkeypatch.setenv("YTMCP_DEBUG", "true")

    def fail(*args):
        raise OSError("decode failure")

    monkeypatch.setattr("youtube_transcript_mcp.cli.TranscriptService.get_transcript", fail)
    monkeypatch.setattr(sys, "argv", ["youtube-transcript-mcp", "fetch", "dQw4w9WgXcQ"])
    with pytest.raises(OSError, match="decode failure"):
        main()
