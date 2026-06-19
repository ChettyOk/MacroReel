import { Share } from "@capacitor/share";
import type { Recipe } from "../api";
import { isNativeApp } from "./platform";

export type ShareRecipeResult = "shared" | "cancelled" | "unavailable";

function recipeWebUrl(recipeId: number): string {
  const configured = import.meta.env.VITE_WEB_URL?.replace(/\/$/, "");
  if (configured) return `${configured}/recipe/${recipeId}`;
  if (typeof window !== "undefined" && window.location?.origin) {
    return `${window.location.origin}/recipe/${recipeId}`;
  }
  return `https://macroreel.app/recipe/${recipeId}`;
}

function shareTitle(recipe: Recipe): string {
  const cal = recipe.nutrition?.per_serving?.calories;
  const protein = recipe.nutrition?.per_serving?.protein_g;
  const macros = [
    cal != null ? `${Math.round(cal)} cal` : null,
    protein != null ? `${Math.round(protein)}g protein` : null,
  ]
    .filter(Boolean)
    .join(" | ");
  return macros ? `${recipe.title} — ${macros}` : recipe.title;
}

export function canShareRecipe(): boolean {
  return isNativeApp() || typeof navigator.share === "function" || !!navigator.clipboard;
}

export async function shareRecipe(recipe: Recipe): Promise<ShareRecipeResult> {
  const url = recipeWebUrl(recipe.id);
  const title = shareTitle(recipe);
  const text = "Check out this recipe on MacroReel!";

  if (isNativeApp()) {
    try {
      await Share.share({ title, text, url, dialogTitle: "Share this recipe" });
      return "shared";
    } catch (err) {
      const message = err instanceof Error ? err.message : "";
      if (/cancel/i.test(message)) return "cancelled";
      return "unavailable";
    }
  }

  if (typeof navigator.share === "function") {
    try {
      await navigator.share({ title, text, url });
      return "shared";
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") return "cancelled";
      return "unavailable";
    }
  }

  try {
    await navigator.clipboard.writeText(`${title}\n${url}`);
    return "shared";
  } catch {
    return "unavailable";
  }
}
