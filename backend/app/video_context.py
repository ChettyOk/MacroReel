"""Fetch title, description, and caption text from supported video URLs via yt-dlp."""

from __future__ import annotations

import base64
import binascii
import http.cookiejar
import logging
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

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


def _cookies_file_from_content() -> Path | None:
    """Materialize YTDLP_COOKIES_CONTENT to a file on the persistent disk."""
    text = _normalize_cookies_text(YTDLP_COOKIES_CONTENT)
    if not text:
        return None
    target = DATA_DIR / "yt-dlp-cookies.txt"
    try:
        target.write_text(text, encoding="utf-8")
        return target
    except OSError as e:  # noqa: BLE001
        logger.warning("Could not write YTDLP_COOKIES_CONTENT to %s: %s", target, e)
        return None


def _yt_dlp_cookie_options() -> dict[str, Any]:
    """Optional cookies so YouTube and other sites accept yt-dlp (bot / sign-in walls)."""
    extra: dict[str, Any] = {}

    content_file = _cookies_file_from_content()
    if content_file is not None:
        extra["cookiefile"] = str(content_file.resolve())
        return extra

    if YTDLP_COOKIES_FILE:
        raw = YTDLP_COOKIES_FILE.strip().strip('"').strip("'")
        p = Path(raw)
        if not p.is_absolute():
            p = BACKEND_DIR / p
        if not p.is_file():
            # Don't hard-fail the whole import (e.g. TikTok/IG don't need cookies).
            # Warn so YouTube bot walls surface a clear, actionable message instead.
            logger.warning(
                "YTDLP_COOKIES_FILE is not a readable file: %s. "
                "Continuing without cookies. Paste cookies via YTDLP_COOKIES_CONTENT "
                "or set YTDLP_COOKIES_FROM_BROWSER to fix YouTube bot checks.",
                p,
            )
            return extra
        extra["cookiefile"] = str(p.resolve())
        return extra

    if YTDLP_COOKIES_FROM_BROWSER:
        spec = YTDLP_COOKIES_FROM_BROWSER.strip()
        if ":" in spec:
            browser, profile = spec.split(":", 1)
            browser = browser.strip().lower()
            profile = profile.strip() or None
            if not browser:
                raise ValueError("YTDLP_COOKIES_FROM_BROWSER: missing browser name before ':'")
            extra["cookiesfrombrowser"] = (browser, profile) if profile else (browser,)
        else:
            extra["cookiesfrombrowser"] = (spec.lower(),)
        return extra

    return extra


def _is_youtube_url(url: str) -> bool:
    u = url.lower()
    return "youtube.com" in u or "youtu.be" in u


def _youtube_extractor_args(url: str) -> dict[str, Any]:
    """Rotate YouTube player clients; the default web client often fails even with valid cookies."""
    if not _is_youtube_url(url):
        return {}
    spec = (YTDLP_YOUTUBE_PLAYER_CLIENTS or "").strip()
    low = spec.lower()
    if low in ("off", "false", "0", "no"):
        return {}
    if spec:
        clients = [c.strip() for c in spec.split(",") if c.strip()]
    else:
        clients = ["android", "web", "ios", "mweb", "tv_embedded"]
    if not clients:
        return {}
    return {"extractor_args": {"youtube": {"player_client": clients}}}


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


_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def _clean_ytdlp_error(raw: str) -> str:
    """Strip ANSI / ERROR: prefixes so API clients show a readable message."""
    msg = _ANSI_RE.sub("", raw).strip()
    msg = re.sub(r"^(ERROR:\s*)+", "", msg, flags=re.IGNORECASE).strip()
    # Collapse noisy yt-dlp wiki tails for UI; keep the first sentence-ish chunk.
    if "See  https://github.com/yt-dlp" in msg or "See https://github.com/yt-dlp" in msg:
        msg = re.split(r"\s+See\s+https://github\.com/yt-dlp", msg, maxsplit=1)[0].strip()
    return msg or "Video extraction failed."


def fetch_video_context(url: str) -> VideoContext:
    opts: dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "nocheckcertificate": False,
        "socket_timeout": 30,
    }
    opts.update(_yt_dlp_cookie_options())
    opts.update(_youtube_extractor_args(url))

    cookiejar: http.cookiejar.CookieJar | None = None
    with yt_dlp.YoutubeDL(opts) as ydl:
        try:
            info = ydl.extract_info(url, download=False)
        except yt_dlp.utils.DownloadError as e:
            msg = _clean_ytdlp_error(str(e))
            low = msg.lower()
            if "private video" in low:
                msg = "This video is private. Use a public video link, or add cookies for an account that can view it."
            elif "sign in to confirm" in low or "not a bot" in low:
                if not YTDLP_COOKIES_FILE and not YTDLP_COOKIES_FROM_BROWSER:
                    msg += (
                        " Fix: set YTDLP_COOKIES_FILE (cookies.txt) or YTDLP_COOKIES_FROM_BROWSER (e.g. chrome) "
                        "in backend/.env — see https://github.com/yt-dlp/yt-dlp/wiki/FAQ#how-do-i-pass-cookies-to-yt-dlp"
                    )
                else:
                    msg += (
                        " Cookies are set but YouTube still blocked: export a fresh cookies.txt while logged in, "
                        "upgrade yt-dlp (`pip install -U yt-dlp`), try YTDLP_COOKIES_FROM_BROWSER=chrome, or read "
                        "https://github.com/yt-dlp/yt-dlp/wiki/Extractors#exporting-youtube-cookies (account / PO token)."
                    )
            raise ValueError(msg) from e
        cookiejar = getattr(ydl, "cookiejar", None)

    if not isinstance(info, dict):
        raise ValueError("Unexpected response from video extractor")

    title = str(info.get("title") or "").strip()
    description = str(info.get("description") or info.get("alt_title") or "").strip()
    transcript = _download_best_transcript(info, cookiejar=cookiejar).strip()
    thumbnail_url = pick_best_thumbnail(info)

    if len(transcript) > MAX_TRANSCRIPT_CHARS:
        transcript = transcript[:MAX_TRANSCRIPT_CHARS] + "\n\n[…truncated…]"

    return VideoContext(title=title, description=description, transcript=transcript, thumbnail_url=thumbnail_url)
