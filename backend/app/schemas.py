import json
from datetime import datetime, timezone

from pydantic import BaseModel, Field, HttpUrl, field_validator

DIETARY_FLAGS = [
    "vegetarian",
    "vegan",
    "gluten-free",
    "dairy-free",
    "high-protein",
    "low-carb",
    "keto",
    "nut-free",
]


class Nutrition(BaseModel):
    """Macros, typically per serving."""

    calories: float | None = None
    protein_g: float | None = None
    carbs_g: float | None = None
    fat_g: float | None = None
    fiber_g: float | None = None


class NutritionReport(BaseModel):
    per_serving: Nutrition = Field(default_factory=Nutrition)
    total: Nutrition = Field(default_factory=Nutrition)
    servings: int | None = None
    serving_label: str | None = Field(
        default=None,
        description="What one 'serving' means in the video: tender, piece, strip, etc.",
    )
    estimated_yield_g: float | None = Field(
        default=None,
        description="Total recipe weight (g) summed from weighed/volume ingredients — used for portion scaling.",
    )
    per_serving_weight_g: float | None = Field(
        default=None,
        description="estimated_yield_g / servings — grams (or ml≈g) per one recipe serving.",
    )
    matched: int = 0
    unmatched: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    source: str | None = None  # e.g. "USDA FoodData Central"


class RecipeBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    ingredients: list[str] = Field(default_factory=list)
    steps: list[str] = Field(default_factory=list)
    prep_time_min: int | None = Field(default=None, ge=0, le=100000)
    cook_time_min: int | None = Field(default=None, ge=0, le=100000)
    servings: int | None = Field(default=None, ge=1, le=100)
    dietary_flags: list[str] = Field(default_factory=list)

    @field_validator("title", mode="before")
    @classmethod
    def title_strip(cls, v: str) -> str:
        return str(v).strip()

    @field_validator("ingredients", "steps", mode="before")
    @classmethod
    def strip_strings(cls, v) -> list[str]:
        if v is None:
            return []
        if not isinstance(v, list):
            raise TypeError("expected a list of strings")
        return [str(x).strip() for x in v if str(x).strip()]

    @field_validator("dietary_flags", mode="before")
    @classmethod
    def norm_flags(cls, v) -> list[str]:
        if v is None:
            return []
        if not isinstance(v, list):
            raise TypeError("expected a list of strings")
        out: list[str] = []
        for x in v:
            f = str(x).strip().lower().replace(" ", "-")
            if f and f not in out:
                out.append(f)
        return out


class RecipeCreate(RecipeBase):
    source_url: str | None = Field(default=None, max_length=2000)
    source_platform: str | None = Field(default=None, max_length=40)
    source_context_text: str | None = Field(default=None, max_length=20000)
    thumbnail_url: str | None = Field(default=None, max_length=2000)
    nutrition: NutritionReport | None = None


class RecipeUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=200)
    ingredients: list[str] | None = None
    steps: list[str] | None = None
    prep_time_min: int | None = Field(default=None, ge=0, le=100000)
    cook_time_min: int | None = Field(default=None, ge=0, le=100000)
    servings: int | None = Field(default=None, ge=1, le=100)
    dietary_flags: list[str] | None = None
    nutrition: NutritionReport | None = None
    source_context_text: str | None = Field(default=None, max_length=20000)


class RecipeRead(RecipeBase):
    id: int
    source_url: str | None = None
    source_platform: str | None = None
    source_context_text: str | None = None
    thumbnail_url: str | None = None
    nutrition: NutritionReport | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class VideoExtractRequest(BaseModel):
    url: HttpUrl
    use_ai: bool = Field(
        default=True,
        description="If true, use Google Gemini to structure the recipe. If false, heuristics only (no API usage).",
    )
    use_media: bool | None = Field(
        default=None,
        description="Force the media pipeline (download+ffmpeg+transcribe+frames). Defaults to server config.",
    )
    compute_nutrition: bool | None = Field(
        default=None,
        description="Compute nutrition via USDA. Defaults to server config.",
    )


ACTIVITY_LEVELS = ["sedentary", "light", "moderate", "active", "very_active"]
GOALS = ["lose", "maintain", "gain"]
SEXES = ["male", "female", "other"]
# Common allergen groups users can declare.
ALLERGENS = ["dairy", "gluten", "nuts", "peanuts", "egg", "soy", "shellfish", "fish", "sesame"]


