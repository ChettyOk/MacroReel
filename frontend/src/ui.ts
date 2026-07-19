/** Shared layout class names — styles live in index.css */

export function linesToList(text: string): string[] {
  return text
    .split("\n")
    .map((s) => s.trim())
    .filter(Boolean);
}

export function numOrNull(text: string): number | null {
  const v = parseFloat(text);
  return Number.isFinite(v) && v >= 0 ? v : null;
}

/** Whole numbers only (prep/cook minutes, servings). */
export function intOrNull(text: string, opts?: { min?: number; max?: number }): number | null {
  const trimmed = text.trim();
  if (!trimmed) return null;
  if (!/^-?\d+$/.test(trimmed)) return null;
  const v = Number.parseInt(trimmed, 10);
  if (!Number.isFinite(v)) return null;
  if (opts?.min != null && v < opts.min) return null;
  if (opts?.max != null && v > opts.max) return null;
  return v;
}
