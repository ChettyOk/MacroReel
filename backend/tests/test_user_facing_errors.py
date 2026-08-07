from app.video_context import _clean_ytdlp_error


def test_clean_ytdlp_error_still_strips_ansi():
    raw = "\x1b[0;31mERROR:\x1b[0m [youtube] abc: Sign in to confirm you’re not a bot."
    cleaned = _clean_ytdlp_error(raw)
    assert "\x1b" not in cleaned
    assert "Sign in to confirm" in cleaned
