import pytest

from youtube_transcript_mcp.models import Segment, TranscriptResult


@pytest.fixture
def transcript():
    return TranscriptResult(
        video_id="dQw4w9WgXcQ",
        url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        source="captions",
        language="English",
        language_code="en",
        is_generated=False,
        segments=[Segment(text="Hello world", start=0.5, duration=1.25)],
        text="Hello world",
    )
