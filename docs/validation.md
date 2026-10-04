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
setting was `base` for the initial version. CUDA and Docker execution were not tested locally. GitHub
Actions separately runs the offline suite on Windows/Ubuntu and Python 3.11/3.12.

## v1.1.0 update (2026-10-04)

Reproduced the reported decoding failure in an isolated Windows x64 Python 3.12.14
environment with Faster-Whisper 1.2.1 and PyAV 19.0.1. A generated one-second WAV
failed with `TypeError: open() got an unexpected keyword argument 'metadata_errors'`
inside `faster_whisper.audio.decode_audio`.

**PyAV 19 breaks faster-whisper 1.2.1 decode (metadata_errors); keep av<19 until
faster-whisper supports it.** The upstream development branch has a compatibility
fix, but this project conservatively constrains released installations to
`av>=11,<19`.

- Installing the updated Whisper extra downgraded PyAV 19.0.1 to 18.1.0; the same
  generated WAV decoded successfully (16,000 samples).
- A completely fresh Python 3.12 venv with `pip install -e ".[whisper]"` also
  resolved PyAV 18.1.0, passed `pip check`, and decoded the WAV successfully.
- Local Python 3.12 suite: 103 tests passed, 93% statement coverage, including a
  real PyAV/Faster-Whisper decode regression test. Python 3.11 also passed the
  configuration/provider tests. The audio test skips when the optional Whisper
  dependencies are not installed.
- `doctor` reports `whisper_model=small`, `whisper_language=null`,
  `av_constraint=av>=11,<19`, `av_version=18.1.0`, and `av_constraint_active=true`.
- The unchanged captions CLI command for `dQw4w9WgXcQ` returned text successfully.
- Forced transcription failures preserve `TypeError` and `metadata_errors` in
  normal errors; debug mode preserves the original traceback. Tests cover
  credential redaction in chained exceptions and notes, including debug mode.
- Ruff checks and the v1.1.0 wheel/source-distribution build passed.

The new Windows Python 3.12 CI decode job installs the real Whisper extra and
decodes a generated WAV without downloading model weights. Other CI jobs remain
offline and captions-only. Model inference uses `condition_on_previous_text=False`
and adds a warning below 0.35 language probability. Whisper model default is now
`small`, and caption-language preferences remain independent of Whisper hints.

### Hindi clip quality limitation

The first 60 seconds of the user-supplied public video `LpCfEoIb1MU` were recreated
locally as a 16 kHz mono WAV from its original Hindi Opus track (format 251).
The user's saved M4A on a different Windows machine was not available here.
The updated service with `small`/CPU/int8 and a per-call `hi` hint completed
without `metadata_errors`: 17 segments, language `hi`, and Devanagari output.

**The near-perfect reference accuracy was not reproduced.** The result contained
misspellings and mixed-script hallucinations after the opening speech. A separate
test using the upstream decoder directly also produced mixed-script text with
`condition_on_previous_text=False`; enabling previous-text context produced a
shorter, more consistently Devanagari result but still had errors. This does not
establish whether the original saved M4A would give the same result.

The required guard remains disabled (`condition_on_previous_text=False`) as
specified in the update brief. Language hints and a larger default model are not
a guarantee of transcription quality. Prefer captions when available, and review
transcripts rather than treating a forced-language probability of 1.0 as proof of
accuracy. Exact baseline comparison requires the original saved clip.
