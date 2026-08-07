"""Fetch title, description, and caption text from supported video URLs via yt-dlp."""

from __future__ import annotations

import base64
import binascii
import http.cookiejar
import logging
import re
import shutil
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

import yt_dlp

from app.config import (
    BACKEND_DIR,
    DATA_DIR,
    YTDLP_COOKIES_CONTENT,
    YTDLP_COOKIES_FILE,
    YTDLP_COOKIES_FROM_BROWSER,
    YTDLP_YOUTUBE_PLAYER_CLIENTS,
)
from app.thumbnail import pick_best_thumbnail

logger = logging.getLogger(__name__)

MAX_TRANSCRIPT_CHARS = 18_000

_SUB_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def _normalize_cookies_text(raw: str) -> str:
    """Accept raw cookies.txt text or base64-encoded text; return Netscape text."""
    text = raw.strip()
    if not text:
        return ""
    # If it doesn't already look like a Netscape cookie jar, try base64.
    if "\t" not in text and "# Netscape" not in text and "# HTTP Cookie File" not in text:
        compact = "".join(text.split())
        try:
            decoded = base64.b64decode(compact, validate=True).decode("utf-8")
            if decoded.strip():
                text = decoded
        except (binascii.Error, ValueError, UnicodeDecodeError):
            pass
    if not text.startswith("#"):
        text = "# Netscape HTTP Cookie File\n" + text
    if not text.endswith("\n"):
        text += "\n"
    return text


def _writable_cookie_path(source: Path | None = None, *, content: str | None = None) -> Path | None:
    """
    Materialize cookies into DATA_DIR so yt-dlp can update the jar without
    failing on a full disk / read-only source path.
    """
    target = DATA_DIR / "yt-dlp-cookies.txt"
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        if content is not None:
            text = _normalize_cookies_text(content)
            if not text:
                return None
            target.write_text(text, encoding="utf-8")
            return target
        if source is None or not source.is_file():
            return None
        shutil.copyfile(source, target)
        return target
    except OSError as e:  # noqa: BLE001
        logger.warning("Could not prepare writable cookies at %s: %s", target, e)
        # Fall back to the original file if we at least have one.
        if source is not None and source.is_file():
            return source
        return None


def _resolve_configured_cookie_file() -> Path | None:
    if YTDLP_COOKIES_CONTENT and YTDLP_COOKIES_CONTENT.strip():
        return _writable_cookie_path(content=YTDLP_COOKIES_CONTENT)

    if YTDLP_COOKIES_FILE:
        raw = YTDLP_COOKIES_FILE.strip().strip('"').strip("'")
        p = Path(raw)
        if not p.is_absolute():
            p = BACKEND_DIR / p
        if not p.is_file():
            logger.warning(
                "YTDLP_COOKIES_FILE is not a readable file: %s. "
                "Continuing without that cookie file.",
                p,
            )
            return None
        return _writable_cookie_path(source=p)

    # Sensible local default if the repo cookies file exists.
    default = BACKEND_DIR / "cookies" / "youtube.txt"
    if default.is_file():
        return _writable_cookie_path(source=default)
    return None


def _browser_profile_dirs(browser: str) -> list[Path]:
    """Likely cookie-profile roots for a browser name (best-effort, OS-specific)."""
    home = Path.home()
    name = browser.strip().lower()
    # Normalize common aliases yt-dlp accepts.
    if name in ("chrome", "chrome-beta", "chrome-canary", "chrome-dev"):
        return [
            home / "Library" / "Application Support" / "Google" / "Chrome",
            home / ".config" / "google-chrome",
            home / ".config" / "google-chrome-beta",
        ]
    if name in ("chromium", "chromium-browser"):
        return [
            home / "Library" / "Application Support" / "Chromium",
            home / ".config" / "chromium",
        ]
    if name in ("edge", "msedge"):
        return [
            home / "Library" / "Application Support" / "Microsoft Edge",
            home / ".config" / "microsoft-edge",
        ]
    if name == "firefox":
        return [
            home / "Library" / "Application Support" / "Firefox",
            home / ".mozilla" / "firefox",
        ]
    if name == "brave":
        return [
            home / "Library" / "Application Support" / "BraveSoftware" / "Brave-Browser",
            home / ".config" / "BraveSoftware" / "Brave-Browser",
        ]
    if name == "opera":
        return [
            home / "Library" / "Application Support" / "com.operasoftware.Opera",
            home / ".config" / "opera",
        ]
    if name == "safari":
        return [home / "Library" / "Cookies"]
    return []


