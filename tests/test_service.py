import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import requests
from youtube_transcript_api._errors import TranscriptsDisabled

from youtube_transcript_mcp.config import Settings
from youtube_transcript_mcp.models import TranscriptError
from youtube_transcript_mcp.service import TimeoutSession, TranscriptService


def test_caption_success_skips_audio(monkeypatch, transcript):
    service = TranscriptService(Settings())
    captions = Mock(return_value=transcript)
    whisper = Mock(side_effect=AssertionError("audio must not be used"))
    monkeypatch.setattr(service, "_captions", captions)
    monkeypatch.setattr(service, "_whisper", whisper)
    assert service.get_transcript(transcript.url, ["hi", "en"]) is transcript
    captions.assert_called_once_with(transcript.video_id, ["hi", "en"])
    whisper.assert_not_called()


@pytest.mark.parametrize(
    "error",
    [requests.ConnectionError("secret-proxy-password"), TranscriptsDisabled("dQw4w9WgXcQ")],
)
def test_fallback(monkeypatch, transcript, error):
    service = TranscriptService(Settings())
    transcript.source = "whisper"
    monkeypatch.setattr(service, "_captions", Mock(side_effect=error))
    monkeypatch.setattr(service, "_whisper", Mock(return_value=transcript))
    result = service.get_transcript(transcript.video_id)
    assert result.source == "whisper"
    assert result.warnings
    assert "secret-proxy-password" not in result.model_dump_json()


def test_captions_only_error_no_download(monkeypatch):
    service = TranscriptService(Settings())
    monkeypatch.setattr(service, "_captions", Mock(side_effect=requests.Timeout("secret")))
    whisper = Mock()
    monkeypatch.setattr(service, "_whisper", whisper)
    with pytest.raises(TranscriptError, match="Captions unavailable"):
        service.get_transcript("dQw4w9WgXcQ", source="captions")
    whisper.assert_not_called()


def test_explicit_whisper_skips_captions(monkeypatch, transcript):
    service = TranscriptService(Settings())
    captions = Mock()
    monkeypatch.setattr(service, "_captions", captions)
    monkeypatch.setattr(service, "_whisper", Mock(return_value=transcript))
    service.get_transcript(transcript.video_id, source="whisper")
    captions.assert_not_called()


def test_invalid_request_does_no_network(monkeypatch):
    service = TranscriptService(Settings())
    captions = Mock()
    monkeypatch.setattr(service, "_captions", captions)
    with pytest.raises(TranscriptError):
        service.get_transcript("https://localhost/private")
    with pytest.raises(TranscriptError):
        service.get_transcript("dQw4w9WgXcQ", languages=[])
    with pytest.raises(TranscriptError):
        service.get_transcript("dQw4w9WgXcQ", source="bad")
    captions.assert_not_called()


def test_fetched_caption_mapping(monkeypatch):
    service = TranscriptService(Settings())

    class Fetched(list):
        language = "Hindi"
        language_code = "hi"
        is_generated = True

    fetched = Fetched(
        [
            SimpleNamespace(text=" नमस्ते ", start=0, duration=1),
            SimpleNamespace(text=" ", start=1, duration=1),
        ]
    )
    api = Mock()
    api.fetch.return_value = fetched
    monkeypatch.setattr(service, "_caption_api", lambda session: api)
    result = service.get_transcript("dQw4w9WgXcQ", ["hi"])
    assert result.text == "नमस्ते"
    assert result.language_code == "hi"
    assert len(result.segments) == 1
    assert result.is_generated


def test_empty_captions_trigger_fallback(monkeypatch, transcript):
    service = TranscriptService(Settings())
    api = Mock()
    api.fetch.return_value = []
    monkeypatch.setattr(service, "_caption_api", lambda session: api)
    monkeypatch.setattr(service, "_whisper", Mock(return_value=transcript))
    assert service.get_transcript("dQw4w9WgXcQ").warnings


def test_list_tracks(monkeypatch):
    service = TranscriptService(Settings())
    api = Mock()
    api.list.return_value = [
        SimpleNamespace(
            language="English", language_code="en", is_generated=False, is_translatable=True
        )
    ]
    monkeypatch.setattr(service, "_caption_api", lambda session: api)
    tracks = service.list_captions("dQw4w9WgXcQ")
    assert tracks[0].language_code == "en"
    assert tracks[0].is_translatable


def test_list_error_sanitized(monkeypatch):
    service = TranscriptService(Settings())
    api = Mock()
    api.list.side_effect = requests.ConnectionError("credential-secret")
    monkeypatch.setattr(service, "_caption_api", lambda session: api)
    with pytest.raises(TranscriptError) as caught:
        service.list_captions("dQw4w9WgXcQ")
    assert "credential-secret" not in str(caught.value)


def test_disabled_and_missing_whisper(monkeypatch):
    service = TranscriptService(Settings(whisper_enabled=False))
    with pytest.raises(TranscriptError, match="disabled"):
        service.get_transcript("dQw4w9WgXcQ", source="whisper")
    monkeypatch.setitem(sys.modules, "faster_whisper", None)
    with pytest.raises(TranscriptError, match="Install Whisper"):
        TranscriptService(Settings()).get_transcript("dQw4w9WgXcQ", source="whisper")


