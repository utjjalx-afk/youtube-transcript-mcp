import importlib.util
import math
import threading
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Literal

import requests
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import YouTubeTranscriptApiException
from youtube_transcript_api.proxies import GenericProxyConfig
from yt_dlp import YoutubeDL

from youtube_transcript_mcp.config import Settings
from youtube_transcript_mcp.models import (
    CaptionTrack,
    Segment,
    TranscriptError,
    TranscriptResult,
    normalize_languages,
    video_id_from_input,
)


class TimeoutSession(requests.Session):
    def __init__(self, timeout: int):
        super().__init__()
        self.timeout = timeout

    def request(self, method, url, **kwargs):
        kwargs.setdefault("timeout", self.timeout)
        return super().request(method, url, **kwargs)


class QuietLogger:
    def debug(self, message):
        pass

    def warning(self, message):
        pass

    def error(self, message):
        pass


class TranscriptService:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or Settings.from_env()
        self._model = None
        self._whisper_lock = threading.Lock()

    def _caption_api(self, session: requests.Session) -> YouTubeTranscriptApi:
        options = {"http_client": session}
        if self.settings.proxy:
            options["proxy_config"] = GenericProxyConfig(
                http_url=self.settings.proxy, https_url=self.settings.proxy
            )
        return YouTubeTranscriptApi(**options)

    def list_captions(self, video: str) -> list[CaptionTrack]:
        video_id = video_id_from_input(video)
        try:
            with TimeoutSession(self.settings.request_timeout_seconds) as session:
                tracks = self._caption_api(session).list(video_id)
                return [
                    CaptionTrack(
                        language=track.language,
                        language_code=track.language_code,
                        is_generated=track.is_generated,
                        is_translatable=track.is_translatable,
                    )
                    for track in tracks
                ]
        except (YouTubeTranscriptApiException, requests.RequestException):
            raise TranscriptError(
                "Could not list captions. The video may be unavailable, have no captions, "
                "or YouTube may be blocking this IP."
            ) from None

    def _captions(self, video_id: str, languages: list[str]) -> TranscriptResult:
        with TimeoutSession(self.settings.request_timeout_seconds) as session:
            fetched = self._caption_api(session).fetch(video_id, languages=languages)
            segments = [
                Segment(text=snippet.text.strip(), start=snippet.start, duration=snippet.duration)
                for snippet in fetched
                if snippet.text.strip()
            ]
            if not segments:
                raise TranscriptError("The selected caption track is empty.")
            return TranscriptResult(
                video_id=video_id,
                url=f"https://www.youtube.com/watch?v={video_id}",
                source="captions",
                language=fetched.language,
                language_code=fetched.language_code,
                is_generated=fetched.is_generated,
                segments=segments,
                text="\n".join(segment.text for segment in segments),
            )

    def get_transcript(
        self,
        video: str,
        languages: list[str] | None = None,
        source: Literal["auto", "captions", "whisper"] = "auto",
    ) -> TranscriptResult:
        video_id = video_id_from_input(video)
        preferred_languages = normalize_languages(languages)
        if source not in {"auto", "captions", "whisper"}:
            raise TranscriptError("source must be auto, captions, or whisper.")
        warnings = []
        if source != "whisper":
            try:
                return self._captions(video_id, preferred_languages)
            except (YouTubeTranscriptApiException, requests.RequestException, TranscriptError):
                if source == "captions":
                    raise TranscriptError(
                        "Captions unavailable for the requested languages, or YouTube blocked "
                        "the request. Try list_captions or source='auto'."
                    ) from None
                warnings.append("Preferred captions unavailable; used audio transcription instead.")
        result = self._whisper(video_id)
        result.warnings.extend(warnings)
        return result

    def _download_audio(self, video_id: str, directory: Path) -> Path:
        max_bytes = self.settings.max_download_mb * 1024 * 1024

        def check_progress(status):
            if status.get("downloaded_bytes", 0) > max_bytes:
                raise TranscriptError("Audio download exceeded YTMCP_MAX_DOWNLOAD_MB.")

        options = {
            "format": "bestaudio/best",
            "outtmpl": str(directory / "audio.%(ext)s"),
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "logger": QuietLogger(),
            "socket_timeout": self.settings.request_timeout_seconds,
            "retries": 2,
            "fragment_retries": 2,
            "max_filesize": max_bytes,
            "progress_hooks": [check_progress],
        }
        if self.settings.proxy:
            options["proxy"] = self.settings.proxy
        if self.settings.cookies_file:
            options["cookiefile"] = self.settings.cookies_file
        try:
            with YoutubeDL(options) as downloader:
                info = downloader.extract_info(
                    f"https://www.youtube.com/watch?v={video_id}", download=False
                )
                if not info or info.get("is_live") or info.get("live_status") == "is_upcoming":
                    raise TranscriptError("Live/upcoming or unavailable videos are not supported.")
                duration = info.get("duration")
                if (
                    not isinstance(duration, (int, float))
                    or not math.isfinite(duration)
                    or duration <= 0
                    or duration > self.settings.max_duration_seconds
                ):
                    raise TranscriptError(
                        "Video duration is unknown or exceeds YTMCP_MAX_DURATION_SECONDS."
                    )
                downloader.process_info(info)
                audio = Path(downloader.prepare_filename(info)).resolve()
                if not audio.is_relative_to(directory.resolve()) or not audio.is_file():
                    raise TranscriptError(
                        "No usable audio downloaded; check size limits and access."
                    )
                if audio.stat().st_size > max_bytes:
                    raise TranscriptError("Audio download exceeded YTMCP_MAX_DOWNLOAD_MB.")
                return audio
        except TranscriptError:
            raise
        except Exception:
            raise TranscriptError(
                "Audio download failed. Check video access, network/IP blocking, "
                "and yt-dlp updates. "
                "Whisper cannot bypass YouTube access restrictions."
            ) from None

    def _whisper(self, video_id: str) -> TranscriptResult:
        if not self.settings.whisper_enabled:
            raise TranscriptError("Whisper fallback is disabled by YTMCP_WHISPER_ENABLED.")
        try:
            from faster_whisper import WhisperModel
        except ImportError:
            raise TranscriptError(
                'Install Whisper support with: python -m pip install -e ".[whisper]"'
            ) from None
        with self._whisper_lock, TemporaryDirectory(prefix="ytmcp-") as temporary:
            audio = self._download_audio(video_id, Path(temporary))
            try:
                if self._model is None:
                    self._model = WhisperModel(
                        self.settings.whisper_model,
                        device=self.settings.whisper_device,
                        compute_type=self.settings.whisper_compute_type,
                    )
                raw_segments, info = self._model.transcribe(str(audio), vad_filter=True)
                segments = [
                    Segment(
                        text=segment.text.strip(),
                        start=segment.start,
                        duration=max(0, segment.end - segment.start),
                    )
                    for segment in raw_segments
                    if segment.text.strip()
                ]
                if not segments:
                    raise TranscriptError("Whisper detected no speech in the video.")
                return TranscriptResult(
                    video_id=video_id,
                    url=f"https://www.youtube.com/watch?v={video_id}",
                    source="whisper",
                    language=info.language,
                    language_code=info.language,
                    is_generated=True,
                    segments=segments,
                    text="\n".join(segment.text for segment in segments),
                )
            except TranscriptError:
                raise
            except Exception:
                raise TranscriptError(
                    "Whisper transcription failed. Check model download access, available memory, "
                    "and device/compute settings. CPU with int8 is the default."
                ) from None

    def status(self) -> dict[str, str | bool | int]:
        return {
            "transport": "stdio",
            "whisper_enabled": self.settings.whisper_enabled,
            "whisper_installed": importlib.util.find_spec("faster_whisper") is not None,
            "whisper_model": self.settings.whisper_model,
            "whisper_device": self.settings.whisper_device,
            "whisper_compute_type": self.settings.whisper_compute_type,
            "max_duration_seconds": self.settings.max_duration_seconds,
            "max_download_mb": self.settings.max_download_mb,
            "proxy_configured": bool(self.settings.proxy),
            "cookies_configured": bool(self.settings.cookies_file),
        }
