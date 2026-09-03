"""End-to-end extraction pipeline: URL -> recipe draft.

Stages (each degrades gracefully):
  ingest -> context (captions/description) -> [media: download, audio->transcribe, frames->OCR]
  -> combine -> LLM structure (Gemini) or heuristic fallback.
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from app import config
from app.gemini_extract import GeminiUpstreamError, structure_recipe
from app.heuristic_recipe import draft_from_text
from app.schemas import NutritionReport, RecipeBase
from app.video_context import VideoContext, fetch_video_context
from app.video_urls import detect_platform, normalize_video_url, validate_video_url


@dataclass
class PipelineResult:
    draft: RecipeBase
    platform: str
    thumbnail_url: str | None = None
    source_video_title: str | None = None
    had_description: bool = False
    had_transcript: bool = False  # captions/subtitles from the page
    had_audio_transcription: bool = False  # Gemini audio transcription
    had_frame_vision: bool = False  # Gemini frame OCR
    used_ai: bool = False
    steps_log: list[str] = field(default_factory=list)
    note: str | None = None
    source_context_text: str | None = None  # description/caption for stated-macro parsing
    stated_nutrition: NutritionReport | None = None


def _combine_context(
    ctx: VideoContext,
    audio_transcript: str,
    onscreen_text: str,
) -> str:
    """Order blocks so Gemini sees caption ingredients and spoken/on-screen steps clearly."""
    parts: list[str] = []
    if ctx.title.strip():
        parts.append(f"Video title:\n{ctx.title.strip()}")
    if ctx.description.strip():
        parts.append(
            "Description / caption (prefer this for ingredient lists and stated macros):\n"
            f"{ctx.description.strip()}"
        )
    if onscreen_text.strip():
        parts.append(
            "On-screen text from video frames (prefer for ingredient cards / macro overlays):\n"
            f"{onscreen_text.strip()}"
        )
    if audio_transcript.strip():
        parts.append(
            "Audio transcript (spoken instructions — prefer for steps):\n"
            f"{audio_transcript.strip()}"
        )
    if ctx.transcript.strip():
        parts.append(
            "Subtitles/captions from the page (prefer for steps when no audio transcript):\n"
            f"{ctx.transcript.strip()}"
        )
    return "\n\n---\n\n".join(parts)


def _run_media_stage(url: str, result: PipelineResult) -> tuple[str, str]:
    """Download + ffmpeg + Gemini transcribe/OCR. Returns (audio_transcript, onscreen_text)."""
    from app import gemini_media, media  # local import: heavy/optional deps

    audio_transcript = ""
    onscreen_text = ""

    with tempfile.TemporaryDirectory(prefix="macroreel_") as tmp:
        workdir = Path(tmp)
        try:
            video_path = media.download_video(url, workdir)
            result.steps_log.append("downloaded video")
        except media.MediaError as e:
            result.steps_log.append(f"media download skipped: {e}")
            return "", ""

        if config.ENABLE_TRANSCRIPTION:
            audio_path = media.extract_audio(video_path, workdir)
            if audio_path is not None:
                audio_transcript = gemini_media.transcribe_audio(audio_path)
                if audio_transcript.strip():
                    result.had_audio_transcription = True
                    result.steps_log.append("transcribed audio (Gemini)")
                else:
                    result.steps_log.append("audio transcription empty")
            else:
                result.steps_log.append("no audio track")

        if config.ENABLE_FRAME_VISION:
            frames = media.extract_frames(
                video_path,
                workdir,
                interval_sec=config.FRAME_INTERVAL_SEC,
                max_frames=config.MAX_FRAMES,
            )
            if frames:
                onscreen_text = gemini_media.read_frames_text(frames)
                if onscreen_text.strip():
                    result.had_frame_vision = True
                    result.steps_log.append(f"read on-screen text from {len(frames)} frames (Gemini)")
                else:
                    result.steps_log.append("frame OCR empty")
            else:
                result.steps_log.append("frame extraction produced no frames")

    return audio_transcript, onscreen_text


def run_pipeline(url: str, *, use_ai: bool, use_media: bool | None) -> PipelineResult:
    url = validate_video_url(url)
    platform = detect_platform(url)
    result = PipelineResult(draft=RecipeBase(title="Imported recipe"), platform=platform)

    # 1) Context from the page (title, description, captions) — always attempted.
    ctx = fetch_video_context(url)  # may raise ValueError -> handled by caller
    result.source_video_title = ctx.title or None
    result.thumbnail_url = ctx.thumbnail_url
    result.had_description = bool(ctx.description.strip())
    result.had_transcript = bool(ctx.transcript.strip())
    result.steps_log.append("fetched page metadata/captions")

    # 2) Optional media pipeline (download + ffmpeg + Gemini transcribe/OCR).
    # Client use_media=True runs deep extract whenever ffmpeg exists; ENABLE_MEDIA_PIPELINE is the default only.
    want_media = config.ENABLE_MEDIA_PIPELINE if use_media is None else bool(use_media)
    audio_transcript = ""
    onscreen_text = ""
    if want_media:
        if not config.ffmpeg_available():
            result.steps_log.append("media pipeline requested but ffmpeg/ffprobe not found — using captions only")
        else:
            audio_transcript, onscreen_text = _run_media_stage(url, result)
            if not audio_transcript and not onscreen_text and not result.had_transcript:
                result.steps_log.append("deep extract produced no extra text — using captions/description")

    # 3) Combine all available text (title + description + captions + media).
    combined = _combine_context(ctx, audio_transcript, onscreen_text)
    if not combined.strip():
        raise ValueError("No title, description, captions, transcript, or on-screen text found for this URL.")

    # 4) Structure with Gemini, or heuristics.
    # Keep the full combined block for stated-macro parsing (calories in title/captions too).
    result.source_context_text = combined.strip() or None

    if use_ai:
        try:
            outcome = structure_recipe(combined)
            result.draft = outcome.draft
            result.used_ai = True
            result.stated_nutrition = outcome.stated_nutrition
            result.steps_log.append(f"structured with Gemini ({outcome.model_used})")
            if outcome.model_used != config.GEMINI_MODEL:
                result.note = (
                    f"Gemini used model \u201c{outcome.model_used}\u201d "
                    f"(configured \u201c{config.GEMINI_MODEL}\u201d was unavailable)."
                )
        except GeminiUpstreamError as e:
            if e.status_code == 429 and config.GEMINI_FALLBACK_ON_QUOTA:
                result.draft = draft_from_text(ctx.title, combined, transcript=audio_transcript or ctx.transcript)
                result.used_ai = False
                result.note = f"{e} Loaded a heuristic draft instead \u2014 edit below, or retry later."
                result.steps_log.append("Gemini quota hit \u2014 used heuristic fallback")
            else:
                raise
    else:
        result.draft = draft_from_text(ctx.title, combined, transcript=audio_transcript or ctx.transcript)
        result.steps_log.append("structured with heuristics (no AI)")

    if _is_empty_recipe_draft(result.draft):
        raise ValueError(
            "No recipe found in this video’s title, description, or captions. "
            "Try a cooking video with ingredients listed, or enable Deep extract."
        )

    # Warn when we only had thin caption text (common cause of mismatched drafts).
    rich_source = result.had_transcript or result.had_audio_transcription or result.had_frame_vision
    if not rich_source and not result.note:
        result.note = (
            "Imported from the video caption/description only. "
            "Turn on Deeper extract to read spoken steps and on-screen text for a closer match."
        )

    return result


def _is_empty_recipe_draft(draft: RecipeBase) -> bool:
    title = (draft.title or "").strip().lower()
    has_content = bool(draft.ingredients) or bool(draft.steps)
    if has_content:
        return False
    return title in ("", "could not parse recipe", "imported recipe")
