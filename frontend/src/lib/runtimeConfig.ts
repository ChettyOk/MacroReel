import { API_BASE } from "../api";

export type RuntimeConfig = {
  googleClientId: string;
};

declare global {
  interface Window {
    __MACROREEL_CONFIG__?: { google_client_id?: string };
  }
}

/** Injected into index.html by the production API server before React loads. */
export function readInlineRuntimeConfig(): RuntimeConfig | null {
  const id = window.__MACROREEL_CONFIG__?.google_client_id?.trim();
  if (id) return { googleClientId: id };
  return null;
}

/** Load public runtime config. Inline script first, then API, then Vite build-time env. */
export async function loadRuntimeConfig(): Promise<RuntimeConfig> {
  const inline = readInlineRuntimeConfig();
  if (inline) return inline;

  const fromBuild = (import.meta.env.VITE_GOOGLE_CLIENT_ID ?? "").trim();
  const configUrl = `${API_BASE || ""}/app-config.json`;

  try {
    const res = await fetch(configUrl, { cache: "no-store" });
    if (res.ok) {
      const data = (await res.json()) as { google_client_id?: string };
      const fromServer = (data.google_client_id ?? "").trim();
      return { googleClientId: fromServer || fromBuild };
    }
  } catch {
    /* Dev API may be down; use build-time values. */
  }

  return { googleClientId: fromBuild };
}
