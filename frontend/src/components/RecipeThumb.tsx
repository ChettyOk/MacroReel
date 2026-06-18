import { useEffect, useMemo, useState } from "react";
import { fetchRecipeThumbnailObjectUrl } from "../api";
import { platformLabel, resolveThumbnailUrl, titleHue } from "../lib/thumbnail";

export type RecipeThumbProps = {
  title: string;
  recipeId?: number;
  thumbnailUrl?: string | null;
  sourceUrl?: string | null;
  sourcePlatform?: string | null;
  calories?: number | null;
  proteinG?: number | null;
  variant?: "card" | "hero";
};

export function RecipeThumb({
  title,
  recipeId,
  thumbnailUrl,
  sourceUrl,
  sourcePlatform,
  calories,
  proteinG,
  variant = "card",
}: RecipeThumbProps) {
  const publicSrc = useMemo(
    () => (recipeId != null ? null : resolveThumbnailUrl(thumbnailUrl, sourceUrl)),
    [recipeId, thumbnailUrl, sourceUrl],
  );
  const [authSrc, setAuthSrc] = useState<string | null>(null);
  const [imgFailed, setImgFailed] = useState(false);

  useEffect(() => {
    setImgFailed(false);
    if (recipeId == null) {
      setAuthSrc(null);
      return;
    }
    let cancelled = false;
    let objectUrl: string | null = null;
    void fetchRecipeThumbnailObjectUrl(recipeId).then((url) => {
      if (cancelled) {
        if (url) URL.revokeObjectURL(url);
        return;
      }
      objectUrl = url;
      setAuthSrc(url);
    });
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [recipeId]);

  const src = recipeId != null ? authSrc : publicSrc;
  const showImage = Boolean(src && !imgFailed);
  const hue = titleHue(title || "recipe");
  const initial = (title.trim()[0] || "R").toUpperCase();
  const platform = platformLabel(sourcePlatform);
  const kcal = calories != null && Number.isFinite(calories) ? Math.round(calories) : null;

  const fallbackBg = `linear-gradient(145deg, hsl(${hue} 38% 14%) 0%, hsl(${hue} 52% 26%) 48%, #0d0d0d 100%)`;

  return (
    <div
      className={`recipe-thumb recipe-thumb--${variant}${showImage ? "" : " recipe-thumb--fallback"}`}
      style={showImage ? undefined : { background: fallbackBg }}
      aria-hidden
    >
      {showImage ? (
        <img
          className="recipe-thumb__img"
          src={src!}
          alt=""
          loading="lazy"
          decoding="async"
          referrerPolicy="no-referrer"
          onError={() => setImgFailed(true)}
        />
      ) : (
        <>
          <span className="recipe-thumb__initial">{initial}</span>
          <span className="recipe-thumb__glow" aria-hidden />
        </>
      )}
      <div className="recipe-thumb__overlay" />
      {platform ? <span className="recipe-thumb__platform">{platform}</span> : null}
      {kcal != null ? (
        <span className="recipe-thumb__kcal">
          <strong>{kcal}</strong> kcal
        </span>
      ) : proteinG != null && proteinG >= 15 ? (
        <span className="recipe-thumb__kcal">
          <strong>{Math.round(proteinG)}g</strong> protein
        </span>
      ) : null}
    </div>
  );
}
