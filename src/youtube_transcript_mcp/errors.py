import re
from urllib.parse import unquote, urlsplit

from youtube_transcript_mcp.config import Settings


def redact_message(message: str, settings: Settings) -> str:
    sensitive_values = [settings.proxy, settings.cookies_file]
    if settings.proxy:
        try:
            proxy = urlsplit(settings.proxy)
            sensitive_values.extend([proxy.username, proxy.password])
        except ValueError:
            pass
    values = {
        variant
        for value in sensitive_values
        if value
        for variant in (value, unquote(value))
        if variant
    }
    for value in sorted(values, key=len, reverse=True):
        message = message.replace(value, "[redacted]")
    message = re.sub(r"(?i)\b(?:https?|socks5h?)://[^\s<>\"']+", "[redacted-url]", message)
    message = re.sub(
        r"(?im)\b(?:cookie|set-cookie|authorization)\s*:\s*[^\r\n]+",
        "[redacted-header]",
        message,
    )
    return re.sub(
        r"(?i)\b(?:password|passwd|token|api_key|proxy_password)\s*[=:]\s*"
        r"(?:\"[^\"]*\"|'[^']*'|[^\s,;]+)",
        "[redacted-credential]",
        message,
    )


def redact_exception(error: BaseException, settings: Settings) -> None:
    """Preserve exception types/tracebacks while removing sensitive diagnostic values."""
    pending = [error]
    seen = set()
    while pending:
        current = pending.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        current.args = tuple(
            redact_message(argument, settings) if isinstance(argument, str) else argument
            for argument in current.args
        )
        for argument in current.args:
            if isinstance(argument, BaseException):
                pending.append(argument)
        for name, value in vars(current).items():
            if isinstance(value, str):
                setattr(current, name, redact_message(value, settings))
            elif isinstance(value, BaseException):
                pending.append(value)
        if hasattr(current, "__notes__"):
            current.__notes__ = [redact_message(note, settings) for note in current.__notes__]
        for name in ("filename", "filename2", "strerror"):
            value = getattr(current, name, None)
            if isinstance(value, str):
                setattr(current, name, redact_message(value, settings))
        if current.__cause__ is not None:
            pending.append(current.__cause__)
        if current.__context__ is not None:
            pending.append(current.__context__)
