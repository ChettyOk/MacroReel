import { getAuthToken } from "./lib/auth";

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
  location_label: string | null;
  possible_stores: string[];
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

export type AuthUser = {
  id: number;
  email: string;
  name: string | null;
  picture_url: string | null;
  has_password: boolean;
  has_security_question: boolean;
  created_at: string;
};

export const SECURITY_QUESTIONS = [
  "What city were you born in?",
  "What was your first pet's name?",
  "What is your mother's maiden name?",
  "What was the name of your elementary school?",
] as const;

export type AuthResponse = {
  access_token: string;
  token_type: string;
  user: AuthUser;
};

let onUnauthorized: (() => void) | null = null;

export function setUnauthorizedHandler(handler: (() => void) | null): void {
  onUnauthorized = handler;
}

function authHeaders(extra?: HeadersInit): HeadersInit {
  const headers: Record<string, string> = { ...(extra as Record<string, string>) };
  const token = getAuthToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  return headers;
}

async function apiFetch(path: string, init?: RequestInit): Promise<Response> {
  const headers = authHeaders(init?.headers);
  const res = await fetch(`${base}${path}`, { ...init, headers });
  if (res.status === 401 && onUnauthorized) onUnauthorized();
  return res;
}

export function recipeThumbnailUrl(recipeId: number): string {
  return `${base}/recipes/${recipeId}/thumbnail`;
}

export async function fetchRecipeThumbnailObjectUrl(recipeId: number): Promise<string | null> {
  const res = await apiFetch(`/recipes/${recipeId}/thumbnail`);
  if (!res.ok) return null;
  const blob = await res.blob();
  return URL.createObjectURL(blob);
}

export async function register(
  email: string,
  password: string,
  securityQuestion: string,
  securityAnswer: string,
  name?: string,
): Promise<AuthResponse> {
  const res = await fetch(`${base}/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      email,
      password,
      name: name ?? null,
      security_question: securityQuestion,
      security_answer: securityAnswer,
    }),
  });
  await parse(res);
  return res.json();
}

export async function login(email: string, password: string): Promise<AuthResponse> {
  const res = await fetch(`${base}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  await parse(res);
  return res.json();
}

export async function loginWithGoogle(idToken: string): Promise<AuthResponse> {
  const res = await fetch(`${base}/auth/google`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ id_token: idToken }),
  });
  await parse(res);
  return res.json();
}

export async function fetchCurrentUser(): Promise<AuthUser> {
  const res = await apiFetch("/auth/me");
  await parse(res);
  return res.json();
}

export async function lookupForgotPasswordQuestion(email: string): Promise<string> {
  const res = await fetch(`${base}/auth/forgot-password/lookup`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email }),
  });
  await parse(res);
  const data = (await res.json()) as { security_question: string };
  return data.security_question;
}

export async function resetPasswordWithSecurityAnswer(
  email: string,
  securityAnswer: string,
  newPassword: string,
): Promise<void> {
  const res = await fetch(`${base}/auth/forgot-password/reset`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      email,
      security_answer: securityAnswer,
      new_password: newPassword,
    }),
  });
  await parse(res);
}

export async function updateSecurityQuestion(
  securityQuestion: string,
  securityAnswer: string,
  currentPassword: string,
): Promise<void> {
  const res = await apiFetch("/auth/security-question", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      security_question: securityQuestion,
      security_answer: securityAnswer,
      current_password: currentPassword,
    }),
  });
  await parse(res);
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
  const res = await apiFetch("/recipes");
  await parse(res);
  return res.json();
}

export async function fetchRecipe(id: number): Promise<Recipe> {
  const res = await apiFetch(`/recipes/${id}`);
  await parse(res);
  return res.json();
}

export async function extractRecipeFromVideo(
  url: string,
  options?: { useAi?: boolean; useMedia?: boolean | null; computeNutrition?: boolean | null },
): Promise<ExtractFromVideoResult> {
  const res = await apiFetch("/recipes/extract-from-video", {
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
  const res = await apiFetch("/nutrition", {
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
  const res = await apiFetch("/recipes", {
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
  const res = await apiFetch(`/recipes/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  await parse(res);
  return res.json();
}

export async function deleteRecipe(id: number): Promise<void> {
  const res = await apiFetch(`/recipes/${id}`, { method: "DELETE" });
  await parse(res);
}

export async function getProfile(): Promise<ProfileRead> {
  const res = await apiFetch("/profile");
  await parse(res);
  return res.json();
}

export async function saveProfile(data: Profile): Promise<ProfileRead> {
  const res = await apiFetch("/profile", {
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
  const res = await apiFetch(`/daily-log${q}`);
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
  const res = await apiFetch("/daily-log", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  await parse(res);
  return res.json();
}

export async function fetchDailyLogWeek(days = 7): Promise<DailyLogWeekDay[]> {
  const res = await apiFetch(`/daily-log/week?days=${days}`);
  await parse(res);
  return res.json();
}

export async function refreshRecipeNutrition(id: number): Promise<Recipe> {
  const res = await apiFetch(`/recipes/${id}/refresh-nutrition`, { method: "POST" });
  await parse(res);
  return res.json();
}

export async function getInsights(
  ingredients: string[],
  servings: number | null,
  nutrition: NutritionReport | null,
): Promise<RecipeInsights> {
  const res = await apiFetch("/insights", {
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
  const res = await apiFetch("/recipe-upgrades", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(recipe),
  });
  await parse(res);
  return res.json();
}

export async function getGroceryPrices(ingredients: string[], location?: string | null): Promise<RecipePriceEstimate> {
  const res = await apiFetch("/grocery-prices", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ingredients, location: location?.trim() || null }),
  });
  await parse(res);
  return res.json();
}

export async function synthesizeSpeech(text: string, voice?: string): Promise<Blob> {
  const res = await apiFetch("/tts", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, voice: voice ?? null }),
  });
  await parse(res);
  return res.blob();
}