def _browser_cookies_available(browser: str) -> bool:
    """True when a local browser profile dir exists (never true on bare Docker/Render)."""
    dirs = _browser_profile_dirs(browser)
    if not dirs:
        # Unknown browser name — let yt-dlp try; failure is still handled as retryable.
        return True
    return any(p.is_dir() for p in dirs)


def _browser_cookie_options() -> dict[str, Any] | None:
    if not YTDLP_COOKIES_FROM_BROWSER:
        return None
    spec = YTDLP_COOKIES_FROM_BROWSER.strip()
    if ":" in spec:
        browser, profile = spec.split(":", 1)
        browser = browser.strip().lower()
        profile = profile.strip() or None
        if not browser:
            return None
        if not _browser_cookies_available(browser):
            logger.warning(
                "YTDLP_COOKIES_FROM_BROWSER=%s but no local %s profile was found "
                "(expected under %s). Skipping browser cookies — use YTDLP_COOKIES_CONTENT "
                "on servers/Docker.",
                YTDLP_COOKIES_FROM_BROWSER,
                browser,
                Path.home(),
            )
            return None
        return {"cookiesfrombrowser": (browser, profile) if profile else (browser,)}

    browser = spec.lower()
    if not browser:
        return None
    if not _browser_cookies_available(browser):
        logger.warning(
            "YTDLP_COOKIES_FROM_BROWSER=%s but no local %s profile was found "
            "(expected under %s). Skipping browser cookies — use YTDLP_COOKIES_CONTENT "
            "on servers/Docker.",
            YTDLP_COOKIES_FROM_BROWSER,
            browser,
            Path.home(),
        )
        return None
    return {"cookiesfrombrowser": (browser,)}


def _yt_dlp_cookie_options() -> dict[str, Any]:
    """Best single cookie source (file preferred over browser) for simple callers."""
    cookie_file = _resolve_configured_cookie_file()
    if cookie_file is not None:
        return {"cookiefile": str(cookie_file.resolve())}
    browser = _browser_cookie_options()
    return browser or {}


def cookies_configured() -> bool:
    """True when any cookie source is available for YouTube hardening."""
    return bool(_yt_dlp_cookie_options())


def _is_youtube_url(url: str) -> bool:
    u = url.lower()
    return "youtube.com" in u or "youtu.be" in u


def _configured_player_clients() -> list[str] | None:
    spec = (YTDLP_YOUTUBE_PLAYER_CLIENTS or "").strip()
    low = spec.lower()
    if low in ("off", "false", "0", "no"):
        return []
    if not spec:
        return None
    return [c.strip() for c in spec.split(",") if c.strip()]


def _youtube_extractor_args(url: str, clients: list[str] | None = None) -> dict[str, Any]:
    """Build extractor_args for a specific player_client list."""
    if not _is_youtube_url(url):
        return {}
    if clients is not None:
        use = clients
    else:
        configured = _configured_player_clients()
        if configured is not None:
            use = configured
        else:
            # Cookie-friendly defaults when a single-shot call is made.
            use = ["web", "mweb", "android", "tv_embedded"]
    if not use:
        return {}
    return {"extractor_args": {"youtube": {"player_client": use}}}


def _youtube_attempt_plans() -> list[tuple[dict[str, Any], list[str]]]:
    """
    Ordered (cookie_opts, player_clients) attempts for YouTube.

    Public metadata often works with android/ios *without* cookies. Cookie-based
    clients (web/mweb/tv) are tried afterward. Mixing cookie-incompatible clients
    with cookies in one shot is a common cause of persistent bot errors.
    """
    configured = _configured_player_clients()
    cookie_file = _resolve_configured_cookie_file()
    browser = _browser_cookie_options()

    plans: list[tuple[dict[str, Any], list[str]]] = []

    if configured is not None:
        # Operator override: honor their client list, still try cookie-less then with cookies.
        if configured:
            plans.append(({}, configured))
            if cookie_file is not None:
                plans.append(({"cookiefile": str(cookie_file.resolve())}, configured))
            if browser is not None:
                plans.append((browser, configured))
        return plans

    # 1) No cookies — mobile/TV clients frequently bypass bot walls for public videos.
    for clients in (["android"], ["ios"], ["tv_embedded"], ["android", "ios"]):
        plans.append(({}, clients))

    # 2) Cookie file + clients that actually honor cookies.
    if cookie_file is not None:
        cookie_opts = {"cookiefile": str(cookie_file.resolve())}
        for clients in (["web", "mweb"], ["tv", "tv_embedded"], ["web"]):
            plans.append((cookie_opts, clients))

    # 3) Browser cookies (local only; useless on Render).
    if browser is not None:
        for clients in (["web", "mweb"], ["web"]):
            plans.append((browser, clients))

    return plans


