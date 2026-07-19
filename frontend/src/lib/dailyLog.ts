import type { DailyLogDay, Nutrition } from "../api";
import * as api from "../api";
import { getDailyLog as getLocalLog, localDateKey } from "./storage";

const MIGRATED_KEY = "macroreel-daily-log-migrated";
const OLD_MIGRATED_KEY = "recipeai-daily-log-migrated";

/** One-time migration from localStorage to server. */
export async function migrateLocalDailyLogOnce(): Promise<void> {
  if (localStorage.getItem(MIGRATED_KEY) === "1" || localStorage.getItem(OLD_MIGRATED_KEY) === "1") return;
  const local = getLocalLog();
  if (local.entries.length === 0) {
    localStorage.setItem(MIGRATED_KEY, "1");
    return;
  }
  try {
    for (const e of local.entries) {
      await api.addDailyLogEntry({
        recipe_id: e.recipeId,
        title: e.title,
        servings: e.servings,
        nutrition: e.nutrition,
        log_date: local.date,
      });
    }
    localStorage.removeItem("macroreel-daily-log");
    localStorage.removeItem("recipeai-daily-log");
    localStorage.setItem(MIGRATED_KEY, "1");
    localStorage.removeItem(OLD_MIGRATED_KEY);
  } catch {
    /* keep local until server is up */
  }
}

export async function loadTodayLog(): Promise<DailyLogDay> {
  await migrateLocalDailyLogOnce();
  return api.fetchDailyLog(localDateKey());
}

export function sumLogTotals(totals: Nutrition): Nutrition {
  return {
    calories: totals.calories ?? 0,
    protein_g: totals.protein_g ?? 0,
    carbs_g: totals.carbs_g ?? 0,
    fat_g: totals.fat_g ?? 0,
    fiber_g: totals.fiber_g ?? 0,
  };
}
