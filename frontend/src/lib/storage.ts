import type { Nutrition } from "../api";

const ONBOARDING_KEY = "macroreel-onboarding-done";
const OLD_ONBOARDING_KEY = "recipeai-onboarding-done";
const DAILY_LOG_KEY = "macroreel-daily-log";
const OLD_DAILY_LOG_KEY = "recipeai-daily-log";
const CLIENT_CACHE_VERSION_KEY = "macroreel-client-cache-version";
const CLIENT_CACHE_VERSION = "2026-06-15-capacitor-share-v2";
const VOLATILE_CACHE_PREFIXES = [
  "macroreel-shopping-location",
];

export function clearStaleClientCache(): void {
  try {
    if (localStorage.getItem(CLIENT_CACHE_VERSION_KEY) === CLIENT_CACHE_VERSION) return;
    for (const key of Object.keys(localStorage)) {
      if (VOLATILE_CACHE_PREFIXES.some((prefix) => key === prefix || key.startsWith(`${prefix}:`))) {
        localStorage.removeItem(key);
      }
    }
    localStorage.setItem(CLIENT_CACHE_VERSION_KEY, CLIENT_CACHE_VERSION);
  } catch {
    /* Storage can be unavailable in private or restricted WebViews. */
  }
}

export type DailyLogEntry = {
  recipeId: number;
  title: string;
  servings: number;
  nutrition: Nutrition;
  loggedAt: string;
};

export type DailyLog = {
  date: string; // YYYY-MM-DD
  entries: DailyLogEntry[];
};

function todayKey(): string {
  return new Date().toISOString().slice(0, 10);
}

export function isOnboardingDone(userId?: number | null): boolean {
  if (userId != null) {
    return localStorage.getItem(`${ONBOARDING_KEY}:${userId}`) === "1";
  }
  return localStorage.getItem(ONBOARDING_KEY) === "1" || localStorage.getItem(OLD_ONBOARDING_KEY) === "1";
}

export function markOnboardingDone(userId?: number | null): void {
  if (userId != null) {
    localStorage.setItem(`${ONBOARDING_KEY}:${userId}`, "1");
    return;
  }
  localStorage.setItem(ONBOARDING_KEY, "1");
  localStorage.removeItem(OLD_ONBOARDING_KEY);
}

export function getDailyLog(): DailyLog {
  try {
    const raw = localStorage.getItem(DAILY_LOG_KEY) ?? localStorage.getItem(OLD_DAILY_LOG_KEY);
    if (!raw) return { date: todayKey(), entries: [] };
    const log = JSON.parse(raw) as DailyLog;
    if (log.date !== todayKey()) return { date: todayKey(), entries: [] };
    return log;
  } catch {
    return { date: todayKey(), entries: [] };
  }
}

export function saveDailyLog(log: DailyLog): void {
  localStorage.setItem(DAILY_LOG_KEY, JSON.stringify(log));
  localStorage.removeItem(OLD_DAILY_LOG_KEY);
}

export function logMealToday(entry: Omit<DailyLogEntry, "loggedAt">): void {
  const log = getDailyLog();
  log.entries.push({ ...entry, loggedAt: new Date().toISOString() });
  saveDailyLog(log);
}

export function sumLoggedToday(): Nutrition {
  const log = getDailyLog();
  const out: Nutrition = { calories: 0, protein_g: 0, carbs_g: 0, fat_g: 0, fiber_g: 0 };
  for (const e of log.entries) {
    const n = e.nutrition;
    const s = e.servings;
    out.calories = (out.calories ?? 0) + (n.calories ?? 0) * s;
    out.protein_g = (out.protein_g ?? 0) + (n.protein_g ?? 0) * s;
    out.carbs_g = (out.carbs_g ?? 0) + (n.carbs_g ?? 0) * s;
    out.fat_g = (out.fat_g ?? 0) + (n.fat_g ?? 0) * s;
    out.fiber_g = (out.fiber_g ?? 0) + (n.fiber_g ?? 0) * s;
  }
  return {
    calories: out.calories ? Math.round(out.calories) : 0,
    protein_g: out.protein_g ? Math.round(out.protein_g * 10) / 10 : 0,
    carbs_g: out.carbs_g ? Math.round(out.carbs_g * 10) / 10 : 0,
    fat_g: out.fat_g ? Math.round(out.fat_g * 10) / 10 : 0,
    fiber_g: out.fiber_g ? Math.round(out.fiber_g * 10) / 10 : 0,
  };
}
