import os
import shutil
from pathlib import Path

from dotenv import load_dotenv

_backend_dir = Path(__file__).resolve().parent.parent
# Load the project root .env first, then backend/.env (backend wins for duplicate keys).
load_dotenv(_backend_dir.parent / ".env", override=True)
load_dotenv(_backend_dir / ".env", override=True)

BACKEND_DIR = _backend_dir

_data_default = _backend_dir / "data"
DATA_DIR = Path(os.getenv("DATA_DIR", str(_data_default))).expanduser()
DATA_DIR.mkdir(parents=True, exist_ok=True)

_static_default = _backend_dir / "static"
STATIC_DIR = Path(os.getenv("STATIC_DIR", str(_static_default))).expanduser()

PORT = int(os.getenv("PORT", "8000") or "8000")


def _clean_secret(value: str) -> str:
    """Strip BOM, quotes, and accidental newlines from .env secrets (common .env editor issues)."""
    if not value:
        return ""
    s = value.strip()
    if s.startswith("\ufeff"):
        s = s.lstrip("\ufeff")
    if len(s) >= 2 and ((s[0] == s[-1] == '"') or (s[0] == s[-1] == "'")):
        s = s[1:-1].strip()
    s = s.replace("\r", "").replace("\n", "")
    return s.strip()


def _flag(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


# ── Google AI Studio / Gemini (free tier): https://aistudio.google.com/app/apikey ──
GEMINI_API_KEY: str = _clean_secret(os.getenv("GEMINI_API_KEY", "") or os.getenv("GOOGLE_API_KEY", ""))
# Default flash-lite: better free-tier availability than gemini-2.0-flash for many keys.
GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash-lite").strip()
GEMINI_MODEL_FALLBACKS: str = os.getenv(
    "GEMINI_MODEL_FALLBACKS",
    "gemini-2.0-flash-lite,gemini-2.5-flash-lite,gemini-2.5-flash,gemini-1.5-flash,gemini-2.0-flash",
).strip()
GEMINI_FALLBACK_ON_QUOTA: bool = _flag("GEMINI_FALLBACK_ON_QUOTA", True)

# ── Media pipeline (download + ffmpeg + Gemini audio transcription + frame vision) ──
# Off by default: keeps the app light and avoids downloading videos unless you opt in.
ENABLE_MEDIA_PIPELINE: bool = _flag("ENABLE_MEDIA_PIPELINE", False)
ENABLE_TRANSCRIPTION: bool = _flag("ENABLE_TRANSCRIPTION", True)  # within media pipeline
ENABLE_FRAME_VISION: bool = _flag("ENABLE_FRAME_VISION", True)  # within media pipeline
FRAME_INTERVAL_SEC: int = int(os.getenv("FRAME_INTERVAL_SEC", "4") or "4")
MAX_FRAMES: int = int(os.getenv("MAX_FRAMES", "8") or "8")
MAX_VIDEO_SECONDS: int = int(os.getenv("MAX_VIDEO_SECONDS", "240") or "240")
FFMPEG_BIN: str = os.getenv("FFMPEG_BIN", "ffmpeg").strip() or "ffmpeg"
FFPROBE_BIN: str = os.getenv("FFPROBE_BIN", "ffprobe").strip() or "ffprobe"

# ── Nutrition: USDA FoodData Central (free): https://fdc.nal.usda.gov/api-key-signup.html ──
USDA_API_KEY: str = _clean_secret(os.getenv("USDA_API_KEY", ""))
ENABLE_NUTRITION: bool = _flag("ENABLE_NUTRITION", True)
# AI nutrition estimates are non-deterministic and only run when no video-stated macros are found.
ENABLE_GEMINI_NUTRITION: bool = _flag("ENABLE_GEMINI_NUTRITION", False)

# ── Grocery pricing: optional live/partner JSON feed; built-in estimates are fallback only. ──
SPOONACULAR_API_KEY: str = _clean_secret(os.getenv("SPOONACULAR_API_KEY", ""))
GROCERY_PRICE_FEED_URL: str = os.getenv("GROCERY_PRICE_FEED_URL", "").strip()
GROCERY_PRICE_FEED_FILE: str = os.getenv("GROCERY_PRICE_FEED_FILE", "").strip()
GROCERY_PRICE_CACHE_TTL_SEC: int = int(os.getenv("GROCERY_PRICE_CACHE_TTL_SEC", "3600") or "3600")

# ── Text-to-speech: optional Kokoro cook-mode narration ──
ENABLE_KOKORO_TTS: bool = _flag("ENABLE_KOKORO_TTS", False)
KOKORO_TTS_PROVIDER: str = os.getenv("KOKORO_TTS_PROVIDER", "fal-ai").strip().lower() or "fal-ai"
KOKORO_MODEL: str = os.getenv("KOKORO_MODEL", "hexgrad/Kokoro-82M").strip()
KOKORO_VOICE: str = os.getenv("KOKORO_VOICE", "af_heart").strip() or "af_heart"
KOKORO_LANG_CODE: str = os.getenv("KOKORO_LANG_CODE", "a").strip() or "a"
HUGGINGFACE_API_KEY: str = _clean_secret(os.getenv("HUGGINGFACE_API_KEY", "") or os.getenv("HF_TOKEN", ""))
TTS_CACHE_DIR = Path(os.getenv("TTS_CACHE_DIR", str(DATA_DIR / "tts"))).expanduser()
TTS_CACHE_DIR.mkdir(parents=True, exist_ok=True)

# ── yt-dlp cookies / YouTube hardening (see README) ──
YTDLP_COOKIES_FILE: str = os.getenv("YTDLP_COOKIES_FILE", "").strip()
YTDLP_COOKIES_FROM_BROWSER: str = os.getenv("YTDLP_COOKIES_FROM_BROWSER", "").strip()
YTDLP_YOUTUBE_PLAYER_CLIENTS: str = os.getenv("YTDLP_YOUTUBE_PLAYER_CLIENTS", "").strip()

# Comma-separated extra CORS origins (the Vite dev server is always allowed).
EXTRA_CORS_ORIGINS: str = os.getenv("EXTRA_CORS_ORIGINS", "").strip()


def ffmpeg_available() -> bool:
    return shutil.which(FFMPEG_BIN) is not None and shutil.which(FFPROBE_BIN) is not None
