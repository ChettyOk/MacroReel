import os
import secrets
import shutil
from pathlib import Path

from dotenv import dotenv_values

_backend_dir = Path(__file__).resolve().parent.parent
_real_env_keys = set(os.environ)


def _load_local_env(path: Path) -> None:
    for key, value in dotenv_values(path).items():
        if value is not None and key not in _real_env_keys:
            os.environ[key] = value


# Load local env files without overriding real shell/Render env vars. backend/.env wins over root .env locally.
_load_local_env(_backend_dir.parent / ".env")
_load_local_env(_backend_dir / ".env")

BACKEND_DIR = _backend_dir


def _writable_dir(path: Path, fallback: Path) -> Path:
    try:
        path.mkdir(parents=True, exist_ok=True)
        return path
    except OSError:
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback


_data_default = _backend_dir / "data"
DATA_DIR = _writable_dir(Path(os.getenv("DATA_DIR", str(_data_default))).expanduser(), _data_default)

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
KOKORO_TTS_PROVIDER: str = os.getenv("KOKORO_TTS_PROVIDER", "edge").strip().lower() or "edge"
EDGE_TTS_VOICE: str = os.getenv("EDGE_TTS_VOICE", "en-US-AriaNeural").strip() or "en-US-AriaNeural"
KOKORO_MODEL: str = os.getenv("KOKORO_MODEL", "hexgrad/Kokoro-82M").strip()
KOKORO_VOICE: str = os.getenv("KOKORO_VOICE", "af_heart").strip() or "af_heart"
KOKORO_LANG_CODE: str = os.getenv("KOKORO_LANG_CODE", "a").strip() or "a"
HUGGINGFACE_API_KEY: str = _clean_secret(os.getenv("HUGGINGFACE_API_KEY", "") or os.getenv("HF_TOKEN", ""))
TTS_CACHE_DIR = _writable_dir(Path(os.getenv("TTS_CACHE_DIR", str(DATA_DIR / "tts"))).expanduser(), DATA_DIR / "tts")

# ── yt-dlp cookies / YouTube hardening (see README) ──
YTDLP_COOKIES_FILE: str = os.getenv("YTDLP_COOKIES_FILE", "").strip()
# Paste a Netscape cookies.txt body directly (handy on Render where you can't upload files).
# Accepts raw text or base64-encoded text. Written to DATA_DIR at runtime.
YTDLP_COOKIES_CONTENT: str = os.getenv("YTDLP_COOKIES_CONTENT", "")
YTDLP_COOKIES_FROM_BROWSER: str = os.getenv("YTDLP_COOKIES_FROM_BROWSER", "").strip()
YTDLP_YOUTUBE_PLAYER_CLIENTS: str = os.getenv("YTDLP_YOUTUBE_PLAYER_CLIENTS", "").strip()

# Comma-separated extra CORS origins (the Vite dev server is always allowed).
EXTRA_CORS_ORIGINS: str = os.getenv("EXTRA_CORS_ORIGINS", "").strip()

# ── Auth (JWT + Google OAuth) ──
JWT_SECRET: str = _clean_secret(os.getenv("JWT_SECRET", "")) or secrets.token_urlsafe(32)
JWT_ALGORITHM: str = "HS256"
JWT_EXPIRE_MINUTES: int = int(os.getenv("JWT_EXPIRE_MINUTES", str(60 * 24 * 7)) or str(60 * 24 * 7))
GOOGLE_CLIENT_ID: str = _clean_secret(os.getenv("GOOGLE_CLIENT_ID", "") or os.getenv("VITE_GOOGLE_CLIENT_ID", ""))


def ffmpeg_available() -> bool:
    return shutil.which(FFMPEG_BIN) is not None and shutil.which(FFPROBE_BIN) is not None
