import { API_BASE } from "../api";

export type RuntimeConfig = {
  googleClientId: string;
};

/** Load public runtime config from the API (Docker/Render). Falls back to Vite build-time env. */
export async function loadRuntimeConfig(): Promise<RuntimeConfig> {
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
