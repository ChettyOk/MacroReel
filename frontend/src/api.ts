export const DIETARY_FLAGS = [
  "vegetarian",
  "vegan",
  "gluten-free",
  "dairy-free",
  "high-protein",
  "low-carb",
  "keto",
  "nut-free",
];

export const ALLERGENS = [
  "dairy",
  "gluten",
  "nuts",
  "peanuts",
  "egg",
  "soy",
  "shellfish",
  "fish",
  "sesame",
];

export const ACTIVITY_LEVELS = ["sedentary", "light", "moderate", "active", "very_active"];
export const GOALS = ["lose", "maintain", "gain"];
export const SEXES = ["male", "female", "other"];

export type Nutrition = {
  calories: number | null;
  protein_g: number | null;
  carbs_g: number | null;
  fat_g: number | null;
  fiber_g: number | null;
};

export type NutritionReport = {
  per_serving: Nutrition;
  total: Nutrition;
  servings: number | null;
  serving_label: string | null;
  estimated_yield_g: number | null;
  per_serving_weight_g: number | null;
  matched: number;
  unmatched: string[];
  notes: string[];
  source: string | null;
};

export type Recipe = {
  id: number;
  title: string;
  ingredients: string[];
  steps: string[];
  prep_time_min: number | null;
  cook_time_min: number | null;
  servings: number | null;
  dietary_flags: string[];
  source_url: string | null;
  source_platform: string | null;
  source_context_text: string | null;
  thumbnail_url: string | null;
  nutrition: NutritionReport | null;
  created_at: string;
  updated_at: string;
};

export type ExtractFromVideoResult = {
  title: string;
  ingredients: string[];
  steps: string[];
  prep_time_min: number | null;
  cook_time_min: number | null;
  servings: number | null;
  dietary_flags: string[];
  source_url: string;
  source_platform: string | null;
  source_video_title: string | null;
  had_transcript: boolean;
  had_description: boolean;
  had_audio_transcription: boolean;
  had_frame_vision: boolean;
  used_ai: boolean;
  nutrition: NutritionReport | null;
  pipeline_steps: string[];
  extraction_note: string | null;
  source_context_text: string | null;
  thumbnail_url: string | null;
};

export type RecipeInput = {
  title: string;
  ingredients: string[];
  steps: string[];
  prep_time_min?: number | null;
  cook_time_min?: number | null;
  servings?: number | null;
  dietary_flags?: string[];
  source_url?: string | null;
  source_platform?: string | null;
  source_context_text?: string | null;
  thumbnail_url?: string | null;
  nutrition?: NutritionReport | null;
};

export type Profile = {
  height_cm: number | null;
  weight_kg: number | null;
  age: number | null;
  sex: string | null;
  activity_level: string | null;
  goal: string | null;
  allergies: string[];
  dietary_prefs: string[];
};

export type DailyTargets = {
  bmr: number | null;
  tdee: number | null;
  target_calories: number | null;
  protein_g: number | null;
  carbs_g: number | null;
  fat_g: number | null;
  bmi: number | null;
  bmi_category: string | null;
  basis: string | null;
};

export type ProfileRead = Profile & { targets: DailyTargets | null };

export type Substitution = {
  ingredient: string;
  suggestion: string;
  reason: string;
};

export type RecipeInsights = {
  has_profile: boolean;
  per_serving: Nutrition;
  calories_pct_of_target: number | null;
  protein_pct_of_target: number | null;
  fit_notes: string[];
  allergy_warnings: string[];
  dietary_conflicts: string[];
  substitutions: Substitution[];
};

export type StorePriceEstimate = {
  store: string;
  region: string;
  price: number;
  currency: string;
};

export type IngredientPriceEstimate = {
  ingredient: string;
  normalized_name: string;
  estimated_weight_g: number | null;
  quantity_label: string | null;
  stores: StorePriceEstimate[];
  best_store: string | null;
  best_price: number | null;
  notes: string[];
};

export type RecipePriceEstimate = {
  items: IngredientPriceEstimate[];
  total_best_price: number | null;
  currency: string;
  notes: string[];
};

export type RecipeRepairSuggestion = {
  field: string;
  suggestion: string;
  reason: string;
  confidence: string;
};

export type LowCalorieOption = {
  title: string;
  suggestion: string;
  estimated_savings: string | null;
};

export type RecipeUpgradeResponse = {
  pricing: RecipePriceEstimate;
  substitutions: Substitution[];
  repairs: RecipeRepairSuggestion[];
  low_calorie_options: LowCalorieOption[];
  cook_narration: string[];
};

/** Empty string = same origin (production Docker deploy). Dev defaults to local API. */
export const API_BASE =
  import.meta.env.VITE_API_URL !== undefined
    ? import.meta.env.VITE_API_URL
    : "http://127.0.0.1:8000";
const base = API_BASE;

export function recipeThumbnailUrl(recipeId: number): string {
  return `${base}/recipes/${recipeId}/thumbnail`;
}

export type DailyLogEntry = {
  id: number;
  recipe_id: number | null;
  title: string;
  servings: number;
  nutrition: Nutrition;
  logged_at: string;
};