def iter_ytdlp_option_sets(url: str, base: dict[str, Any]) -> Iterator[dict[str, Any]]:
    """Yield yt-dlp option dicts to try for this URL (YouTube gets multi-attempt plans)."""
    if not _is_youtube_url(url):
        opts = dict(base)
        opts.update(_yt_dlp_cookie_options())
        yield opts
        return

    seen: set[str] = set()
    for cookie_opts, clients in _youtube_attempt_plans():
        opts = dict(base)
        opts.update(cookie_opts)
        opts.update(_youtube_extractor_args(url, clients))
        key = f"{sorted(cookie_opts.items())}|{clients}"
        if key in seen:
            continue
        seen.add(key)
        yield opts


@dataclass
class VideoContext:
    title: str
    description: str
    transcript: str
    thumbnail_url: str | None = None

    def as_prompt_block(self) -> str:
        parts: list[str] = []
        if self.title.strip():
            parts.append(f"Video title:\n{self.title.strip()}")
        if self.description.strip():
            parts.append(f"Video description / caption text:\n{self.description.strip()}")
        if self.transcript.strip():
            parts.append(f"Transcript / subtitles (may be auto-generated):\n{self.transcript.strip()}")
        return "\n\n---\n\n".join(parts)


def _http_get(url: str, *, cookiejar: http.cookiejar.CookieJar | None = None, timeout: int = 45) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": _SUB_UA})
    if cookiejar is not None:
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookiejar))
        with opener.open(req, timeout=timeout) as resp:
            raw = resp.read()
    else:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
    return raw.decode("utf-8", errors="replace")


def _vtt_to_plain(vtt: str) -> str:
    lines_out: list[str] = []
    for line in vtt.splitlines():
        s = line.strip()
        if not s or s.startswith("WEBVTT") or "-->" in s or s.isdigit():
            continue
        s = re.sub(r"<[^>]+>", "", s)
        s = s.strip()
        if s:
            lines_out.append(s)
    return "\n".join(lines_out)


