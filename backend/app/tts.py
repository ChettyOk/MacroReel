"""Optional Kokoro text-to-speech for cook-mode narration."""

from __future__ import annotations

import hashlib
import io

from app import config


class TTSError(RuntimeError):
    pass


def _inference_client_cls():
    try:
        from huggingface_hub import InferenceClient
    except ImportError as e:
        raise TTSError("huggingface_hub is required for Kokoro Hugging Face TTS.") from e
    return InferenceClient


def _ext_for_media(media_type: str) -> str:
    mt = media_type.lower()
    if "mpeg" in mt or "mp3" in mt:
        return ".mp3"
    if "ogg" in mt:
        return ".ogg"
    return ".wav"


def _media_type_for_audio(audio: bytes) -> str:
    if audio.startswith(b"ID3") or audio[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"):
        return "audio/mpeg"
    if audio.startswith(b"OggS"):
        return "audio/ogg"
    return "audio/wav"


def _cache_key(text: str, voice: str) -> str:
    payload = "|".join([config.KOKORO_TTS_PROVIDER, config.KOKORO_MODEL, voice, text])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _from_cache(text: str, voice: str) -> tuple[bytes, str] | None:
    key = _cache_key(text, voice)
    for ext, media in ((".mp3", "audio/mpeg"), (".ogg", "audio/ogg"), (".wav", "audio/wav")):
        path = config.TTS_CACHE_DIR / f"{key}{ext}"
        if path.is_file():
            try:
                return path.read_bytes(), media
            except OSError:
                return None
    return None


def _write_cache(text: str, voice: str, audio: bytes, media_type: str) -> None:
    key = _cache_key(text, voice)
    path = config.TTS_CACHE_DIR / f"{key}{_ext_for_media(media_type)}"
    try:
        path.write_bytes(audio)
    except OSError:
        pass


def _synthesize_huggingface(text: str, voice: str) -> tuple[bytes, str]:
    if not config.HUGGINGFACE_API_KEY:
        raise TTSError("HUGGINGFACE_API_KEY or HF_TOKEN is required for Kokoro Hugging Face TTS.")

    provider = config.KOKORO_TTS_PROVIDER if config.KOKORO_TTS_PROVIDER != "huggingface" else "fal-ai"
    InferenceClient = _inference_client_cls()
    client = InferenceClient(
        provider=provider,
        api_key=config.HUGGINGFACE_API_KEY,
    )
    try:
        # Mirrors:
        # client.text_to_speech("...", model="hexgrad/Kokoro-82M")
        audio = client.text_to_speech(
            text,
            model=config.KOKORO_MODEL,
            extra_body={"voice": voice},
        )
    except Exception as e:  # noqa: BLE001
        raise TTSError(f"Kokoro Hugging Face TTS failed: {e}") from e
    if not audio:
        raise TTSError("Kokoro Hugging Face TTS returned empty audio.")
    return audio, _media_type_for_audio(audio)


def _synthesize_local(text: str, voice: str) -> tuple[bytes, str]:
    try:
        import numpy as np
        import soundfile as sf
        from kokoro import KPipeline
    except Exception as e:  # noqa: BLE001
        raise TTSError("Local Kokoro TTS requires kokoro, soundfile, numpy, and espeak-ng.") from e

    pipeline = KPipeline(lang_code=config.KOKORO_LANG_CODE)
    chunks = []
    for _, _, audio in pipeline(text, voice=voice):
        chunks.append(audio)
    if not chunks:
        raise TTSError("Local Kokoro TTS returned empty audio.")
    audio = np.concatenate(chunks)
    buf = io.BytesIO()
    sf.write(buf, audio, 24000, format="WAV")
    return buf.getvalue(), "audio/wav"


def synthesize_kokoro(text: str, voice: str | None = None) -> tuple[bytes, str]:
    if not config.ENABLE_KOKORO_TTS:
        raise TTSError("Kokoro TTS is disabled.")
    clean = " ".join(text.split())
    if not clean:
        raise TTSError("No text provided for TTS.")
    selected_voice = (voice or config.KOKORO_VOICE).strip() or "af_heart"

    cached = _from_cache(clean, selected_voice)
    if cached:
        return cached

    if config.KOKORO_TTS_PROVIDER == "local":
        audio, media_type = _synthesize_local(clean, selected_voice)
    else:
        audio, media_type = _synthesize_huggingface(clean, selected_voice)

    _write_cache(clean, selected_voice, audio, media_type)
    return audio, media_type
