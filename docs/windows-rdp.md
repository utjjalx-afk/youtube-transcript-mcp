# Windows RDP setup

This server runs on the machine where Hermes launches its MCP subprocess. A
public RDP IP alone is not an MCP endpoint. You do not need to open an additional
firewall port or expose this server on the internet.

## Native setup (recommended)

1. Install Python 3.11+ and Git from their official installers.
2. Open PowerShell in a folder you own and clone the repository.
3. Create a dedicated virtual environment and install:

```powershell
git clone https://github.com/utjjalx-afk/youtube-transcript-mcp.git
cd youtube-transcript-mcp
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[whisper]"
.\.venv\Scripts\python.exe -m youtube_transcript_mcp doctor
```

If `python` is not on PATH, use `py -3.11` or `py -3.12` to create the venv.
The installed interpreter must be Python 3.11 or newer.

4. Resolve the interpreter path with:

```powershell
(Resolve-Path .\.venv\Scripts\python.exe).Path
```

5. Replace the placeholder in `examples/hermes-windows.yaml` with that path,
   merge it into `$HOME\.hermes\config.yaml`, then restart Hermes or `/reload-mcp`.
6. Ask Hermes to call `get_status`, then `list_captions` / `get_transcript`.

Single-quoted Windows paths in YAML preserve backslashes. Standard JSON requires
escaped backslashes, as shown in `examples/mcp-client.json`. No venv activation
or system PowerShell execution-policy change is required.

## CPU and storage

No GPU is required. `small` with CPU/int8 is the default. Allow roughly a 500 MB
model download and around 1 GB RAM (actual usage varies). For a low-memory machine,
set `YTMCP_WHISPER_MODEL` to `tiny`. Model weights consume disk and require network
access on first use. Model initialization happens on first transcription, not at
MCP startup, so the initial connection stays fast. Downloaded audio is temporary.
Use `source=captions` for fast lightweight requests with no model/audio download.

Faster-Whisper uses bundled PyAV decoding, without a system FFmpeg requirement
for this implementation. NVIDIA inference is optional and requires the CUDA/cuDNN
versions supported by your installed CTranslate2/Faster-Whisper stack; this project
does not install or manage GPU drivers.

For Hindi speech, set `YTMCP_WHISPER_LANGUAGE=hi` in the server environment or use
`fetch --source whisper --whisper-language hi`. Caption `--languages` remains
independent. The `small` model is the recommended starting point for Hindi/Indic;
`base` can be faster but weaker on non-English speech.

If decoding reports `metadata_errors`, reinstall the updated Whisper extra with
`.\.venv\Scripts\python.exe -m pip install -e ".[whisper]"`. It constrains PyAV to
`av>=11,<19`; PyAV 19 is incompatible with Faster-Whisper 1.2.1 decoding. `doctor`
shows the installed version and whether the constraint is satisfied. For provider
diagnostics, set `$env:YTMCP_DEBUG = "true"` temporarily; error causes/tracebacks
remain visible with credential redaction.

## Network and security

- Rented RDP/datacenter addresses may be blocked by YouTube. Whisper fallback
  cannot solve an audio-download block. Avoid request bursts and respect access
  restrictions.
- Keep RDP protected with strong authentication and restricted firewall access.
- Do not put login passwords, tokens, cookies or proxy credentials into GitHub.
- If you configure an authorized cookie file, keep it outside the repo. The
  caption backend does not use it; yt-dlp alone may use it.
- Only merge the example config; never replace your whole Hermes config.
- Running on this local computer does not automatically install it on a separate
  rented RDP machine. Repeat these steps there if that is where Hermes runs.
