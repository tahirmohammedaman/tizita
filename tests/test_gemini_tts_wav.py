from tizita.providers.base import pcm16_to_wav, wav_duration_s
from tizita.providers.gemini_tts import as_wav


def test_raw_pcm_is_wrapped_once():
    wav = as_wav(b"\x00\x00" * 2400, 24000)
    assert wav[:4] == b"RIFF" and wav.count(b"RIFF") == 1
    assert wav_duration_s(wav) == 0.1


def test_wav_answer_keeps_its_bytes_and_trailing_chunk():
    original = pcm16_to_wav(b"\x00\x00" * 2400, 24000) + b"C2PA\x04\x00\x00\x00abcd"
    assert as_wav(original, 24000) == original
    assert wav_duration_s(as_wav(original, 24000)) == 0.1
