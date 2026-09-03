"""YouTube metadata fallbacks when yt-dlp is blocked (common on datacenter IPs).

Order:
  1) Innertube ANDROID player (title, description, caption tracks)
  2) YouTube Data API v3 (optional YOUTUBE_API_KEY)
  3) oEmbed (title + thumbnail only)
"""

from __future__ import annotations

import json
import logging
import re
import ssl
import urllib.error
import urllib.parse
import urllib.request
from typing import Any
from urllib.parse import parse_qs, urlparse

from app.config import YOUTUBE_API_KEY

logger = logging.getLogger(__name__)

# Public Android client constants used by yt-dlp / YouTube apps.
_ANDROID_CLIENT_NAME = "ANDROID"
_ANDROID_CLIENT_VERSION = "20.10.38"
_ANDROID_UA = f"com.google.android.youtube/{_ANDROID_CLIENT_VERSION} (Linux; U; Android 14) gzip"
_WEB_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

_VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")


def _ssl_context() -> ssl.SSLContext:
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except Exception:  # noqa: BLE001
        return ssl.create_default_context()


def extract_youtube_video_id(url: str) -> str | None:
    """Return the 11-char video id from common YouTube URL shapes, or None."""
    raw = (url or "").strip()
    if not raw:
        return None
    parsed = urlparse(raw if "://" in raw else f"https://{raw}")
    host = (parsed.hostname or "").lower().removeprefix("www.")

    if host == "youtu.be":
        vid = parsed.path.lstrip("/").split("/")[0].split("?")[0]
        return vid if _VIDEO_ID_RE.match(vid) else None

    if host.endswith("youtube.com") or host == "youtube-nocookie.com":
        qs = parse_qs(parsed.query)
        if "v" in qs and qs["v"]:
            vid = qs["v"][0]
            return vid if _VIDEO_ID_RE.match(vid) else None
        parts = [p for p in parsed.path.split("/") if p]
        for marker in ("shorts", "embed", "live", "v"):
            if marker in parts:
                idx = parts.index(marker)
                if idx + 1 < len(parts):
                    vid = parts[idx + 1].split("?")[0]
                    if _VIDEO_ID_RE.match(vid):
                        return vid
    return None


def _http_json(url: str, *, data: dict[str, Any] | None = None, headers: dict[str, str] | None = None, timeout: int = 30) -> dict[str, Any]:
    hdrs = {"Accept": "application/json", **(headers or {})}
    body = None
    if data is not None:
        body = json.dumps(data).encode("utf-8")
        hdrs.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(url, data=body, headers=hdrs, method="POST" if body else "GET")
    with urllib.request.urlopen(req, timeout=timeout, context=_ssl_context()) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError("Unexpected JSON response")
    return parsed


def _http_text(url: str, *, headers: dict[str, str] | None = None, timeout: int = 30) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": _WEB_UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout, context=_ssl_context()) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _vtt_or_xml_to_plain(raw: str) -> str:
    """Best-effort plain text from VTT / timedtext XML / srv3."""
    text = raw.strip()
    if not text:
        return ""
    if "WEBVTT" in text[:40].upper() or "-->" in text:
        lines_out: list[str] = []
        for line in text.splitlines():
            s = line.strip()
            if not s or s.startswith("WEBVTT") or "-->" in s or s.isdigit():
                continue
            s = re.sub(r"<[^>]+>", "", s).strip()
            if s:
                lines_out.append(s)
        return "\n".join(lines_out)

    import html as html_lib

    # timedtext format=3 uses <p>...</p>; older formats use <text>...</text> or text="...".
    nodes = re.findall(r"<p\b[^>]*>(.*?)</p>", text, flags=re.I | re.S)
    if not nodes:
        nodes = re.findall(r"<text[^>]*>(.*?)</text>", text, flags=re.I | re.S)
    if nodes:
        cleaned = [
            html_lib.unescape(re.sub(r"<[^>]+>", "", urllib.parse.unquote_plus(n))).strip()
            for n in nodes
        ]
        return "\n".join(x for x in cleaned if x)

    parts = re.findall(r'text="([^"]*)"', text)
    if parts:
        decoded = [
            html_lib.unescape(urllib.parse.unquote_plus(p.replace("\\n", " "))).strip()
            for p in parts
        ]
        return "\n".join(x for x in decoded if x)
    return ""


