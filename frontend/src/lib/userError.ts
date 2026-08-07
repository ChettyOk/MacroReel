/**
 * Turn API / runtime errors into short messages safe to show in the UI.
 * Strips developer tooling, stack traces, and infra jargon.
 */

const DEV_MARKERS =
  /\b(yt-?dlp|ytdlp|ffmpeg|ffprobe|kokoro|edge-?tts|huggingface|hf_token|gemini|traceback|uvicorn|sqlalchemy|pydantic|ENABLE_[A-Z_]+|YTDLP_[A-Z_]+|GEMINI_[A-Z_]+|HUGGINGFACE|KOKORO_|backend\/|\.env|cookies\.txt|PO token|InferenceClient)\b/i;

function stripAnsi(text: string): string {
  return text.replace(/\x1b\[[0-9;]*m/g, "").trim();
}

function firstSentence(text: string, maxLen = 180): string {
  const cleaned = text.replace(/\s+/g, " ").trim();
  if (cleaned.length <= maxLen) return cleaned;
  const cut = cleaned.slice(0, maxLen);
  const at = Math.max(cut.lastIndexOf(". "), cut.lastIndexOf("! "), cut.lastIndexOf("? "));
  if (at > 60) return cut.slice(0, at + 1).trim();
  return `${cut.trim()}…`;
}

/** Map known technical failures to clear user copy. */
export function sanitizeErrorMessage(raw: string, fallback = "Something went wrong. Please try again."): string {
  const text = stripAnsi(raw);
  if (!text) return fallback;
  const lower = text.toLowerCase();

  if (lower.includes("failed to fetch") || lower.includes("networkerror") || lower.includes("load failed")) {
    return "Couldn’t reach the server. Check your connection and try again.";
  }
  if (lower.includes("sign in to confirm") || lower.includes("not a bot")) {
    return "YouTube temporarily blocked this import. Try another public link, wait a moment, or add the recipe by hand.";
  }
  if (lower.includes("ip address is blocked") || lower.includes("your ip address is blocked")) {
    return "This video couldn’t be reached from our servers. Try a different link or add the recipe by hand.";
  }
  if (lower.includes("private video")) {
    return "This video is private. Use a public link, or add the recipe by hand.";
  }
  if (lower.includes("instagram") && (lower.includes("empty media") || lower.includes("login"))) {
    return "Instagram couldn’t share this video. Try a public Reel link, or add the recipe by hand.";
  }
  if (lower.includes("unsupported video host") || lower.includes("invalid url")) {
    return "Paste a TikTok, YouTube, Instagram, or Facebook video link.";
  }
  if (lower.includes("no recipe found") || lower.includes("could not parse recipe")) {
    return "No recipe was found in that video. Try a cooking video with ingredients listed, or add it by hand.";
  }
  if (lower.includes("no title, description") || lower.includes("no usable text")) {
    return "We couldn’t read enough from that video. Try another link or add the recipe by hand.";
  }
  if (lower.includes("email already registered")) {
    return "An account with this email already exists. Sign in, or use Forgot password.";
  }
  if (lower.includes("invalid email or password")) {
    return "Incorrect email or password.";
  }
  if (lower.includes("incorrect security answer")) {
    return "That security answer doesn’t match. Please try again.";
  }
  if (lower.includes("invalid or expired token") || lower.includes("not authenticated") || lower.includes("invalid token")) {
    return "Please sign in again.";
  }
  if (lower.includes("google sign-in is not configured")) {
    return "Google sign-in isn’t available right now. Use email and password instead.";
  }
  if (lower.includes("invalid google") || lower.includes("google account missing")) {
    return "Google sign-in didn’t work. Please try again, or use email and password.";
  }
  if (lower.includes("nutrition is disabled")) {
    return "Nutrition lookup isn’t available right now. You can still save your recipe.";
  }
  if (lower.includes("recipe not found") || lower.includes("log entry not found")) {
    return "We couldn’t find that item. It may have been removed.";
  }
  if (lower.includes("url too long")) {
    return "That link is too long. Try a shorter share link.";
  }
  if (
    DEV_MARKERS.test(text) ||
    lower.includes("extraction failed:") ||
    lower.startsWith("error:") ||
    lower.includes("file \"") ||
    lower.includes("line ")
  ) {
    if (lower.includes("extract") || lower.includes("youtube") || lower.includes("tiktok") || lower.includes("instagram")) {
      return "We couldn’t import that video right now. Try again, use another link, or add the recipe by hand.";
    }
    if (lower.includes("tts") || lower.includes("audio") || lower.includes("voice") || lower.includes("kokoro") || lower.includes("edge")) {
      return "Voice playback isn’t available right now. You can still read the steps on screen.";
    }
    return fallback;
  }

  // FastAPI / pydantic leftovers
  let msg = text
    .replace(/^value error,\s*/i, "")
    .replace(/^(error:\s*)+/i, "")
    .replace(/^\[(?:youtube|tiktok|instagram|facebook)\]\s*/i, "");

  if (/field required/i.test(msg)) return "Please fill in all required fields.";
  if (/string should have at least/i.test(msg) && /password/i.test(msg)) {
    return "Password must be at least 8 characters and include a letter and a number.";
  }

  return firstSentence(msg) || fallback;
}

export function toUserErrorMessage(
  err: unknown,
  fallback = "Something went wrong. Please try again.",
): string {
  if (err instanceof Error && err.message) {
    return sanitizeErrorMessage(err.message, fallback);
  }
  if (typeof err === "string" && err.trim()) {
    return sanitizeErrorMessage(err, fallback);
  }
  return fallback;
}
