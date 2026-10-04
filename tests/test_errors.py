import traceback

import pytest

from youtube_transcript_mcp.config import Settings
from youtube_transcript_mcp.errors import redact_exception, redact_message


@pytest.mark.parametrize(
    "message",
    [
        "proxy-user proxy-password private-cookies.txt",
        "https://different-user:different-password@other.proxy/path?token=secret",
        "Cookie: SID=private-cookie; session=private-session",
        "Authorization: Bearer private-token",
        "password='private-password' token=private-token",
    ],
)
def test_redact_diagnostic_credentials(message):
    result = redact_message(
        message,
        Settings(
            proxy="http://proxy-user:proxy-password@proxy.test", cookies_file="private-cookies.txt"
        ),
    )
    assert "private-" not in result
    assert "proxy-user" not in result
    assert "proxy-password" not in result
    assert "different-password" not in result
    assert "secret" not in result


def test_encoded_proxy_password():
    settings = Settings(proxy="http://user:p%40ssword@proxy.test")
    assert "p@ssword" not in redact_message("failed: p@ssword", settings)
    assert "p%40ssword" not in redact_message("failed: p%40ssword", settings)


def test_redact_oserror_filename_and_cause():
    settings = Settings(cookies_file="private-cookies.txt")
    error = OSError(13, "cannot read private-cookies.txt", "private-cookies.txt")
    error.__cause__ = RuntimeError("private-cookies.txt")
    error.add_note("private-cookies.txt")
    redact_exception(error, settings)
    diagnostic = "".join(traceback.format_exception(error))
    assert "private-cookies.txt" not in diagnostic
    assert "PermissionError" in diagnostic