def test_whisper_model_reused_and_temporary_files_cleaned(monkeypatch):
    service = TranscriptService(Settings())
    folders = []

    def download(video_id, directory):
        folders.append(directory)
        audio = directory / "audio.m4a"
        audio.write_bytes(b"test")
        return audio

    model = Mock()
    model.transcribe.side_effect = lambda *args, **kwargs: (
        iter([SimpleNamespace(text=" Hello ", start=1.0, end=2.5)]),
        SimpleNamespace(language="en", language_probability=0.9),
    )
    constructor = Mock(return_value=model)
    monkeypatch.setitem(sys.modules, "faster_whisper", SimpleNamespace(WhisperModel=constructor))
    monkeypatch.setattr(service, "_download_audio", download)
    for _ in range(2):
        result = service.get_transcript("dQw4w9WgXcQ", source="whisper")
        assert result.source == "whisper"
        assert result.segments[0].duration == 1.5
        assert result.text == "Hello"
    constructor.assert_called_once_with("small", device="cpu", compute_type="int8")
    assert model.transcribe.call_args.kwargs == {
        "vad_filter": True,
        "condition_on_previous_text": False,
    }
    assert all(not folder.exists() for folder in folders)


@pytest.mark.parametrize("failure", [True, False])
def test_whisper_failure_cleans_audio(monkeypatch, failure):
    service = TranscriptService(Settings(proxy="http://user:credential-secret@proxy.test"))
    folders = []

    def download(video_id, directory):
        folders.append(directory)
        audio = directory / "audio.webm"
        audio.write_bytes(b"test")
        return audio

    model = Mock()
    if failure:
        model.transcribe.side_effect = RuntimeError("credential-secret")
    else:
        model.transcribe.return_value = (iter([]), SimpleNamespace(language="en"))
    monkeypatch.setitem(
        sys.modules, "faster_whisper", SimpleNamespace(WhisperModel=Mock(return_value=model))
    )
    monkeypatch.setattr(service, "_download_audio", download)
    with pytest.raises(TranscriptError) as caught:
        service.get_transcript("dQw4w9WgXcQ", source="whisper")
    assert "credential-secret" not in str(caught.value)
    assert all(not folder.exists() for folder in folders)


def fake_downloader(monkeypatch, tmp_path, metadata, downloaded=b"audio", error=None):
    options_seen = {}

    class Downloader:
        def __init__(self, options):
            options_seen.update(options)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def extract_info(self, url, download):
            assert url == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
            assert download is False
            if error:
                raise error
            return metadata

        def process_info(self, info):
            (tmp_path / "audio.m4a").write_bytes(downloaded)

        def prepare_filename(self, info):
            return str(tmp_path / "audio.m4a")

    monkeypatch.setattr("youtube_transcript_mcp.service.YoutubeDL", Downloader)
    return options_seen


def test_audio_download_options(monkeypatch, tmp_path):
    service = TranscriptService(Settings(proxy="http://proxy", cookies_file="cookies.txt"))
    options = fake_downloader(monkeypatch, tmp_path, {"duration": 10})
    assert service._download_audio("dQw4w9WgXcQ", tmp_path) == tmp_path / "audio.m4a"
    assert options["noplaylist"] is True
    assert options["proxy"] == "http://proxy"
    assert options["cookiefile"] == "cookies.txt"
    with pytest.raises(TranscriptError, match="exceeded"):
        options["progress_hooks"][0]({"downloaded_bytes": 101 * 1024 * 1024})


@pytest.mark.parametrize(
    "metadata",
    [
        None,
        {"duration": None},
        {"duration": 3601},
        {"duration": 0},
        {"duration": float("nan")},
        {"duration": 10, "is_live": True},
        {"duration": 10, "live_status": "is_upcoming"},
    ],
)
def test_download_rejects_unbounded_videos(monkeypatch, tmp_path, metadata):
    fake_downloader(monkeypatch, tmp_path, metadata)
    with pytest.raises(TranscriptError):
        TranscriptService(Settings())._download_audio("dQw4w9WgXcQ", tmp_path)
    assert not (tmp_path / "audio.m4a").exists()


def test_download_byte_limit(monkeypatch, tmp_path):
    fake_downloader(monkeypatch, tmp_path, {"duration": 10}, b"x" * (1024 * 1024 + 1))
    with pytest.raises(TranscriptError, match="exceeded"):
        TranscriptService(Settings(max_download_mb=1))._download_audio("dQw4w9WgXcQ", tmp_path)


def test_download_error_sanitized(monkeypatch, tmp_path):
    fake_downloader(monkeypatch, tmp_path, {}, error=RuntimeError("credential-secret"))
    with pytest.raises(TranscriptError) as caught:
        TranscriptService(
            Settings(proxy="http://user:credential-secret@proxy.test")
        )._download_audio("dQw4w9WgXcQ", tmp_path)
    assert "credential-secret" not in str(caught.value)
    assert "RuntimeError" in str(caught.value)
    assert isinstance(caught.value.__cause__, RuntimeError)
    assert "credential-secret" not in str(caught.value.__cause__)


