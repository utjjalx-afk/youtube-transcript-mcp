import sys
from datetime import timedelta

import anyio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from youtube_transcript_mcp.server import create_server
from youtube_transcript_mcp.service import TranscriptService


def test_tool_schema_and_mocked_call(monkeypatch, transcript):
    service = TranscriptService()
    from unittest.mock import Mock

    fetch_transcript = Mock(return_value=transcript)
    monkeypatch.setattr(service, "get_transcript", fetch_transcript)
    server = create_server(service)

    async def run():
        tools = await server.list_tools()
        assert {tool.name for tool in tools} == {"get_transcript", "list_captions", "get_status"}
        fetch = next(tool for tool in tools if tool.name == "get_transcript")
        assert fetch.inputSchema["required"] == ["video"]
        assert fetch.annotations.readOnlyHint
        assert fetch.outputSchema
        assert "whisper_language" in fetch.inputSchema["properties"]
        result = await server.call_tool(
            "get_transcript", {"video": transcript.video_id, "whisper_language": "hi"}
        )
        assert result[1]["text"] == "Hello world"
        fetch_transcript.assert_called_once_with(transcript.video_id, None, "auto", "hi")

    anyio.run(run)


def test_real_stdio_handshake_and_validation():
    async def run():
        parameters = StdioServerParameters(
            command=sys.executable,
            args=["-m", "youtube_transcript_mcp", "serve"],
            env={"YTMCP_WHISPER_ENABLED": "false", "PYTHONUTF8": "1"},
        )
        with anyio.fail_after(30):
            async with stdio_client(parameters) as (reader, writer):
                async with ClientSession(
                    reader, writer, read_timeout_seconds=timedelta(seconds=15)
                ) as session:
                    initialized = await session.initialize()
                    assert initialized.serverInfo.name == "youtube-transcript-mcp"
                    listed = await session.list_tools()
                    assert len(listed.tools) == 3
                    status = await session.call_tool("get_status", {})
                    assert not status.isError
                    assert status.structuredContent["whisper_enabled"] is False
                    invalid = await session.call_tool("get_transcript", {"video": "invalid"})
                    assert invalid.isError
                    assert "valid YouTube" in invalid.content[0].text

    anyio.run(run)
