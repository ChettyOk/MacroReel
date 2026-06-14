"""First-pass upgrade tools for pricing, recipe repair, and cook assistance."""

from __future__ import annotations

import re

from app.grocery_prices import estimate_recipe_price
from app.insights import suggest_substitutions
from app.schemas import (
    LowCalorieOption,
    NutritionReport,
    ProfileBase,
    RecipeRepairSuggestion,
    RecipeUpgradeResponse,
)

_LOW_CAL_SWAPS = [
    ("heavy cream", "Use evaporated skim milk or Greek yogurt for creaminess.", "Often saves 40-70 calories per serving."),
    ("cream", "Use Greek yogurt, light cream cheese, or evaporated skim milk.", "Often saves 30-60 calories per serving."),
    ("butter", "Use half the butter plus broth, lemon juice, or cooking spray.", "Can save about 50 calories per tablespoon removed."),
    ("oil", "Measure oil instead of free-pouring, or switch to spray for roasting.", "Each tablespoon reduced saves about 120 calories."),
    ("mayonnaise", "Swap mayo for Greek yogurt or a yogurt-mayo blend.", "Often saves 50-90 calories per serving."),
    ("cheese", "Use a stronger cheese and reduce the amount by one-third.", "Keeps flavor while lowering calories."),
    ("sugar", "Reduce sugar by 25% or use monk fruit/stevia where texture allows.", "Cuts added sugar calories."),
    ("rice", "Use half rice and half cauliflower rice.", "Can save 80-120 calories per serving."),
    ("pasta", "Use zucchini noodles or high-protein pasta and reduce portion size.", "Can lower calories or improve protein/fiber."),
]

_TEMP_RE = re.compile(r"\b(?:\d{3}\s*(?:f|c|degrees?)|gas mark \d)\b", re.I)
_TIME_RE = re.compile(r"\b\d+\s*(?:-\s*\d+\s*)?(?:min|mins|minutes?|hours?|hrs?)\b", re.I)
_QTY_RE = re.compile(r"\b\d|[¼½¾⅓⅔⅛⅜⅝⅞]")


def repair_recipe(
    ingredients: list[str],
    steps: list[str],
    servings: int | None,
    nutrition: NutritionReport | None,
) -> list[RecipeRepairSuggestion]:
    text = " ".join(steps).lower()
    repairs: list[RecipeRepairSuggestion] = []

    if servings is None:
        repairs.append(
            RecipeRepairSuggestion(
                field="servings",
                suggestion="Default to 4 servings, then adjust after weighing or plating the final recipe.",
                reason="The creator did not provide servings, so the app needs a sensible editable default.",
            )
        )

    if ("bake" in text or "roast" in text or "oven" in text) and not _TEMP_RE.search(text):
        repairs.append(
            RecipeRepairSuggestion(
                field="temperature",
                suggestion="Use 375 degF / 190 degC as a middle oven temperature unless the food needs a specific setting.",
                reason="Many baked or roasted recipes omit temperature; 375 degF is a common moderate default.",
            )
        )

    if ("air fry" in text or "airfry" in text) and not _TEMP_RE.search(text):
        repairs.append(
            RecipeRepairSuggestion(
                field="temperature",
                suggestion="Start around 390-400 degF for air frying and check early for doneness.",
                reason="Most air-fryer recipes use high heat, but exact timing depends on thickness.",
            )
        )

    if steps and not _TIME_RE.search(text):
        repairs.append(
            RecipeRepairSuggestion(
                field="cook_time",
                suggestion="Estimate 20-30 minutes total cooking time, then verify by texture, temperature, and doneness.",
                reason="No clear cook time was found in the recipe steps.",
            )
        )

    vague_ingredients = [line for line in ingredients if not _QTY_RE.search(line)]
    if vague_ingredients:
        repairs.append(
            RecipeRepairSuggestion(
                field="ingredient_quantities",
                suggestion=f"Add quantities for: {', '.join(vague_ingredients[:4])}.",
                reason="Missing quantities make macros, grocery prices, and repeatable cooking less accurate.",
                confidence="high",
            )
        )

    if nutrition is None or nutrition.per_serving.calories is None:
        repairs.append(
            RecipeRepairSuggestion(
                field="nutrition",
                suggestion="Use creator-stated macros when available; otherwise calculate from ingredient amounts.",
                reason="No reliable calories per serving are currently attached to this recipe.",
            )
        )

    return repairs[:8]


def low_calorie_options(ingredients: list[str], nutrition: NutritionReport | None) -> list[LowCalorieOption]:
    text = " | ".join(i.lower() for i in ingredients)
    out: list[LowCalorieOption] = []
    seen: set[str] = set()
    for trigger, suggestion, savings in _LOW_CAL_SWAPS:
        if trigger in text and trigger not in seen:
            seen.add(trigger)
            out.append(
                LowCalorieOption(
                    title=f"Lighten {trigger}",
                    suggestion=suggestion,
                    estimated_savings=savings,
                )
            )
    calories = nutrition.per_serving.calories if nutrition else None
    if calories and calories >= 650:
        out.insert(
            0,
            LowCalorieOption(
                title="Smaller macro-friendly portion",
                suggestion="Try logging 0.75 serving and add a high-volume side like salad, steamed vegetables, or broth soup.",
                estimated_savings=f"About {round(calories * 0.25)} calories saved versus a full serving.",
            ),
        )
    return out[:8]


def cook_narration(title: str | None, steps: list[str]) -> list[str]:
    if not steps:
        return ["No cooking steps were found. Add steps before using read-aloud cook mode."]
    intro = f"Starting {title}." if title else "Starting this recipe."
    return [intro, *[f"Step {idx}. {step}" for idx, step in enumerate(steps, start=1)]]


def build_recipe_upgrades(
    *,
    title: str | None,
    ingredients: list[str],
    steps: list[str],
    servings: int | None,
    nutrition: NutritionReport | None,
    profile: ProfileBase | None,
) -> RecipeUpgradeResponse:
    return RecipeUpgradeResponse(
        pricing=estimate_recipe_price(ingredients),
        substitutions=suggest_substitutions(ingredients, profile),
        repairs=repair_recipe(ingredients, steps, servings, nutrition),
        low_calorie_options=low_calorie_options(ingredients, nutrition),
        cook_narration=cook_narration(title, steps),
    )
