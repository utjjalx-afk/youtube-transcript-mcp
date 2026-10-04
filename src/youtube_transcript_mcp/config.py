import os
import re
from dataclasses import dataclass, field

from youtube_transcript_mcp.models import TranscriptError


def positive_integer(name: str, default: int) -> int:
    try:
        value = int(os.environ.get(name, str(default)))
        if value <= 0:
            raise ValueError
        return value
    except ValueError:
        raise TranscriptError(f"{name} must be a positive integer.") from None


def boolean(name: str, default: bool) -> bool:
    value = os.environ.get(name, str(default)).lower()
    if value in {"true", "1", "yes"}:
        return True
    if value in {"false", "0", "no"}:
        return False
    raise TranscriptError(f"{name} must be true or false.")


def normalize_whisper_language(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    language = value.strip().lower()
    if not re.fullmatch(r"[a-z]{2,3}", language):
        raise TranscriptError(
            "Whisper language must be a code such as hi or en, or empty for auto."
        )
    return language


@dataclass(frozen=True)
class Settings:
    whisper_enabled: bool = True
    whisper_model: str = "small"
    whisper_language: str | None = None
    whisper_device: str = "cpu"
    whisper_compute_type: str = "int8"
    debug: bool = False
    max_duration_seconds: int = 3600
    max_download_mb: int = 100
    request_timeout_seconds: int = 30
    proxy: str | None = field(default=None, repr=False)
    cookies_file: str | None = field(default=None, repr=False)

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            whisper_enabled=boolean("YTMCP_WHISPER_ENABLED", True),
            whisper_model=os.environ.get("YTMCP_WHISPER_MODEL", "small"),
            whisper_language=normalize_whisper_language(os.environ.get("YTMCP_WHISPER_LANGUAGE")),
            whisper_device=os.environ.get("YTMCP_WHISPER_DEVICE", "cpu"),
            whisper_compute_type=os.environ.get("YTMCP_WHISPER_COMPUTE_TYPE", "int8"),
            debug=boolean("YTMCP_DEBUG", False),
            max_duration_seconds=positive_integer("YTMCP_MAX_DURATION_SECONDS", 3600),
            max_download_mb=positive_integer("YTMCP_MAX_DOWNLOAD_MB", 100),
            request_timeout_seconds=positive_integer("YTMCP_REQUEST_TIMEOUT_SECONDS", 30),
            proxy=os.environ.get("YTMCP_PROXY") or None,
            cookies_file=os.environ.get("YTMCP_COOKIES_FILE") or None,
        )
