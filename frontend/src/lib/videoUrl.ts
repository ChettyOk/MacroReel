export type VideoPlatform = "tiktok" | "youtube" | "instagram" | "facebook" | "unknown";

const VIDEO_URL_RE =
  /https?:\/\/(?:www\.|m\.|vm\.)?(?:tiktok\.com|youtu\.be|youtube\.com|instagram\.com|facebook\.com|fb\.watch)[^\s)\]"']*/i;

export function detectPlatform(url: string): VideoPlatform {
  try {
    const host = new URL(url.trim()).hostname.replace(/^www\./, "").toLowerCase();
    if (host.includes("tiktok")) return "tiktok";
    if (host.includes("youtube") || host === "youtu.be") return "youtube";
    if (host.includes("instagram")) return "instagram";
    if (host.includes("facebook") || host === "fb.watch") return "facebook";
  } catch {
    /* ignore */
  }
  return "unknown";
}

export function isSupportedVideoUrl(url: string): boolean {
  return detectPlatform(url) !== "unknown";
}

/** Match backend normalization — YouTube Shorts, youtu.be, embed, etc. */
export function normalizeVideoUrl(url: string): string {
  const raw = url.trim();
  if (!raw) return raw;
  try {
    const parsed = new URL(raw.startsWith("http") ? raw : `https://${raw}`);
    const host = parsed.hostname.replace(/^www\./, "").toLowerCase();

    if (host === "youtu.be") {
      const id = parsed.pathname.slice(1).split("/")[0]?.split("?")[0];
      if (id) return `https://www.youtube.com/watch?v=${id}`;
    }

    if (host.includes("youtube") || host === "music.youtube.com") {
      const parts = parsed.pathname.split("/").filter(Boolean);
      const shortsIdx = parts.indexOf("shorts");
      if (shortsIdx >= 0 && parts[shortsIdx + 1]) {
        const id = parts[shortsIdx + 1].split("?")[0];
        return `https://www.youtube.com/watch?v=${id}`;
      }
      if (parts[0] === "embed" && parts[1]) {
        return `https://www.youtube.com/watch?v=${parts[1]}`;
      }
      const v = parsed.searchParams.get("v");
      if (v) return `https://www.youtube.com/watch?v=${v}`;
    }

    return parsed.href;
  } catch {
    return raw;
  }
}

/** Pull the first supported video URL from share text or query params. */
export function extractVideoUrlFromText(text: string): string | null {
  const trimmed = text.trim();
  if (!trimmed) return null;
  const match = trimmed.match(VIDEO_URL_RE);
  const candidate = match ? match[0].replace(/[),.;!?]+$/, "") : null;
  if (candidate && isSupportedVideoUrl(candidate)) {
    return normalizeVideoUrl(candidate);
  }
  try {
    const u = new URL(trimmed.startsWith("http") ? trimmed : `https://${trimmed}`);
    if (isSupportedVideoUrl(u.href)) return normalizeVideoUrl(u.href);
  } catch {
    /* ignore */
  }
  return null;
}

export function platformDisplayName(platform: string | null | undefined): string {
  if (!platform) return "video";
  const p = platform.toLowerCase();
  if (p.includes("youtube")) return "YouTube";
  if (p.includes("tiktok")) return "TikTok";
  if (p.includes("instagram")) return "Instagram";
  if (p.includes("facebook")) return "Facebook";
  return platform.charAt(0).toUpperCase() + platform.slice(1);
}

export function platformOpenLabel(platform: string | null | undefined): string {
  return `Open on ${platformDisplayName(platform)}`;
}
