"""Normalize and validate supported cooking-video URLs (TikTok, YouTube, Instagram, …)."""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

SUPPORTED_PLATFORMS = ("tiktok", "youtube", "instagram", "facebook")
_PLATFORM_HINT = "Paste a TikTok, YouTube, Instagram, or Facebook video link."


def detect_platform(url: str) -> str:
    host = (urlparse(url).hostname or "").lower().removeprefix("www.")
    if "tiktok" in host:
        return "tiktok"
    if "youtube" in host or host == "youtu.be":
        return "youtube"
    if "instagram" in host:
        return "instagram"
    if "facebook" in host or host == "fb.watch":
        return "facebook"
    return "unknown"


def normalize_video_url(url: str) -> str:
    """Canonicalize common YouTube short links so yt-dlp and thumbnails behave consistently."""
    raw = url.strip()
    if not raw:
        return raw

    parsed = urlparse(raw)
    if not parsed.scheme:
        parsed = urlparse(f"https://{raw}")
    host = (parsed.hostname or "").lower().removeprefix("www.")

    if host == "youtu.be":
        vid = parsed.path.lstrip("/").split("/")[0]
        if vid:
            return f"https://www.youtube.com/watch?v={vid}"

    if host in ("youtube.com", "m.youtube.com", "music.youtube.com"):
        parts = [p for p in parsed.path.split("/") if p]
        if "shorts" in parts:
            idx = parts.index("shorts")
            if idx + 1 < len(parts):
                vid = parts[idx + 1].split("?")[0]
                if vid:
                    return f"https://www.youtube.com/watch?v={vid}"
        if parts and parts[0] == "live" and len(parts) > 1:
            return f"https://www.youtube.com/watch?v={parts[1]}"
        if parts and parts[0] == "embed" and len(parts) > 1:
            return f"https://www.youtube.com/watch?v={parts[1]}"
        if parsed.path == "/watch" or "v" in parse_qs(parsed.query):
            vid = parse_qs(parsed.query).get("v", [None])[0]
            if vid:
                return f"https://www.youtube.com/watch?v={vid}"

    scheme = parsed.scheme or "https"
    netloc = parsed.netloc or parsed.path.split("/")[0]
    path = parsed.path if parsed.netloc else "/" + "/".join(parsed.path.split("/")[1:])
    if not path.startswith("/"):
        path = "/" + path
    return f"{scheme}://{netloc}{path}" + (f"?{parsed.query}" if parsed.query else "")


def validate_video_url(url: str) -> str:
    """Return normalized URL or raise ValueError with a user-facing message."""
    normalized = normalize_video_url(url)
    if not normalized.startswith(("http://", "https://")):
        raise ValueError(f"Invalid URL. {_PLATFORM_HINT}")
    platform = detect_platform(normalized)
    if platform not in SUPPORTED_PLATFORMS:
        raise ValueError(f"Unsupported video host. {_PLATFORM_HINT}")
    return normalized
