import app.config as config
from app.tts import TTSError, _synthesize_huggingface, synthesize_kokoro


def test_kokoro_tts_disabled(monkeypatch):
    monkeypatch.setattr(config, "ENABLE_KOKORO_TTS", False)

    try:
        synthesize_kokoro("Read this step.")
    except TTSError as e:
        assert "disabled" in str(e).lower()
    else:
        raise AssertionError("Expected disabled Kokoro TTS to raise")


def test_kokoro_tts_writes_and_reads_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "ENABLE_KOKORO_TTS", True)
    monkeypatch.setattr(config, "KOKORO_TTS_PROVIDER", "huggingface")
    monkeypatch.setattr(config, "KOKORO_MODEL", "hexgrad/Kokoro-82M")
    monkeypatch.setattr(config, "TTS_CACHE_DIR", tmp_path)
    calls = {"count": 0}

    def fake_provider(text: str, voice: str):
        calls["count"] += 1
        return b"RIFF\x00\x00\x00\x00WAVEfake", "audio/wav"

    monkeypatch.setattr("app.tts._synthesize_huggingface", fake_provider)

    first = synthesize_kokoro("hello cook mode", "af_heart")
    second = synthesize_kokoro("hello cook mode", "af_heart")

    assert first == second
    assert first[0].startswith(b"RIFF")
    assert calls["count"] == 1


def test_huggingface_fal_provider_uses_inference_client(monkeypatch):
    monkeypatch.setattr(config, "HUGGINGFACE_API_KEY", "hf_test")
    monkeypatch.setattr(config, "KOKORO_TTS_PROVIDER", "fal-ai")
    monkeypatch.setattr(config, "KOKORO_MODEL", "hexgrad/Kokoro-82M")
    calls = {"client": None, "tts": None}

    class FakeInferenceClient:
        def __init__(self, provider: str, api_key: str):
            calls["client"] = {"provider": provider, "api_key": api_key}

        def text_to_speech(self, text: str, model: str, extra_body: dict):
            calls["tts"] = {"text": text, "model": model, "extra_body": extra_body}
            return b"RIFFaudio"

    monkeypatch.setattr("app.tts._inference_client_cls", lambda: FakeInferenceClient)

    audio, media_type = _synthesize_huggingface("hello", "af_heart")

    assert audio == b"RIFFaudio"
    assert media_type == "audio/wav"
    assert calls["client"] == {"provider": "fal-ai", "api_key": "hf_test"}
    assert calls["tts"] == {
        "text": "hello",
        "model": "hexgrad/Kokoro-82M",
        "extra_body": {"voice": "af_heart"},
    }


def test_kokoro_provider_uses_fal_ai_inference(monkeypatch):
    monkeypatch.setattr(config, "HUGGINGFACE_API_KEY", "hf_test")
    monkeypatch.setattr(config, "KOKORO_TTS_PROVIDER", "kokoro")
    monkeypatch.setattr(config, "KOKORO_MODEL", "hexgrad/Kokoro-82M")
    calls = {"client": None}

    class FakeInferenceClient:
        def __init__(self, provider: str, api_key: str):
            calls["client"] = {"provider": provider, "api_key": api_key}

        def text_to_speech(self, text: str, model: str, extra_body: dict):
            return b"RIFFaudio"

    monkeypatch.setattr("app.tts._inference_client_cls", lambda: FakeInferenceClient)

    _synthesize_huggingface("hello cook mode", "af_heart")

    assert calls["client"] == {"provider": "fal-ai", "api_key": "hf_test"}


def test_edge_provider_uses_edge_tts(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "ENABLE_KOKORO_TTS", True)
    monkeypatch.setattr(config, "KOKORO_TTS_PROVIDER", "edge")
    monkeypatch.setattr(config, "EDGE_TTS_VOICE", "en-US-JennyNeural")
    monkeypatch.setattr(config, "TTS_CACHE_DIR", tmp_path)

    calls = {"count": 0}

    def fake_edge(text: str, voice: str):
        calls["count"] += 1
        return b"ID3fake-mp3", "audio/mpeg"

    monkeypatch.setattr("app.tts._synthesize_edge", fake_edge)

    audio, media = synthesize_kokoro("hello from edge", None)

    assert media == "audio/mpeg"
    assert audio.startswith(b"ID3")
    assert calls["count"] == 1


def test_edge_provider_maps_kokoro_voice_id(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "ENABLE_KOKORO_TTS", True)
    monkeypatch.setattr(config, "KOKORO_TTS_PROVIDER", "edge")
    monkeypatch.setattr(config, "EDGE_TTS_VOICE", "en-US-JennyNeural")
    monkeypatch.setattr(config, "TTS_CACHE_DIR", tmp_path)

    captured: dict[str, str] = {}

    def fake_edge(text: str, voice: str):
        captured["voice"] = voice
        return b"ID3fake-mp3", "audio/mpeg"

    monkeypatch.setattr("app.tts._synthesize_edge", fake_edge)

    synthesize_kokoro("hello cook mode", "af_heart")

    assert captured["voice"] == "en-US-JennyNeural"