def _pick_subtitle_formats(lang_entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    preferred_ext = ("vtt", "srv3", "srv2", "srv1", "json3", "ttml")
    sorted_entries = sorted(
        lang_entries,
        key=lambda e: preferred_ext.index(e.get("ext", ""))
        if e.get("ext") in preferred_ext
        else len(preferred_ext),
    )
    return sorted_entries


def _merge_caption_maps(info: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for source in (info.get("subtitles") or {}, info.get("automatic_captions") or {}):
        for lang, entries in source.items():
            if not entries:
                continue
            out.setdefault(lang, []).extend(entries)
    return out


def _lang_priority(caps: dict[str, list[dict[str, Any]]]) -> list[str]:
    langs = list(caps.keys())
    en_first = [x for x in langs if x == "en" or x.startswith("en-") or x.endswith(".en")]
    rest = [x for x in langs if x not in en_first]
    return sorted(en_first) + sorted(rest)


def _download_best_transcript(
    info: dict[str, Any],
    *,
    cookiejar: http.cookiejar.CookieJar | None = None,
) -> str:
    caps = _merge_caption_maps(info)
    if not caps:
        return ""

    for lang in _lang_priority(caps):
        entries = _pick_subtitle_formats(caps[lang])
        for ent in entries:
            url = ent.get("url")
            if not url:
                continue
            ext = str(ent.get("ext") or "")
            try:
                raw = _http_get(str(url), cookiejar=cookiejar)
            except (urllib.error.URLError, TimeoutError, OSError):
                continue
            if ext == "vtt" or "WEBVTT" in raw[:20].upper():
                plain = _vtt_to_plain(raw)
            else:
                plain = raw
            plain = plain.strip()
            if plain:
                return plain
    return ""


def _clean_ytdlp_error(raw: str) -> str:
    """Strip ANSI / ERROR: prefixes so API clients show a readable message."""
    msg = _ANSI_RE.sub("", raw).strip()
    msg = re.sub(r"^(ERROR:\s*)+", "", msg, flags=re.IGNORECASE).strip()
    # Collapse noisy yt-dlp wiki tails for UI; keep the first sentence-ish chunk.
    if "See  https://github.com/yt-dlp" in msg or "See https://github.com/yt-dlp" in msg:
        msg = re.split(r"\s+See\s+https://github\.com/yt-dlp", msg, maxsplit=1)[0].strip()
    return msg or "Video extraction failed."


def _user_facing_ytdlp_error(raw: str) -> str:
    msg = _clean_ytdlp_error(raw)
    low = msg.lower()
    if "private video" in low:
        return "This video is private. Use a public video link, or add the recipe by hand."
    if "could not find" in low and "cookies database" in low:
        return (
            "YouTube import isn’t configured for this server yet. "
            "Try another public link, or add the recipe by hand."
        )
    if "sign in to confirm" in low or "not a bot" in low:
        return (
            "YouTube temporarily blocked this import. "
            "Try another public link, wait a moment, or add the recipe by hand."
        )
    if "ip address is blocked" in low:
        return (
            "This video couldn’t be reached from our servers. "
            "Try a different link or add the recipe by hand."
        )
    if "age" in low and ("sign in" in low or "restricted" in low):
        return "This video is age-restricted and couldn’t be imported. Try another link or add it by hand."
    # Never leak host paths like /root/.config/google-chrome to clients.
    if "/.config/" in msg or "/library/application support/" in low or "cookies database" in low:
        return (
            "YouTube temporarily blocked this import. "
            "Try another public link, wait a moment, or add the recipe by hand."
        )
    return msg


def _is_retryable_youtube_error(raw: str) -> bool:
    low = _clean_ytdlp_error(raw).lower()
    return any(
        token in low
        for token in (
            "sign in to confirm",
            "not a bot",
            "login required",
            "confirm your age",
            "age-restricted",
            "cookies",
            "cookies database",
            "http error 403",
            "http error 429",
            "unable to download api page",
            "requested format is not available",
        )
    )


def _extract_info_once(url: str, opts: dict[str, Any]) -> tuple[dict[str, Any], http.cookiejar.CookieJar | None]:
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)
        cookiejar = getattr(ydl, "cookiejar", None)
    if not isinstance(info, dict):
        raise ValueError("We couldn’t read that video. Try another link or add the recipe by hand.")
    return info, cookiejar


def fetch_video_context(url: str) -> VideoContext:
    base_opts: dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "nocheckcertificate": False,
        "socket_timeout": 30,
        "retries": 2,
        "fragment_retries": 2,
    }

    last_error: Exception | None = None
    info: dict[str, Any] | None = None
    cookiejar: http.cookiejar.CookieJar | None = None

    for opts in iter_ytdlp_option_sets(url, base_opts):
        try:
            info, cookiejar = _extract_info_once(url, opts)
            break
        except yt_dlp.utils.DownloadError as e:
            last_error = e
            if _is_youtube_url(url) and _is_retryable_youtube_error(str(e)):
                logger.info("YouTube extract attempt failed (%s); trying next strategy", _clean_ytdlp_error(str(e))[:120])
                continue
            raise ValueError(_user_facing_ytdlp_error(str(e))) from e
        except OSError as e:
            # Disk-full while refreshing cookie jars, etc.
            last_error = e
            logger.warning("YouTube extract OS error: %s", e)
            if _is_youtube_url(url):
                continue
            raise ValueError("We couldn’t read that video right now. Please try again.") from e

    if info is None:
        if last_error is not None:
            raise ValueError(_user_facing_ytdlp_error(str(last_error))) from last_error
        raise ValueError("We couldn’t read that video. Try another link or add the recipe by hand.")

    title = str(info.get("title") or "").strip()
    description = str(info.get("description") or info.get("alt_title") or "").strip()
    transcript = _download_best_transcript(info, cookiejar=cookiejar).strip()
    thumbnail_url = pick_best_thumbnail(info)

    if len(transcript) > MAX_TRANSCRIPT_CHARS:
        transcript = transcript[:MAX_TRANSCRIPT_CHARS] + "\n\n[…truncated…]"

    return VideoContext(title=title, description=description, transcript=transcript, thumbnail_url=thumbnail_url)
