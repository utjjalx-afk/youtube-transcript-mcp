import wave

import pytest


def test_whisper_extra_decodes_audio_with_supported_pyav(tmp_path):
    av = pytest.importorskip("av")
    audio_module = pytest.importorskip("faster_whisper.audio")
    assert 11 <= int(av.__version__.split(".")[0]) < 19
    audio = tmp_path / "silence.wav"
    with wave.open(str(audio), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(16000)
        output.writeframes(b"\x00\x00" * 16000)
    assert len(audio_module.decode_audio(str(audio))) == 16000
