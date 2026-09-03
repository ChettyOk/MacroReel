import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import * as api from "../api";
import {
  detectPlatform,
  extractVideoUrlFromText,
  isSupportedVideoUrl,
  normalizeVideoUrl,
  platformDisplayName,
} from "../lib/videoUrl";
import { toUserErrorMessage } from "../lib/userError";

const STAGES = [
  "Fetching video info",
  "Reading ingredients",
  "Calculating macros",
] as const;

const PLATFORMS = [
  { id: "tiktok", label: "TikTok" },
  { id: "youtube", label: "YouTube" },
  { id: "instagram", label: "Instagram" },
  { id: "facebook", label: "Facebook" },
] as const;

export function ImportPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [videoUrl, setVideoUrl] = useState("");
  const [useAi, setUseAi] = useState(true);
  const [useDeepExtract, setUseDeepExtract] = useState(false);
  const [health, setHealth] = useState<api.HealthStatus | null>(null);
  const [extracting, setExtracting] = useState(false);
  const [stageIdx, setStageIdx] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const autoRanRef = useRef(false);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const detected = videoUrl.trim() ? detectPlatform(videoUrl) : null;

  useEffect(() => {
    void api.fetchHealth().then((h) => {
      setHealth(h);
      // Prefer deeper extract when the server can download + transcribe — much closer to the video.
      if (h.media_pipeline) {
        setUseDeepExtract(true);
      }
    }).catch(() => setHealth(null));
  }, []);

  useEffect(() => {
    if (!extracting) return;
    timerRef.current = setInterval(() => {
      setStageIdx((i) => Math.min(i + 1, STAGES.length - 1));
    }, 4000);
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [extracting]);

  async function runExtract(rawUrl: string) {
    const extracted = normalizeVideoUrl(extractVideoUrlFromText(rawUrl) ?? rawUrl.trim());
    if (!extracted) return;
    if (!isSupportedVideoUrl(extracted)) {
      setError("Paste a TikTok, YouTube, Instagram, or Facebook video link.");
      return;
    }
    setVideoUrl(extracted);
    setError(null);
    setExtracting(true);
    setStageIdx(0);
    try {
      const draft = await api.extractRecipeFromVideo(extracted, {
        useAi,
        useMedia: useDeepExtract,
      });
      navigate("/new", { state: { draft, reveal: true, sourceUrl: extracted } });
    } catch (err) {
      setError(toUserErrorMessage(err, "We couldn’t import that video. Please try again."));
    } finally {
      setExtracting(false);
      setStageIdx(0);
    }
  }

  useEffect(() => {
    if (autoRanRef.current) return;
    const shared = [searchParams.get("url"), searchParams.get("text"), searchParams.get("title")].filter(Boolean).join(" ");
    const url = extractVideoUrlFromText(shared);
    if (!url) return;
    autoRanRef.current = true;
    setVideoUrl(url);
    if (searchParams.get("autorun") !== "0") void runExtract(url);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams]);

  if (extracting) {
    return (
      <div className="extract-screen app-shell--full" style={{ maxWidth: 480, margin: "0 auto" }}>
        <div className="extract-pulse" aria-hidden />
        <h1 className="page-title" style={{ fontSize: "1.5rem" }}>Extracting recipe</h1>
        <p className="page-sub" style={{ margin: "0.5rem 0 0" }}>
          {detected === "youtube"
            ? "Reading YouTube title, description, and captions…"
            : "Hang tight — we're reading the video for you."}
        </p>
        {videoUrl ? (
          <p style={{ fontSize: "0.75rem", color: "var(--text-dim)", marginTop: "0.5rem", wordBreak: "break-all" }}>
            {videoUrl.length > 72 ? `${videoUrl.slice(0, 72)}…` : videoUrl}
          </p>
        ) : null}
        <ol className="extract-stages">
          {STAGES.map((label, i) => (
            <li
              key={label}
              className={
                i < stageIdx ? "extract-stages__done" : i === stageIdx ? "extract-stages__active" : undefined
              }
            >
              <span className="extract-stages__icon" aria-hidden>
                {i < stageIdx ? "✓" : i === stageIdx ? "●" : "○"}
              </span>
              {label}
              {i === stageIdx ? <span className="extract-stages__dots" aria-hidden><span /><span /><span /></span> : null}
            </li>
          ))}
        </ol>

        <div className="extract-skeleton card" aria-hidden>
          <div className="extract-skeleton__thumb skeleton skeleton--shimmer" />
          <div className="extract-skeleton__lines">
            <div className="skeleton skeleton--shimmer skeleton--line" />
            <div className="skeleton skeleton--shimmer skeleton--line skeleton--short" />
            <div className="skeleton skeleton--shimmer skeleton--line" style={{ width: "40%" }} />
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="page reveal-up">
      <h1 className="page-title">Import video</h1>
      <p className="page-sub">
        Paste a TikTok, Instagram, YouTube, Shorts, or Facebook cooking link — or add a recipe by hand.
      </p>

      <div className="platform-pills" aria-label="Supported platforms">
        {PLATFORMS.map((p) => (
          <span key={p.id} className={`platform-pill ${detected === p.id ? "platform-pill--on" : ""}`}>
            {p.label}
          </span>
        ))}
      </div>

      {error ? (
        <div className="card" role="alert" style={{ borderColor: "var(--danger-soft-text)", color: "var(--danger-soft-text)", marginBottom: "1rem" }}>
          {error}
        </div>
      ) : null}

      <form
        className="card form-stack"
        style={{ padding: "0.85rem" }}
        onSubmit={(e) => {
          e.preventDefault();
          void runExtract(videoUrl);
        }}
      >
        <label className="field">
          <span className="field__label">Video URL</span>
          <input
            className="input"
            type="text"
            inputMode="url"
            autoComplete="url"
            placeholder="Paste a TikTok, Instagram, YouTube, or Facebook link"
            value={videoUrl}
            onChange={(e) => setVideoUrl(e.target.value)}
            required
            autoFocus
          />
        </label>
        {detected && detected !== "unknown" ? (
          <p style={{ margin: 0, fontSize: "0.8rem", color: "var(--accent)" }}>
            Detected: {platformDisplayName(detected)}
          </p>
        ) : null}
        <label className="check-row">
          <input type="checkbox" checked={useAi} onChange={(e) => setUseAi(e.target.checked)} />
          Use AI to structure the recipe
        </label>
        <label className="check-row">
          <input
            type="checkbox"
            checked={useDeepExtract}
            onChange={(e) => setUseDeepExtract(e.target.checked)}
            disabled={health != null && !health.media_pipeline}
          />
          Deeper extract (read spoken steps and on-screen text — more accurate)
          {health != null && !health.media_pipeline ? (
            <span className="check-row__hint">
              {" "}
              — turn on ENABLE_MEDIA_PIPELINE=true on the server
            </span>
          ) : null}
        </label>
        <button type="submit" className="btn btn--primary btn--block" disabled={!videoUrl.trim()}>
          Extract recipe
        </button>
      </form>

      <div className="import-divider" role="separator">
        <span>or</span>
      </div>

      <Link to="/new" className="btn btn--secondary btn--block" style={{ textAlign: "center", textDecoration: "none" }}>
        Add recipe manually
      </Link>
      <p className="page-sub" style={{ marginTop: "0.65rem", marginBottom: 0, fontSize: "0.82rem" }}>
        No video needed — type title, ingredients, and steps yourself.
      </p>
    </div>
  );
}
