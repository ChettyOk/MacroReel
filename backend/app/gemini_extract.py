"""Use Google Gemini (Google AI Studio / free-tier Gemini API) to structure recipe text into JSON."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from app.config import GEMINI_API_KEY, GEMINI_MODEL, GEMINI_MODEL_FALLBACKS
from app.schemas import DIETARY_FLAGS, Nutrition, NutritionReport, RecipeBase

SYSTEM = f"""You extract ONE cooking recipe from text taken from a social cooking video.
The text may include the title, the description/caption, on-screen text (OCR), and an audio transcript.

CRITICAL ACCURACY RULES:
- Use ONLY facts explicitly present in the provided text. Do NOT invent, guess, or "complete" the recipe from general cooking knowledge.
- Do NOT substitute ingredients, change quantities, or invent steps that are not written or spoken in the source text.
- Prefer an ingredient list from the description/caption when present. Prefer steps from the transcript / on-screen text when present.
- If a quantity/unit is not stated, omit the quantity rather than inventing one (e.g. "chicken breast" not "2 cups chicken breast").
- If ingredients or steps are incomplete in the source, return only what is supported — leave arrays shorter or empty rather than fabricating.
- If there is no real recipe in the text, use title "Could not parse recipe" with empty ingredients and steps.
- title: concise recipe name from the video (not clickbait fluff).
- prep_time_min / cook_time_min / servings: integers only when explicitly stated; else null.
- dietary_flags: subset of {DIETARY_FLAGS} only when clearly stated or obvious from listed ingredients; else [].
- stated_calories / stated_protein_g / stated_carbs_g / stated_fat_g / stated_fiber_g: ONLY when the source text explicitly lists those macro numbers (e.g. "520 cal, 40g protein"). Otherwise null. Never estimate macros.
- Respond with JSON only, no markdown fences.
JSON schema: {{"title": string, "ingredients": string[], "steps": string[], "prep_time_min": int|null, "cook_time_min": int|null, "servings": int|null, "dietary_flags": string[], "stated_calories": number|null, "stated_protein_g": number|null, "stated_carbs_g": number|null, "stated_fat_g": number|null, "stated_fiber_g": number|null}}
"""

_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "ingredients": {"type": "array", "items": {"type": "string"}},
        "steps": {"type": "array", "items": {"type": "string"}},
        "prep_time_min": {"type": "integer", "nullable": True},
        "cook_time_min": {"type": "integer", "nullable": True},
        "servings": {"type": "integer", "nullable": True},
        "dietary_flags": {"type": "array", "items": {"type": "string"}},
        "stated_calories": {"type": "number", "nullable": True},
        "stated_protein_g": {"type": "number", "nullable": True},
        "stated_carbs_g": {"type": "number", "nullable": True},
        "stated_fat_g": {"type": "number", "nullable": True},
        "stated_fiber_g": {"type": "number", "nullable": True},
    },
    "required": ["title", "ingredients", "steps"],
}


class GeminiUpstreamError(Exception):
    """Gemini / Google API returned a client-visible error; HTTP status is chosen in the route."""

    __slots__ = ("status_code",)

    def __init__(self, message: str, status_code: int) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass
class AiExtractionOutcome:
    draft: RecipeBase
    model_used: str
    stated_nutrition: NutritionReport | None = None


def _models_to_try() -> list[str]:
    ordered: list[str] = []
    if GEMINI_MODEL:
        ordered.append(GEMINI_MODEL)
    for part in GEMINI_MODEL_FALLBACKS.split(","):
        m = part.strip()
        if m and m not in ordered:
            ordered.append(m)
    return ordered or ["gemini-2.0-flash-lite"]


def _parse_json_from_model(text: str) -> dict[str, Any]:
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```(?:json)?\s*", "", t, flags=re.IGNORECASE)
        t = re.sub(r"\s*```$", "", t)
    return json.loads(t)


def _coerce_int(value: Any) -> int | None:
    try:
        if value is None:
            return None
        return int(value)
    except (ValueError, TypeError):
        return None


def _coerce_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (ValueError, TypeError):
        return None


def _stated_nutrition_from_parsed(data: dict[str, Any], servings: int | None) -> NutritionReport | None:
    cal = _coerce_float(data.get("stated_calories"))
    protein = _coerce_float(data.get("stated_protein_g"))
    carbs = _coerce_float(data.get("stated_carbs_g"))
    fat = _coerce_float(data.get("stated_fat_g"))
    fiber = _coerce_float(data.get("stated_fiber_g"))
    if cal is None and protein is None and carbs is None and fat is None:
        return None
    srv = max(servings or 1, 1)
    per = Nutrition(
        calories=cal,
        protein_g=protein,
        carbs_g=carbs,
        fat_g=fat,
        fiber_g=fiber,
    )
    total = Nutrition(
        calories=round(cal * srv, 1) if cal is not None else None,
        protein_g=round(protein * srv, 1) if protein is not None else None,
        carbs_g=round(carbs * srv, 1) if carbs is not None else None,
        fat_g=round(fat * srv, 1) if fat is not None else None,
        fiber_g=round(fiber * srv, 1) if fiber is not None else None,
    )
    return NutritionReport(
        per_serving=per,
        total=total,
        servings=servings or srv,
        source="Creator caption (AI-extracted stated macros)",
        notes=["Macros taken from numbers stated in the video text — not estimated."],
    )


def _draft_from_parsed(data: dict[str, Any]) -> tuple[RecipeBase, NutritionReport | None]:
    title = str(data.get("title") or "").strip() or "Imported recipe"
    ingredients = data.get("ingredients") if isinstance(data.get("ingredients"), list) else []
    steps = data.get("steps") if isinstance(data.get("steps"), list) else []
    flags = data.get("dietary_flags") if isinstance(data.get("dietary_flags"), list) else []
    servings = _coerce_int(data.get("servings"))
    draft = RecipeBase(
        title=title,
        ingredients=[str(x).strip() for x in ingredients if str(x).strip()],
        steps=[str(x).strip() for x in steps if str(x).strip()],
        prep_time_min=_coerce_int(data.get("prep_time_min")),
        cook_time_min=_coerce_int(data.get("cook_time_min")),
        servings=servings,
        dietary_flags=[str(x) for x in flags if str(x) in DIETARY_FLAGS],
    )
    return draft, _stated_nutrition_from_parsed(data, servings)


def _quota_error_message(exc: genai_errors.ClientError) -> str:
    msg = getattr(exc, "message", None) or str(exc)
    low = msg.lower()
    if "limit: 0" in low or "free_tier" in low:
        return (
            "Gemini free-tier quota for this model is 0 (model may be unavailable on your key or region). "
            "Try GEMINI_MODEL=gemini-2.0-flash-lite in backend/.env, wait and retry, check https://ai.dev/rate-limit , "
            "or uncheck \u201cUse Gemini\u201d for heuristic-only import."
        )
    return (
        "Gemini quota or rate limit (429). Free tier has caps \u2014 wait and retry, try "
        "GEMINI_MODEL=gemini-2.0-flash-lite, or see https://ai.google.dev/gemini-api/docs/rate-limits"
    )


def _generate_once(client: "genai.Client", model: str, user_msg: str) -> AiExtractionOutcome:
    response = client.models.generate_content(
        model=model,
        contents=user_msg,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM,
            temperature=0.0,
            response_mime_type="application/json",
            response_schema=_RESPONSE_SCHEMA,
        ),
    )
    try:
        raw = (response.text or "").strip()
    except ValueError as e:
        raise RuntimeError(
            "Gemini did not return usable text (content may be blocked or empty). Try heuristic import."
        ) from e
    if not raw:
        raise RuntimeError("Empty model response")
    draft, stated = _draft_from_parsed(_parse_json_from_model(raw))
    return AiExtractionOutcome(draft=draft, model_used=model, stated_nutrition=stated)


def structure_recipe(context_text: str) -> AiExtractionOutcome:
    """Turn combined recipe text (captions + transcript + on-screen text) into a structured draft."""
    if not GEMINI_API_KEY:
        raise RuntimeError(
            "GEMINI_API_KEY (or GOOGLE_API_KEY) is not set \u2014 create a free key at "
            "https://aistudio.google.com/app/apikey"
        )
    if not context_text.strip():
        raise ValueError("No usable text (no title, description, captions, transcript, or on-screen text).")

    client = genai.Client(api_key=GEMINI_API_KEY)
    user_msg = (
        "Extract the recipe EXACTLY as stated in the following video text. "
        "Do not invent ingredients, steps, quantities, or macros.\n\n"
        f"{context_text}\n\n"
        "Return JSON only with keys title, ingredients, steps, prep_time_min, cook_time_min, "
        "servings, dietary_flags, stated_calories, stated_protein_g, stated_carbs_g, "
        "stated_fat_g, stated_fiber_g."
    )

    models = _models_to_try()
    last_quota: genai_errors.ClientError | None = None

    for model in models:
        try:
            return _generate_once(client, model, user_msg)
        except genai_errors.ClientError as e:
            code = int(getattr(e, "code", 0) or 0)
            msg = (getattr(e, "message", None) or str(e)).lower()
            if code in (400, 401, 403) and (
                "api key" in msg or "api_key_invalid" in msg or "permission" in msg
            ):
                raise GeminiUpstreamError(
                    "Gemini rejected the API key or access (check GEMINI_API_KEY in backend/.env). "
                    "Create a key at https://aistudio.google.com/app/apikey",
                    401 if code != 403 else 403,
                ) from e
            if code == 404 or ("not found" in msg and "model" in msg):
                continue
            if code == 429 or "resource exhausted" in msg or "quota" in msg:
                last_quota = e
                continue
            raise RuntimeError(f"Gemini client error ({code}) on {model}: {e}") from e
        except genai_errors.ServerError as e:
            raise RuntimeError(f"Gemini server error on {model}: {e}") from e

    if last_quota is not None:
        raise GeminiUpstreamError(_quota_error_message(last_quota), 429) from last_quota
    raise RuntimeError(f"Gemini failed for all models tried: {', '.join(models)}")
