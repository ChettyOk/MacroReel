"""Download a video (yt-dlp) and extract audio + key frames (ffmpeg) for the media pipeline."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import yt_dlp

from app.config import FFMPEG_BIN, FFPROBE_BIN, MAX_VIDEO_SECONDS
from app.video_context import _yt_dlp_cookie_options, _youtube_extractor_args


class MediaError(RuntimeError):
    pass


def download_video(url: str, workdir: Path) -> Path:
    """Download the smallest reasonable video file into workdir; returns the file path."""
    outtmpl = str(workdir / "video.%(ext)s")
    opts: dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "outtmpl": outtmpl,
        # Prefer a compact progressive mp4 to keep downloads small and ffmpeg-friendly.
        "format": "mp4/best[ext=mp4]/best",
        "socket_timeout": 30,
    }
    opts.update(_yt_dlp_cookie_options())
    opts.update(_youtube_extractor_args(url))

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            duration = float(info.get("duration") or 0) if isinstance(info, dict) else 0
            if MAX_VIDEO_SECONDS and duration and duration > MAX_VIDEO_SECONDS:
                raise MediaError(
                    f"Video is {int(duration)}s, longer than MAX_VIDEO_SECONDS={MAX_VIDEO_SECONDS}."
                )
    except yt_dlp.utils.DownloadError as e:
        from app.video_context import _clean_ytdlp_error

        raise MediaError(_clean_ytdlp_error(str(e))) from e

    files = sorted(workdir.glob("video.*"))
    if not files:
        raise MediaError("Download produced no file.")
    return files[0]


def probe_duration(video_path: Path) -> float:
    try:
        out = subprocess.run(
            [
                FFPROBE_BIN,
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(video_path),
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )
        return float(out.stdout.strip() or 0)
    except (subprocess.SubprocessError, ValueError, OSError):
        return 0.0


def extract_audio(video_path: Path, workdir: Path) -> Path | None:
    """Extract a mono 16kHz mp3 audio track. Returns None if there is no audio / on failure."""
    audio_path = workdir / "audio.mp3"
    try:
        subprocess.run(
            [
                FFMPEG_BIN,
                "-y",
                "-i",
                str(video_path),
                "-vn",
                "-ac",
                "1",
                "-ar",
                "16000",
                "-b:a",
                "64k",
                str(audio_path),
            ],
            capture_output=True,
            text=True,
            timeout=180,
            check=True,
        )
    except (subprocess.SubprocessError, OSError):
        return None
    return audio_path if audio_path.is_file() and audio_path.stat().st_size > 0 else None


def extract_frames(video_path: Path, workdir: Path, *, interval_sec: int, max_frames: int) -> list[Path]:
    """Sample one frame every interval_sec seconds, capped at max_frames."""
    fps = 1.0 / max(interval_sec, 1)
    pattern = str(workdir / "frame_%03d.jpg")
    try:
        subprocess.run(
            [
                FFMPEG_BIN,
                "-y",
                "-i",
                str(video_path),
                "-vf",
                f"fps={fps},scale=640:-1",
                "-frames:v",
                str(max_frames),
                "-q:v",
                "4",
                pattern,
            ],
            capture_output=True,
            text=True,
            timeout=180,
            check=True,
        )
    except (subprocess.SubprocessError, OSError):
        return []
    return sorted(workdir.glob("frame_*.jpg"))[:max_frames]
