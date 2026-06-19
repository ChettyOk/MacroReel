import { App } from "@capacitor/app";
import type { PluginListenerHandle } from "@capacitor/core";
import type { NavigateFunction } from "react-router-dom";
import { isNativeApp } from "./platform";
import { extractVideoUrlFromText } from "./videoUrl";

/** Parse a native deep link or direct video URL into import text. */
export function parseSharedImportUrl(openUrl: string): string | null {
  const trimmed = openUrl.trim();
  if (!trimmed) return null;

  try {
    const parsed = new URL(trimmed);
    const isImportPath =
      (parsed.protocol === "macroreel:" && parsed.hostname === "import") ||
      (parsed.hostname === "localhost" && parsed.pathname === "/import");

    if (isImportPath) {
      const params = new URLSearchParams(parsed.search);
      const shared = [params.get("url"), params.get("text"), params.get("title")].filter(Boolean).join(" ");
      return extractVideoUrlFromText(shared) || shared.trim() || null;
    }
  } catch {
    /* fall through */
  }

  return extractVideoUrlFromText(trimmed);
}

export function navigateToSharedImport(navigate: NavigateFunction, openUrl: string): boolean {
  const shared = parseSharedImportUrl(openUrl);
  if (!shared) return false;
  navigate(`/import?url=${encodeURIComponent(shared)}`, { replace: true });
  return true;
}

export function setupNativeImportListener(navigate: NavigateFunction): () => void {
  if (!isNativeApp()) return () => undefined;

  let disposed = false;
  const handles: PluginListenerHandle[] = [];

  const handleUrl = (openUrl: string | undefined) => {
    if (!openUrl || disposed) return;
    navigateToSharedImport(navigate, openUrl);
  };

  void App.addListener("appUrlOpen", (event) => {
    handleUrl(event.url);
  }).then((handle) => {
    if (disposed) {
      void handle.remove();
      return;
    }
    handles.push(handle);
  });

  void App.getLaunchUrl().then((result) => {
    handleUrl(result?.url);
  });

  return () => {
    disposed = true;
    handles.forEach((handle) => {
      void handle.remove();
    });
  };
}