def _caption_plain_from_tracks(tracks: list[dict[str, Any]], *, max_chars: int) -> str:
    if not tracks:
        return ""

    def score(t: dict[str, Any]) -> tuple[int, int]:
        lang = str(t.get("languageCode") or "").lower()
        # Prefer manual English, then any English, then others.
        if lang == "en" and not t.get("kind"):
            pri = 0
        elif lang.startswith("en"):
            pri = 1
        else:
            pri = 2
        return (pri, 0 if not t.get("kind") else 1)

    for track in sorted(tracks, key=score):
        base = track.get("baseUrl") or track.get("url")
        if not base:
            continue
        # Prefer plain VTT when available.
        for fmt in ("vtt", "srv3", None):
            try:
                url = str(base)
                if fmt:
                    sep = "&" if "?" in url else "?"
                    url = f"{url}{sep}fmt={fmt}"
                raw = _http_text(url, timeout=25)
                plain = _vtt_or_xml_to_plain(raw).strip()
                if plain:
                    if len(plain) > max_chars:
                        return plain[:max_chars] + "\n\n[…truncated…]"
                    return plain
            except (urllib.error.URLError, TimeoutError, OSError, ValueError):
                continue
    return ""


def fetch_innertube_android(video_id: str, *, max_transcript_chars: int = 18_000) -> dict[str, Any] | None:
    """Fetch title/description/captions via YouTube Innertube ANDROID client."""
    endpoint = "https://www.youtube.com/youtubei/v1/player?prettyPrint=false"
    payload = {
        "context": {
            "client": {
                "clientName": _ANDROID_CLIENT_NAME,
                "clientVersion": _ANDROID_CLIENT_VERSION,
                "androidSdkVersion": 30,
                "hl": "en",
                "gl": "US",
            }
        },
        "videoId": video_id,
        "contentCheckOk": True,
        "racyCheckOk": True,
    }
    try:
        data = _http_json(
            endpoint,
            data=payload,
            headers={
                "User-Agent": _ANDROID_UA,
                "X-YouTube-Client-Name": "3",
                "X-YouTube-Client-Version": _ANDROID_CLIENT_VERSION,
            },
            timeout=30,
        )
    except (urllib.error.URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as e:
        logger.info("Innertube android player failed for %s: %s", video_id, e)
        return None

    status = str(((data.get("playabilityStatus") or {}).get("status") or "")).upper()
    if status and status not in ("OK", "LIVE_STREAM_OFFLINE"):
        reason = (data.get("playabilityStatus") or {}).get("reason") or status
        logger.info("Innertube playability for %s: %s", video_id, reason)
        # Still try videoDetails — sometimes present with LOGIN_REQUIRED for formats only.
    details = data.get("videoDetails") or {}
    title = str(details.get("title") or "").strip()
    description = str(details.get("shortDescription") or "").strip()
    thumbs = ((details.get("thumbnail") or {}).get("thumbnails") or [])
    thumbnail_url = None
    if isinstance(thumbs, list) and thumbs:
        # Prefer largest.
        best = max(thumbs, key=lambda t: int(t.get("width") or 0) * int(t.get("height") or 0))
        thumbnail_url = str(best.get("url") or "") or None

    tracks = (
        ((data.get("captions") or {}).get("playerCaptionsTracklistRenderer") or {}).get("captionTracks")
        or []
    )
    transcript = ""
    if isinstance(tracks, list) and tracks:
        transcript = _caption_plain_from_tracks(tracks, max_chars=max_transcript_chars)

    if not title and not description and not transcript:
        return None
    return {
        "title": title,
        "description": description,
        "transcript": transcript,
        "thumbnail_url": thumbnail_url,
        "source": "innertube_android",
    }


def fetch_youtube_data_api(video_id: str) -> dict[str, Any] | None:
    """Optional Data API v3 snippet (needs YOUTUBE_API_KEY)."""
    key = (YOUTUBE_API_KEY or "").strip()
    if not key:
        return None
    qs = urllib.parse.urlencode(
        {
            "part": "snippet",
            "id": video_id,
            "key": key,
        }
    )
    url = f"https://www.googleapis.com/youtube/v3/videos?{qs}"
    try:
        data = _http_json(url, headers={"User-Agent": _WEB_UA}, timeout=25)
    except (urllib.error.URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as e:
        logger.warning("YouTube Data API failed for %s: %s", video_id, e)
        return None
    items = data.get("items") or []
    if not items:
        return None
    snip = items[0].get("snippet") or {}
    thumbs = snip.get("thumbnails") or {}
    thumb = None
    for name in ("maxres", "standard", "high", "medium", "default"):
        if name in thumbs and thumbs[name].get("url"):
            thumb = str(thumbs[name]["url"])
            break
    title = str(snip.get("title") or "").strip()
    description = str(snip.get("description") or "").strip()
    if not title and not description:
        return None
    return {
        "title": title,
        "description": description,
        "transcript": "",
        "thumbnail_url": thumb,
        "source": "youtube_data_api",
    }


def fetch_oembed(url: str) -> dict[str, Any] | None:
    """Minimal title + thumbnail via oEmbed (no description/captions)."""
    qs = urllib.parse.urlencode({"url": url, "format": "json"})
    endpoint = f"https://www.youtube.com/oembed?{qs}"
    try:
        data = _http_json(endpoint, headers={"User-Agent": _WEB_UA}, timeout=20)
    except (urllib.error.URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as e:
        logger.info("YouTube oEmbed failed: %s", e)
        return None
    title = str(data.get("title") or "").strip()
    thumb = str(data.get("thumbnail_url") or "") or None
    if not title:
        return None
    return {
        "title": title,
        "description": "",
        "transcript": "",
        "thumbnail_url": thumb,
        "source": "oembed",
    }


def fetch_youtube_metadata_fallback(url: str, *, max_transcript_chars: int = 18_000) -> dict[str, Any] | None:
    """
    Aggregate fallbacks when yt-dlp cannot extract.

    Prefers Innertube (description + captions), then Data API, then oEmbed.
    Merges fields so we keep the richest available set.
    """
    video_id = extract_youtube_video_id(url)
    merged: dict[str, Any] = {
        "title": "",
        "description": "",
        "transcript": "",
        "thumbnail_url": None,
        "source": "",
    }
    sources: list[str] = []

    if video_id:
        for fetcher_name, fetcher in (
            ("innertube", lambda: fetch_innertube_android(video_id, max_transcript_chars=max_transcript_chars)),
            ("data_api", lambda: fetch_youtube_data_api(video_id)),
        ):
            try:
                part = fetcher()
            except Exception as e:  # noqa: BLE001
                logger.info("YouTube fallback %s error: %s", fetcher_name, e)
                part = None
            if not part:
                continue
            sources.append(str(part.get("source") or fetcher_name))
            if not merged["title"] and part.get("title"):
                merged["title"] = part["title"]
            if not merged["description"] and part.get("description"):
                merged["description"] = part["description"]
            if not merged["transcript"] and part.get("transcript"):
                merged["transcript"] = part["transcript"]
            if not merged["thumbnail_url"] and part.get("thumbnail_url"):
                merged["thumbnail_url"] = part["thumbnail_url"]

    if not merged["title"] or not merged["thumbnail_url"]:
        try:
            oem = fetch_oembed(url)
        except Exception as e:  # noqa: BLE001
            logger.info("oEmbed fallback error: %s", e)
            oem = None
        if oem:
            sources.append("oembed")
            if not merged["title"]:
                merged["title"] = oem.get("title") or ""
            if not merged["thumbnail_url"]:
                merged["thumbnail_url"] = oem.get("thumbnail_url")

    if not (merged["title"] or merged["description"] or merged["transcript"]):
        return None
    merged["source"] = "+".join(sources) if sources else "fallback"
    return merged
