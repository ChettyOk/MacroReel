from app.video_context import _clean_ytdlp_error


def test_clean_ytdlp_error_strips_ansi_and_wiki_tail():
    raw = (
        "\x1b[0;31mERROR:\x1b[0m [youtube] abc: Private video. Sign in if you've been granted access. "
        "See  https://github.com/yt-dlp/yt-dlp/wiki/FAQ#how-do-i-pass-cookies-to-yt-dlp  for how to manually pass cookies."
    )
    cleaned = _clean_ytdlp_error(raw)
    assert "\x1b" not in cleaned
    assert not cleaned.upper().startswith("ERROR:")
    assert "Private video" in cleaned
    assert "github.com/yt-dlp" not in cleaned
