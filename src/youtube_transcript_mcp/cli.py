import argparse
import json
import sys
from pathlib import Path

from youtube_transcript_mcp import __version__
from youtube_transcript_mcp.models import TranscriptError, render_subtitles
from youtube_transcript_mcp.service import TranscriptService


def main() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Caption-first YouTube transcript MCP server")
    parser.add_argument("--version", action="version", version=__version__)
    subcommands = parser.add_subparsers(dest="command")
    subcommands.add_parser("serve", help="Run the MCP server over stdio (also the default)")
    subcommands.add_parser("doctor", help="Print local capability/limit information")
    captions = subcommands.add_parser("list", help="List available caption tracks")
    captions.add_argument("video")
    fetch = subcommands.add_parser("fetch", help="Fetch a transcript without an MCP client")
    fetch.add_argument("video")
    fetch.add_argument("--languages", nargs="+", default=None)
    fetch.add_argument("--source", choices=["auto", "captions", "whisper"], default="auto")
    fetch.add_argument("--format", choices=["json", "txt", "srt", "vtt"], default="json")
    fetch.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    try:
        service = TranscriptService()
        if arguments.command in {None, "serve"}:
            from youtube_transcript_mcp.server import create_server

            create_server(service).run(transport="stdio")
            return
        if arguments.command == "doctor":
            print(json.dumps(service.status(), indent=2))
            return
        if arguments.command == "list":
            tracks = service.list_captions(arguments.video)
            print(
                json.dumps([track.model_dump() for track in tracks], ensure_ascii=False, indent=2)
            )
            return
        result = service.get_transcript(arguments.video, arguments.languages, arguments.source)
        if arguments.format == "json":
            output = result.model_dump_json(indent=2)
        elif arguments.format == "txt":
            output = result.text
        else:
            output = render_subtitles(result, arguments.format)
        if arguments.output:
            arguments.output.write_text(output, encoding="utf-8")
        else:
            print(output)
    except (TranscriptError, OSError) as error:
        message = (
            str(error) if isinstance(error, TranscriptError) else "Could not write output file."
        )
        print(f"Error: {message}", file=sys.stderr)
        raise SystemExit(1) from None
