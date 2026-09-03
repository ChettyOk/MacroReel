from app.youtube_meta import extract_youtube_video_id, fetch_youtube_metadata_fallback


def test_extract_youtube_video_id_shapes():
    assert extract_youtube_video_id("https://www.youtube.com/watch?v=jNQXAC9IVRw") == "jNQXAC9IVRw"
    assert extract_youtube_video_id("https://youtu.be/jNQXAC9IVRw") == "jNQXAC9IVRw"
    assert extract_youtube_video_id("https://www.youtube.com/shorts/jNQXAC9IVRw") == "jNQXAC9IVRw"
    assert extract_youtube_video_id("https://www.youtube.com/embed/jNQXAC9IVRw") == "jNQXAC9IVRw"
    assert extract_youtube_video_id("https://example.com/watch?v=nope") is None


def test_fallback_uses_innertube(monkeypatch):
    monkeypatch.setattr(
        "app.youtube_meta.fetch_innertube_android",
        lambda _vid, max_transcript_chars=18_000: {
            "title": "High protein pasta",
            "description": "Macros: 520cal, 45g P, 40g C, 12g F\n1. Boil pasta",
            "transcript": "add the chicken",
            "thumbnail_url": "https://i.ytimg.com/vi/abc/hqdefault.jpg",
            "source": "innertube_android",
        },
    )
    monkeypatch.setattr("app.youtube_meta.fetch_youtube_data_api", lambda _vid: None)
    monkeypatch.setattr("app.youtube_meta.fetch_oembed", lambda _url: None)

    meta = fetch_youtube_metadata_fallback("https://www.youtube.com/watch?v=jNQXAC9IVRw")
    assert meta is not None
    assert meta["title"] == "High protein pasta"
    assert "520cal" in meta["description"]
    assert meta["transcript"] == "add the chicken"
    assert "innertube" in meta["source"]


def test_fetch_video_context_falls_back_when_ytdlp_blocked(monkeypatch):
    import yt_dlp

    from app.video_context import fetch_video_context

    def boom(*_a, **_k):  # noqa: ANN002, ANN003
        raise yt_dlp.utils.DownloadError("ERROR: Sign in to confirm you’re not a bot")

    monkeypatch.setattr("app.video_context._extract_info_once", boom)
    monkeypatch.setattr(
        "app.video_context.fetch_youtube_metadata_fallback",
        lambda _url, max_transcript_chars=18_000: {
            "title": "Meal prep chili",
            "description": "Macros: 410cal, 38g P, 28g C, 14g F",
            "transcript": "brown the beef then add beans",
            "thumbnail_url": "https://i.ytimg.com/vi/xyz/hqdefault.jpg",
            "source": "innertube_android",
        },
    )

    ctx = fetch_video_context("https://www.youtube.com/watch?v=jNQXAC9IVRw")
    assert ctx.title == "Meal prep chili"
    assert "410cal" in ctx.description
    assert "brown the beef" in ctx.transcript