export type DailyLogDay = {
  date: string;
  entries: DailyLogEntry[];
  totals: Nutrition;
};

export type DailyLogWeekDay = {
  date: string;
  meal_count: number;
  calories: number | null;
};

export type HealthStatus = {
  status: string;
  ai: boolean;
  media_pipeline: boolean;
  ffmpeg: boolean;
  nutrition: boolean;
  nutrition_usda: boolean;
  tts_kokoro?: boolean;
};

function parseApiError(text: string, status: number): Error {
  if (!text) return new Error(`Request failed (${status})`);
  try {
    const j = JSON.parse(text) as { detail?: unknown };
    if (typeof j.detail === "string") return new Error(j.detail);
    if (Array.isArray(j.detail)) {
      const parts = j.detail.map((item) => {
        if (item && typeof item === "object" && "msg" in item)
          return String((item as { msg: string }).msg);
        return JSON.stringify(item);
      });
      return new Error(parts.join("; "));
    }
  } catch {
    /* not JSON */
  }
  return new Error(text);
}

async function parse(res: Response): Promise<void> {
  if (!res.ok) {
    const text = await res.text();
    throw parseApiError(text, res.status);
  }
}

export async function fetchRecipes(): Promise<Recipe[]> {
  const res = await fetch(`${base}/recipes`);
  await parse(res);
  return res.json();
}

export async function fetchRecipe(id: number): Promise<Recipe> {
  const res = await fetch(`${base}/recipes/${id}`);
  await parse(res);
  return res.json();
}

export async function extractRecipeFromVideo(
  url: string,
  options?: { useAi?: boolean; useMedia?: boolean | null; computeNutrition?: boolean | null },
): Promise<ExtractFromVideoResult> {
  const res = await fetch(`${base}/recipes/extract-from-video`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      url,
      use_ai: options?.useAi ?? true,
      use_media: options?.useMedia ?? null,
      compute_nutrition: options?.computeNutrition ?? null,
    }),
  });
  await parse(res);
  return res.json();
}

export async function computeNutrition(
  ingredients: string[],
  servings: number | null,
  contextText?: string | null,
): Promise<NutritionReport> {
  const res = await fetch(`${base}/nutrition`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      ingredients,
      servings,
      context_text: contextText ?? null,
    }),
  });
  await parse(res);
  return res.json();
}

export async function createRecipe(data: RecipeInput): Promise<Recipe> {
  const res = await fetch(`${base}/recipes`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  await parse(res);
  return res.json();
}

export async function updateRecipe(
  id: number,
  data: Partial<RecipeInput>,
): Promise<Recipe> {
  const res = await fetch(`${base}/recipes/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  await parse(res);
  return res.json();
}

export async function deleteRecipe(id: number): Promise<void> {
  const res = await fetch(`${base}/recipes/${id}`, { method: "DELETE" });
  await parse(res);
}

export async function getProfile(): Promise<ProfileRead> {
  const res = await fetch(`${base}/profile`);
  await parse(res);
  return res.json();
}

export async function saveProfile(data: Profile): Promise<ProfileRead> {
  const res = await fetch(`${base}/profile`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  await parse(res);
  return res.json();
}

export async function fetchHealth(): Promise<HealthStatus> {
  const res = await fetch(`${base}/health`);
  await parse(res);
  return res.json();
}

export async function fetchDailyLog(logDate?: string): Promise<DailyLogDay> {
  const q = logDate ? `?log_date=${encodeURIComponent(logDate)}` : "";
  const res = await fetch(`${base}/daily-log${q}`);
  await parse(res);
  return res.json();
}

export async function addDailyLogEntry(data: {
  recipe_id?: number | null;
  title: string;
  servings: number;
  nutrition: Nutrition;
  log_date?: string;
}): Promise<DailyLogEntry> {
  const res = await fetch(`${base}/daily-log`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  await parse(res);
  return res.json();
}

export async function fetchDailyLogWeek(days = 7): Promise<DailyLogWeekDay[]> {
  const res = await fetch(`${base}/daily-log/week?days=${days}`);
  await parse(res);
  return res.json();
}

export async function refreshRecipeNutrition(id: number): Promise<Recipe> {
  const res = await fetch(`${base}/recipes/${id}/refresh-nutrition`, { method: "POST" });
  await parse(res);
  return res.json();
}

export async function getInsights(
  ingredients: string[],
  servings: number | null,
  nutrition: NutritionReport | null,
): Promise<RecipeInsights> {
  const res = await fetch(`${base}/insights`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ingredients, servings, nutrition }),
  });
  await parse(res);
  return res.json();
}

export async function getRecipeUpgrades(recipe: {
  title?: string | null;
  ingredients: string[];
  steps: string[];
  servings: number | null;
  nutrition: NutritionReport | null;
}): Promise<RecipeUpgradeResponse> {
  const res = await fetch(`${base}/recipe-upgrades`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(recipe),
  });
  await parse(res);
  return res.json();
}

export async function synthesizeSpeech(text: string, voice?: string): Promise<Blob> {
  const res = await fetch(`${base}/tts`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, voice: voice ?? null }),
  });
  await parse(res);
  return res.blob();
}
