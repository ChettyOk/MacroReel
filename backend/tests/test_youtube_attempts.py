import app.config as config
from app.video_context import (
    _browser_cookie_options,
    _user_facing_ytdlp_error,
    _youtube_attempt_plans,
    iter_ytdlp_option_sets,
)


def test_youtube_plans_try_android_before_cookies(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "YTDLP_COOKIES_CONTENT", "")
    monkeypatch.setattr(config, "YTDLP_COOKIES_FILE", "")
    monkeypatch.setattr(config, "YTDLP_COOKIES_FROM_BROWSER", "")
    monkeypatch.setattr(config, "YTDLP_YOUTUBE_PLAYER_CLIENTS", "")
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr("app.video_context.DATA_DIR", tmp_path)
    monkeypatch.setattr("app.video_context.YTDLP_COOKIES_CONTENT", "")
    monkeypatch.setattr("app.video_context.YTDLP_COOKIES_FILE", "")
    monkeypatch.setattr("app.video_context.YTDLP_COOKIES_FROM_BROWSER", "")
    monkeypatch.setattr("app.video_context.YTDLP_YOUTUBE_PLAYER_CLIENTS", "")

    plans = _youtube_attempt_plans()
    assert plans
    first_cookies, first_clients = plans[0]
    assert first_cookies == {}
    assert first_clients == ["android"]


def test_iter_option_sets_includes_player_client_for_youtube(monkeypatch, tmp_path):
    monkeypatch.setattr("app.video_context.DATA_DIR", tmp_path)
    monkeypatch.setattr("app.video_context.YTDLP_COOKIES_CONTENT", "")
    monkeypatch.setattr("app.video_context.YTDLP_COOKIES_FILE", "")
    monkeypatch.setattr("app.video_context.YTDLP_COOKIES_FROM_BROWSER", "")
    monkeypatch.setattr("app.video_context.YTDLP_YOUTUBE_PLAYER_CLIENTS", "")

    opts_list = list(iter_ytdlp_option_sets("https://www.youtube.com/watch?v=abc123XYZ01", {"quiet": True}))
    assert opts_list
    assert opts_list[0]["extractor_args"]["youtube"]["player_client"] == ["android"]


def test_browser_cookies_skipped_when_profile_missing(monkeypatch, tmp_path):
    """Servers/Docker have no Chrome under ~/.config — must not plan cookiesfrombrowser."""
    monkeypatch.setattr("app.video_context.YTDLP_COOKIES_FROM_BROWSER", "chrome")
    monkeypatch.setattr(
        "app.video_context._browser_profile_dirs",
        lambda _browser: [tmp_path / "missing-chrome-profile"],
    )
    assert _browser_cookie_options() is None

    monkeypatch.setattr("app.video_context.YTDLP_COOKIES_CONTENT", "")
    monkeypatch.setattr("app.video_context.YTDLP_COOKIES_FILE", "")
    monkeypatch.setattr("app.video_context.YTDLP_YOUTUBE_PLAYER_CLIENTS", "")
    monkeypatch.setattr("app.video_context.DATA_DIR", tmp_path)
    plans = _youtube_attempt_plans()
    assert all("cookiesfrombrowser" not in opts for opts, _ in plans)


def test_chrome_cookies_db_error_is_user_friendly():
    msg = _user_facing_ytdlp_error(
        'ERROR: could not find chrome cookies database in "/root/.config/google-chrome"'
    )
    assert "/root/" not in msg
    assert "google-chrome" not in msg.lower()
