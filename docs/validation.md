# Validation

Initial version validated on 2026-10-03, Windows x64, Python 3.11.15.

| Check | Result |
| --- | --- |
| Offline test suite | 68 tests passed; 93% package statement coverage |
| Real MCP stdio | Initialization, discovery of all 3 tools, status call and invalid-input tool error passed |
| Ruff lint and format | Passed |
| Package build | Wheel and source distribution built successfully |
| Dependency consistency | `pip check` passed |
| Live captions | Public short test video returned 6 caption segments |
| Live yt-dlp audio download | Download succeeded; temporary audio cleaned up |
| Real Whisper CPU inference | `tiny`/CPU/int8 returned 2 segments, detected English |

The live test used the short public video `jNQXAC9IVRw`. No transcript text,
downloaded audio, model weights, cookies or private configuration is committed.
Provider availability and segment counts can change; success on this local
network does not guarantee success on another RDP/datacenter IP.

Validation dependency versions: MCP 1.30.0, youtube-transcript-api 1.2.4,
yt-dlp 2026.8.19 and Faster-Whisper 1.2.1. This is a record of tested versions,
not a lockfile. The real inference smoke test used `tiny`; the default model
setting is `base`. CUDA and Docker execution were not tested locally. GitHub
Actions separately runs the offline suite on Windows/Ubuntu and Python 3.11/3.12.