class ProfileBase(BaseModel):
    height_cm: float | None = Field(default=None, ge=50, le=260)
    weight_kg: float | None = Field(default=None, ge=20, le=400)
    age: int | None = Field(default=None, ge=10, le=120)
    sex: str | None = None
    activity_level: str | None = None
    goal: str | None = None
    allergies: list[str] = Field(default_factory=list)
    dietary_prefs: list[str] = Field(default_factory=list)

    @field_validator("sex", mode="before")
    @classmethod
    def _sex(cls, v):
        if v is None or str(v).strip() == "":
            return None
        s = str(v).strip().lower()
        return s if s in SEXES else None

    @field_validator("activity_level", mode="before")
    @classmethod
    def _act(cls, v):
        if v is None or str(v).strip() == "":
            return None
        s = str(v).strip().lower()
        return s if s in ACTIVITY_LEVELS else None

    @field_validator("goal", mode="before")
    @classmethod
    def _goal(cls, v):
        if v is None or str(v).strip() == "":
            return None
        s = str(v).strip().lower()
        return s if s in GOALS else None

    @field_validator("allergies", "dietary_prefs", mode="before")
    @classmethod
    def _lists(cls, v):
        if v is None:
            return []
        if not isinstance(v, list):
            raise TypeError("expected a list of strings")
        out: list[str] = []
        for x in v:
            s = str(x).strip().lower().replace(" ", "-")
            if s and s not in out:
                out.append(s)
        return out


class DailyTargets(BaseModel):
    bmr: int | None = None
    tdee: int | None = None
    target_calories: int | None = None
    protein_g: int | None = None
    carbs_g: int | None = None
    fat_g: int | None = None
    bmi: float | None = None
    bmi_category: str | None = None
    basis: str | None = None  # short human explanation


class ProfileRead(ProfileBase):
    targets: DailyTargets | None = None


class Substitution(BaseModel):
    ingredient: str
    suggestion: str
    reason: str


class RecipeInsights(BaseModel):
    has_profile: bool = False
    per_serving: Nutrition = Field(default_factory=Nutrition)
    calories_pct_of_target: int | None = None
    protein_pct_of_target: int | None = None
    fit_notes: list[str] = Field(default_factory=list)
    allergy_warnings: list[str] = Field(default_factory=list)
    dietary_conflicts: list[str] = Field(default_factory=list)
    substitutions: list[Substitution] = Field(default_factory=list)


class InsightsRequest(BaseModel):
    ingredients: list[str] = Field(default_factory=list)
    servings: int | None = Field(default=None, ge=1, le=100)
    nutrition: NutritionReport | None = None

    @field_validator("ingredients", mode="before")
    @classmethod
    def _clean(cls, v):
        if v is None:
            return []
        if not isinstance(v, list):
            raise TypeError("ingredients must be a list of strings")
        return [str(x).strip() for x in v if str(x).strip()]


class StorePriceEstimate(BaseModel):
    store: str
    region: str
    price: float
    currency: str


class IngredientPriceEstimate(BaseModel):
    ingredient: str
    normalized_name: str
    estimated_weight_g: float | None = None
    quantity_label: str | None = None
    stores: list[StorePriceEstimate] = Field(default_factory=list)
    best_store: str | None = None
    best_price: float | None = None
    notes: list[str] = Field(default_factory=list)


class RecipePriceEstimate(BaseModel):
    items: list[IngredientPriceEstimate] = Field(default_factory=list)
    total_best_price: float | None = None
    currency: str = "USD/CAD"
    notes: list[str] = Field(default_factory=list)
    location_label: str | None = None
    possible_stores: list[str] = Field(default_factory=list)


class GroceryPriceRequest(BaseModel):
    ingredients: list[str] = Field(default_factory=list)
    location: str | None = Field(default=None, max_length=120)

    @field_validator("ingredients", mode="before")
    @classmethod
    def _clean(cls, v) -> list[str]:
        if v is None:
            return []
        if not isinstance(v, list):
            raise TypeError("ingredients must be a list of strings")
        return [str(x).strip() for x in v if str(x).strip()]

    @field_validator("location", mode="before")
    @classmethod
    def _clean_location(cls, v) -> str | None:
        if v is None:
            return None
        cleaned = " ".join(str(v).split())
        return cleaned or None


class RecipeRepairSuggestion(BaseModel):
    field: str
    suggestion: str
    reason: str
    confidence: str = "medium"


class LowCalorieOption(BaseModel):
    title: str
    suggestion: str
    estimated_savings: str | None = None


class RecipeUpgradeRequest(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    ingredients: list[str] = Field(default_factory=list)
    steps: list[str] = Field(default_factory=list)
    servings: int | None = Field(default=None, ge=1, le=100)
    nutrition: NutritionReport | None = None

    @field_validator("ingredients", "steps", mode="before")
    @classmethod
    def _clean_lists(cls, v) -> list[str]:
        if v is None:
            return []
        if not isinstance(v, list):
            raise TypeError("expected a list of strings")
        return [str(x).strip() for x in v if str(x).strip()]


class RecipeUpgradeResponse(BaseModel):
    pricing: RecipePriceEstimate
    substitutions: list[Substitution] = Field(default_factory=list)
    repairs: list[RecipeRepairSuggestion] = Field(default_factory=list)
    low_calorie_options: list[LowCalorieOption] = Field(default_factory=list)
    cook_narration: list[str] = Field(default_factory=list)


class TTSRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=8000)
    voice: str | None = Field(default=None, max_length=80)

    @field_validator("text", mode="before")
    @classmethod
    def _clean_text(cls, v: str) -> str:
        return str(v).strip()


