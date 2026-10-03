import math
import re
from typing import Literal
from urllib.parse import parse_qs, urlsplit

from pydantic import BaseModel, Field


class TranscriptError(Exception):
    """A safe, user-facing error that never includes upstream credentials."""


class Segment(BaseModel):
    text: str
    start: float = Field(ge=0)
    duration: float = Field(ge=0)


class TranscriptResult(BaseModel):
    video_id: str
    url: str
    source: Literal["captions", "whisper"]
    language: str
    language_code: str
    is_generated: bool
    segments: list[Segment]
    text: str
    warnings: list[str] = Field(default_factory=list)


class CaptionTrack(BaseModel):
    language: str
    language_code: str
    is_generated: bool
    is_translatable: bool


def video_id_from_input(value: str) -> str:
    value = value.strip()
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", value):
        return value
    try:
        parsed = urlsplit(value)
        if (
            parsed.scheme not in {"http", "https"}
            or parsed.username is not None
            or parsed.password is not None
            or parsed.port is not None
        ):
            raise ValueError
        host = (parsed.hostname or "").lower()
        parts = parsed.path.strip("/").split("/")
        candidate = ""
        if host in {"youtu.be", "www.youtu.be"} and len(parts) == 1:
            candidate = parts[0]
        elif host in {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com"}:
            if parsed.path == "/watch":
                candidate = parse_qs(parsed.query).get("v", [""])[0]
            elif len(parts) == 2 and parts[0] in {"shorts", "embed", "live"}:
                candidate = parts[1]
        elif host in {"youtube-nocookie.com", "www.youtube-nocookie.com"}:
            if len(parts) == 2 and parts[0] == "embed":
                candidate = parts[1]
        if re.fullmatch(r"[A-Za-z0-9_-]{11}", candidate):
            return candidate
    except ValueError:
        pass
    raise TranscriptError("Provide an 11-character video ID or a valid YouTube video URL.")


def normalize_languages(languages: list[str] | None) -> list[str]:
    if languages is None:
        return ["en", "hi"]
    if not languages or len(languages) > 10:
        raise TranscriptError("Provide between 1 and 10 caption language codes.")
    normalized = [language.strip() for language in languages]
    if any(not re.fullmatch(r"[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*", code) for code in normalized):
        raise TranscriptError("Invalid caption language code; use codes such as en, hi, or en-US.")
    return list(dict.fromkeys(normalized))


def timestamp(seconds: float, separator: str = ",") -> str:
    if not math.isfinite(seconds) or seconds < 0:
        raise TranscriptError("Invalid transcript timestamp.")
    total_ms = round(seconds * 1000)
    hours, remainder = divmod(total_ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    whole_seconds, milliseconds = divmod(remainder, 1000)
    return f"{hours:02}:{minutes:02}:{whole_seconds:02}{separator}{milliseconds:03}"


def render_subtitles(result: TranscriptResult, output_format: Literal["srt", "vtt"]) -> str:
    separator = "." if output_format == "vtt" else ","
    blocks = []
    for index, segment in enumerate(result.segments, start=1):
        start = timestamp(segment.start, separator)
        end = timestamp(segment.start + segment.duration, separator)
        blocks.append(f"{index}\n{start} --> {end}\n{segment.text}")
    prefix = "WEBVTT\n\n" if output_format == "vtt" else ""
    return prefix + "\n\n".join(blocks) + "\n"