@pytest.mark.parametrize(
    "hint,configured,expected",
    [("hi", "en", "hi"), (None, "hi", "hi"), ("", "hi", None), (None, None, None)],
)
@pytest.mark.parametrize("confidence,warning", [(0.2, True), (0.35, False), (0.98, False)])
def test_whisper_language_and_confidence(
    monkeypatch, tmp_path, hint, configured, expected, confidence, warning
):
    service = TranscriptService(Settings(whisper_language=configured))
    model = Mock()
    model.transcribe.return_value = (
        iter([SimpleNamespace(text="नमस्ते", start=0, end=1)]),
        SimpleNamespace(language="hi", language_probability=confidence),
    )
    monkeypatch.setitem(
        sys.modules, "faster_whisper", SimpleNamespace(WhisperModel=Mock(return_value=model))
    )
    monkeypatch.setattr(service, "_download_audio", lambda *args: tmp_path / "audio.m4a")
    result = service.get_transcript("dQw4w9WgXcQ", source="whisper", whisper_language=hint)
    assert result.text == "नमस्ते"
    assert model.transcribe.call_args.kwargs["condition_on_previous_text"] is False
    if expected is None:
        assert "language" not in model.transcribe.call_args.kwargs
    else:
        assert model.transcribe.call_args.kwargs["language"] == expected
    assert bool(result.warnings) is warning
    assert service.settings.whisper_language == configured


@pytest.mark.parametrize("debug", [False, True])
def test_whisper_exception_type_message_and_traceback(monkeypatch, tmp_path, debug):
    import traceback

    service = TranscriptService(Settings(debug=debug))
    failure = TypeError("open() got an unexpected keyword argument 'metadata_errors'")
    model = Mock()
    model.transcribe.side_effect = failure
    monkeypatch.setitem(
        sys.modules, "faster_whisper", SimpleNamespace(WhisperModel=Mock(return_value=model))
    )
    monkeypatch.setattr(service, "_download_audio", lambda *args: tmp_path / "audio.m4a")
    with pytest.raises(TypeError if debug else TranscriptError) as caught:
        service.get_transcript("dQw4w9WgXcQ", source="whisper")
    assert "metadata_errors" in str(caught.value)
    if debug:
        assert caught.value is failure
        assert "transcribe" in "".join(traceback.format_exception(caught.value))
    else:
        assert "TypeError" in str(caught.value)
        assert caught.value.__cause__ is failure


def test_debug_download_preserves_raw_error_without_credentials(monkeypatch, tmp_path):
    import traceback

    proxy = "http://proxy-user:proxy-password@proxy.test:8080"
    settings = Settings(debug=True, proxy=proxy, cookies_file="private-cookies.txt")
    failure = RuntimeError(f"Download failed via {proxy}; private-cookies.txt")
    failure.__cause__ = ValueError("proxy-password")
    failure.add_note("private-cookies.txt")
    fake_downloader(monkeypatch, tmp_path, {}, error=failure)
    with pytest.raises(RuntimeError) as caught:
        TranscriptService(settings)._download_audio("dQw4w9WgXcQ", tmp_path)
    diagnostic = "".join(traceback.format_exception(caught.value))
    assert caught.value is failure
    assert "Download failed" in diagnostic
    for secret in (proxy, "proxy-user", "proxy-password", "private-cookies.txt"):
        assert secret not in diagnostic


@pytest.mark.parametrize("av_version,active", [("18.1.0", True), ("19.0.1", False), (None, False)])
def test_status_reports_av_constraint(monkeypatch, av_version, active):
    from importlib.metadata import PackageNotFoundError

    def installed_version(name):
        if av_version is None:
            raise PackageNotFoundError(name)
        return av_version

    monkeypatch.setattr("youtube_transcript_mcp.service.version", installed_version)
    status = TranscriptService(Settings()).status()
    assert status["whisper_model"] == "small"
    assert status["whisper_language"] is None
    assert status["av_constraint"] == "av>=11,<19"
    assert status["av_constraint_active"] is active


def test_status_no_credentials():
    service = TranscriptService(Settings(proxy="secret-proxy", cookies_file="secret-cookie"))
    status = service.status()
    assert status["proxy_configured"]
    assert status["cookies_configured"]
    assert "secret" not in str(status)


def test_caption_timeout(monkeypatch):
    request = Mock(return_value="response")
    monkeypatch.setattr(requests.Session, "request", request)
    with TimeoutSession(7) as session:
        assert session.get("https://example.test") == "response"
    assert request.call_args.kwargs["timeout"] == 7


def test_download_path_confined(monkeypatch, tmp_path):
    fake_downloader(monkeypatch, tmp_path, {"duration": 10})
    directory = tmp_path / "allowed"
    directory.mkdir()
    with pytest.raises(TranscriptError, match="No usable audio"):
        TranscriptService(Settings())._download_audio("dQw4w9WgXcQ", directory)
    assert Path(tmp_path / "audio.m4a").is_file()