class NutritionRequest(BaseModel):
    ingredients: list[str] = Field(default_factory=list)
    servings: int | None = Field(default=None, ge=1, le=100)
    context_text: str | None = Field(
        default=None,
        max_length=20000,
        description="Video description/caption — used to parse creator-stated calories/macros.",
    )

    @field_validator("ingredients", mode="before")
    @classmethod
    def _clean(cls, v) -> list[str]:
        if v is None:
            return []
        if not isinstance(v, list):
            raise TypeError("ingredients must be a list of strings")
        return [str(x).strip() for x in v if str(x).strip()]


class PortionRequest(BaseModel):
    nutrition: NutritionReport
    amount: float = Field(..., gt=0, le=100000)
    unit: str = Field(..., min_length=1, max_length=20)


class PortionResponse(BaseModel):
    portion: Nutrition
    scale_factor: float
    warning: str | None = None


class DailyLogEntryCreate(BaseModel):
    recipe_id: int | None = None
    title: str = Field(..., min_length=1, max_length=200)
    servings: float = Field(..., gt=0, le=100)
    nutrition: Nutrition
    log_date: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")


class DailyLogEntryRead(BaseModel):
    id: int
    recipe_id: int | None = None
    title: str
    servings: float
    nutrition: Nutrition
    logged_at: datetime


class DailyLogDay(BaseModel):
    date: str
    entries: list[DailyLogEntryRead]
    totals: Nutrition


class DailyLogWeekDay(BaseModel):
    date: str
    meal_count: int
    calories: float | None = None


class ExtractFromVideoResponse(RecipeBase):
    """Draft recipe from a video URL; not saved until the client POSTs /recipes."""

    source_url: str = Field(..., max_length=2000)
    source_platform: str | None = Field(default=None, max_length=40)
    source_video_title: str | None = Field(default=None, max_length=500)
    had_transcript: bool = False
    had_description: bool = False
    had_audio_transcription: bool = False
    had_frame_vision: bool = False
    used_ai: bool = False
    nutrition: NutritionReport | None = None
    source_context_text: str | None = Field(default=None, max_length=20000)
    thumbnail_url: str | None = Field(default=None, max_length=2000)
    pipeline_steps: list[str] = Field(default_factory=list)
    extraction_note: str | None = Field(default=None, max_length=4000)


# ── JSON (de)serialization helpers for the SQLite columns ──


def _dump(value) -> str:
    return json.dumps(value, default=lambda o: o.model_dump() if hasattr(o, "model_dump") else o)


def lists_to_json(ingredients: list[str], steps: list[str]) -> tuple[str, str]:
    return json.dumps(ingredients), json.dumps(steps)


def row_to_read(recipe) -> RecipeRead:
    nutrition = None
    raw_nutrition = getattr(recipe, "nutrition", None)
    if raw_nutrition:
        try:
            nutrition = NutritionReport.model_validate(json.loads(raw_nutrition))
        except (ValueError, TypeError):
            nutrition = None

    dietary = []
    raw_flags = getattr(recipe, "dietary_flags", None)
    if raw_flags:
        try:
            dietary = json.loads(raw_flags)
        except (ValueError, TypeError):
            dietary = []

    return RecipeRead(
        id=recipe.id,
        title=recipe.title,
        ingredients=json.loads(recipe.ingredients),
        steps=json.loads(recipe.steps),
        prep_time_min=getattr(recipe, "prep_time_min", None),
        cook_time_min=getattr(recipe, "cook_time_min", None),
        servings=getattr(recipe, "servings", None),
        dietary_flags=dietary,
        source_url=getattr(recipe, "source_url", None),
        source_platform=getattr(recipe, "source_platform", None),
        source_context_text=getattr(recipe, "source_context_text", None),
        thumbnail_url=getattr(recipe, "thumbnail_url", None),
        nutrition=nutrition,
        created_at=recipe.created_at,
        updated_at=recipe.updated_at,
    )


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def profile_row_to_base(profile) -> ProfileBase:
    def _load(raw) -> list[str]:
        if not raw:
            return []
        try:
            v = json.loads(raw)
            return v if isinstance(v, list) else []
        except (ValueError, TypeError):
            return []

    return ProfileBase(
        height_cm=getattr(profile, "height_cm", None),
        weight_kg=getattr(profile, "weight_kg", None),
        age=getattr(profile, "age", None),
        sex=getattr(profile, "sex", None),
        activity_level=getattr(profile, "activity_level", None),
        goal=getattr(profile, "goal", None),
        allergies=_load(getattr(profile, "allergies", None)),
        dietary_prefs=_load(getattr(profile, "dietary_prefs", None)),
    )
