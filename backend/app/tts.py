"""Optional Kokoro text-to-speech for cook-mode narration."""

from __future__ import annotations

import asyncio
import hashlib
import subprocess
import tempfile
from pathlib import Path

from app import config


class TTSError(RuntimeError):
    pass

_MAX_TTS_CHARS = 1200


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
    if "flac" in mt:
        return ".flac"
    return ".wav"


def _media_type_for_audio(audio: bytes) -> str:
    if audio.startswith(b"ID3") or audio[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"):
        return "audio/mpeg"
    if audio.startswith(b"OggS"):
        return "audio/ogg"
    if audio.startswith(b"fLaC"):
        return "audio/flac"
    if audio.startswith(b"RIFF") and len(audio) > 12 and audio[8:12] == b"WAVE":
        return "audio/wav"
    return "audio/wav"


def _cache_key(text: str, voice: str) -> str:
    payload = "|".join([config.KOKORO_TTS_PROVIDER, config.KOKORO_MODEL, voice, text])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _from_cache(text: str, voice: str) -> tuple[bytes, str] | None:
    key = _cache_key(text, voice)
    for ext, media in (
        (".wav", "audio/wav"),
        (".mp3", "audio/mpeg"),
        (".ogg", "audio/ogg"),
        (".flac", "audio/flac"),
    ):
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


def _split_tts_chunks(text: str, max_len: int = _MAX_TTS_CHARS) -> list[str]:
    if len(text) <= max_len:
        return [text]
    parts: list[str] = []
    buf = ""
    for sentence in text.replace("\n", " ").split(". "):
        piece = f"{sentence}. ".strip()
        if not piece:
            continue
        if len(buf) + len(piece) + 1 <= max_len:
            buf = f"{buf} {piece}".strip()
        else:
            if buf:
                parts.append(buf)
            buf = piece if len(piece) <= max_len else piece[:max_len]
    if buf:
        parts.append(buf)
    return parts or [text[:max_len]]


def _ffmpeg_to_wav(audio: bytes) -> bytes:
    if not config.ffmpeg_available():
        raise TTSError("ffmpeg is required to convert Kokoro audio for browser playback.")
    proc = subprocess.run(
        [
            config.FFMPEG_BIN,
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            "pipe:0",
            "-f",
            "wav",
            "-acodec",
            "pcm_s16le",
            "pipe:1",
        ],
        input=audio,
        capture_output=True,
        timeout=120,
        check=False,
    )
    if proc.returncode != 0 or not proc.stdout:
        detail = proc.stderr.decode("utf-8", errors="replace").strip() or "unknown ffmpeg error"
        raise TTSError(f"Audio conversion failed: {detail}")
    return proc.stdout


def _concat_wav_parts(parts: list[bytes]) -> bytes:
    if len(parts) == 1:
        return parts[0]
    if not config.ffmpeg_available():
        raise TTSError("ffmpeg is required to stitch long Kokoro narrations.")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        list_file = tmp_path / "concat.txt"
        wav_paths: list[Path] = []
        for i, part in enumerate(parts):
            path = tmp_path / f"part-{i}.wav"
            path.write_bytes(part)
            wav_paths.append(path)
        list_file.write_text("\n".join(f"file '{p.name}'" for p in wav_paths), encoding="utf-8")
        proc = subprocess.run(
            [
                config.FFMPEG_BIN,
                "-hide_banner",
                "-loglevel",
                "error",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(list_file),
                "-f",
                "wav",
                "-acodec",
                "pcm_s16le",
                "pipe:1",
            ],
            cwd=tmp,
            capture_output=True,
            timeout=180,
            check=False,
        )
        if proc.returncode != 0 or not proc.stdout:
            detail = proc.stderr.decode("utf-8", errors="replace").strip() or "unknown ffmpeg error"
            raise TTSError(f"Audio stitching failed: {detail}")
        return proc.stdout


def _normalize_for_browser(audio: bytes, media_type: str) -> tuple[bytes, str]:
    if media_type == "audio/mpeg" or audio[:3] == b"ID3" or audio[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"):
        return audio, "audio/mpeg"
    if audio.startswith(b"RIFF") and len(audio) > 12 and audio[8:12] == b"WAVE":
        return audio, "audio/wav"
    return _ffmpeg_to_wav(audio), "audio/wav"


def _hf_inference_provider() -> str:
    """Map app provider names to huggingface_hub InferenceClient provider ids."""
    p = config.KOKORO_TTS_PROVIDER
    if p in ("huggingface", "hf"):
        return "fal-ai"
    return p


def _uses_kokoro_huggingface() -> bool:
    return config.KOKORO_TTS_PROVIDER in ("fal-ai", "huggingface", "hf")


def _synthesize_huggingface(text: str, voice: str) -> tuple[bytes, str]:
    if not config.HUGGINGFACE_API_KEY:
        raise TTSError("HUGGINGFACE_API_KEY or HF_TOKEN is required for Kokoro Hugging Face TTS.")

    provider = _hf_inference_provider()
    InferenceClient = _inference_client_cls()
    client = InferenceClient(
        provider=provider,
        api_key=config.HUGGINGFACE_API_KEY,
    )
    try:
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




def _synthesize_edge(text: str, voice: str) -> tuple[bytes, str]:
    try:
        import edge_tts
    except ImportError as e:
        raise TTSError("edge-tts is required for KOKORO_TTS_PROVIDER=edge.") from e

    async def _run() -> bytes:
        communicate = edge_tts.Communicate(text, voice=voice or config.EDGE_TTS_VOICE)
        chunks: list[bytes] = []
        async for chunk in communicate.stream():
            if chunk.get("type") == "audio" and chunk.get("data"):
                chunks.append(chunk["data"])
        return b"".join(chunks)

    try:
        audio = asyncio.run(_run())
    except Exception as e:  # noqa: BLE001
        raise TTSError(f"Edge TTS failed: {e}") from e
    if not audio:
        raise TTSError("Edge TTS returned empty audio.")
    return audio, "audio/mpeg"


def _is_edge_voice_name(voice: str) -> bool:
    """True for Microsoft Edge neural voices, e.g. en-US-AriaNeural."""
    v = voice.strip()
    return "-" in v and v.endswith("Neural")


def _resolve_tts_voice(voice: str | None) -> str:
    """Pick voice for the active provider; Kokoro IDs map to EDGE_TTS_VOICE on edge."""
    raw = (voice or "").strip()
    if config.KOKORO_TTS_PROVIDER in ("edge", "kokoro"):
        if raw and _is_edge_voice_name(raw):
            return raw
        return config.EDGE_TTS_VOICE
    return raw or config.KOKORO_VOICE or "af_heart"


def _synthesize_provider_chunk(text: str, voice: str) -> tuple[bytes, str]:
    provider = config.KOKORO_TTS_PROVIDER
    if provider in ("edge", "kokoro"):
        return _synthesize_edge(text, voice)
    if _uses_kokoro_huggingface():
        return _synthesize_huggingface(text, voice)
    return _synthesize_edge(text, voice)


def tts_provider_available() -> bool:
    """True when ENABLE_KOKORO_TTS is on and the configured provider can be imported."""
    if not config.ENABLE_KOKORO_TTS:
        return False
    provider = config.KOKORO_TTS_PROVIDER
    if provider in ("edge", "kokoro"):
        try:
            import edge_tts  # noqa: F401
        except ImportError:
            return False
        return True
    if provider in ("fal-ai", "huggingface", "hf"):
        try:
            from huggingface_hub import InferenceClient  # noqa: F401
        except ImportError:
            return False
        return bool(config.HUGGINGFACE_API_KEY)
    return False


def synthesize_kokoro(text: str, voice: str | None = None) -> tuple[bytes, str]:
    if not config.ENABLE_KOKORO_TTS:
        raise TTSError("Kokoro TTS is disabled.")
    clean = " ".join(text.split())
    if not clean:
        raise TTSError("No text provided for TTS.")
    selected_voice = _resolve_tts_voice(voice)

    cached = _from_cache(clean, selected_voice)
    if cached:
        return cached

    normalized_parts: list[tuple[bytes, str]] = []
    for chunk in _split_tts_chunks(clean):
        raw, media_type = _synthesize_provider_chunk(chunk, selected_voice)
        normalized_parts.append(_normalize_for_browser(raw, media_type))

    if len(normalized_parts) == 1:
        audio, media_type = normalized_parts[0]
    else:
        wav_parts = [part if mt == "audio/wav" else _ffmpeg_to_wav(part) for part, mt in normalized_parts]
        audio, media_type = _concat_wav_parts(wav_parts), "audio/wav"

    _write_cache(clean, selected_voice, audio, media_type)
    return audio, media_type
