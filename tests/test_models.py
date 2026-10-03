import pytest

from youtube_transcript_mcp.models import (
    TranscriptError,
    normalize_languages,
    render_subtitles,
    timestamp,
    video_id_from_input,
)


@pytest.mark.parametrize(
    "value",
    [
        "dQw4w9WgXcQ",
        " https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=ignored ",
        "https://youtu.be/dQw4w9WgXcQ?t=10",
        "https://m.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://music.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://youtube.com/shorts/dQw4w9WgXcQ",
        "https://youtube.com/live/dQw4w9WgXcQ",
        "https://www.youtube.com/embed/dQw4w9WgXcQ",
        "https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ",
    ],
)
def test_video_inputs(value):
    assert video_id_from_input(value) == "dQw4w9WgXcQ"


@pytest.mark.parametrize(
    "value",
    [
        "",
        "short-id",
        "https://example.com/watch?v=dQw4w9WgXcQ",
        "https://youtube.com.evil.test/watch?v=dQw4w9WgXcQ",
        "https://youtube.com@evil.test/watch?v=dQw4w9WgXcQ",
        "https://user:secret@youtube.com/watch?v=dQw4w9WgXcQ",
        "file:///dQw4w9WgXcQ",
        "https://youtube.com/playlist?list=dQw4w9WgXcQ",
        "https://youtube.com:8080/watch?v=dQw4w9WgXcQ",
        "https://youtube.com:bad/watch?v=dQw4w9WgXcQ",
        "https://youtu.be/dQw4w9WgXcQ/extra",
    ],
)
def test_reject_invalid_inputs(value):
    with pytest.raises(TranscriptError):
        video_id_from_input(value)


def test_languages():
    assert normalize_languages(None) == ["en", "hi"]
    assert normalize_languages([" hi ", "en", "hi"]) == ["hi", "en"]


@pytest.mark.parametrize("languages", [[], ["en"] * 11, ["../etc"], [""], ["English"]])
def test_invalid_languages(languages):
    with pytest.raises(TranscriptError):
        normalize_languages(languages)


def test_formats(transcript):
    assert render_subtitles(transcript, "srt") == (
        "1\n00:00:00,500 --> 00:00:01,750\nHello world\n"
    )
    assert render_subtitles(transcript, "vtt") == (
        "WEBVTT\n\n1\n00:00:00.500 --> 00:00:01.750\nHello world\n"
    )
    assert timestamp(3599.9999) == "01:00:00,000"


@pytest.mark.parametrize("value", [-1, float("nan"), float("inf")])
def test_invalid_timestamp(value):
    with pytest.raises(TranscriptError):
        timestamp(value)
