import json
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

import app.config as config  # noqa: F401 — load .env before other app imports use env
from app.auth import get_current_user, router as auth_router
from app.daily_log import add_entry, delete_entry, get_log_for_date, week_summary
from app.database import ensure_schema, get_db
from app.gemini_extract import GeminiUpstreamError
from app.grocery_prices import estimate_recipe_price
from app.insights import build_insights, compute_targets
from app.models import Profile, Recipe, User
from app.nutrition import compute_nutrition
from app.nutrition_portion import portion_nutrition
from app.pipeline import run_pipeline
from app.schemas import (
    DailyLogDay,
    DailyLogEntryCreate,
    DailyLogEntryRead,
    DailyLogWeekDay,
    ExtractFromVideoResponse,
    GroceryPriceRequest,
    InsightsRequest,
    NutritionReport,
    NutritionRequest,
    PortionRequest,
    PortionResponse,
    ProfileBase,
    ProfileRead,
    RecipeCreate,
    RecipeInsights,
    RecipePriceEstimate,
    RecipeRead,
    RecipeUpdate,
    RecipeUpgradeRequest,
    RecipeUpgradeResponse,
    TTSRequest,
    VideoExtractRequest,
    lists_to_json,
    profile_row_to_base,
    row_to_read,
    utc_now,
)
from app.thumbnail_cache import (
    cache_thumbnail,
    delete_thumbnail,
    get_or_cache_thumbnail,
    resolve_remote_thumbnail_url,
)
from app.spa import mount_spa
from app.tts import TTSError, synthesize_kokoro
from app.upgrades import build_recipe_upgrades
from app.video_context import fetch_video_context
from app.video_urls import normalize_video_url

app = FastAPI(title="Recipe API", version="0.4.0")
app.include_router(auth_router)

_default_origins = [
    "http://127.0.0.1:5173",
    "http://localhost:5173",
    "capacitor://localhost",
    "ionic://localhost",
    "http://localhost",
    "https://localhost",
]
_extra = [o.strip() for o in config.EXTRA_CORS_ORIGINS.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_default_origins + _extra,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    ensure_schema()


@app.get("/health")
def health() -> dict[str, object]:
    return {
        "status": "ok",
        "ai": bool(config.GEMINI_API_KEY),
        "media_pipeline": config.ENABLE_MEDIA_PIPELINE and config.ffmpeg_available(),
        "ffmpeg": config.ffmpeg_available(),
        "nutrition": config.ENABLE_NUTRITION,
        "nutrition_usda": bool(config.USDA_API_KEY),
        "nutrition_gemini": bool(config.GEMINI_API_KEY),
        "tts_kokoro": config.ENABLE_KOKORO_TTS,
        "supported_video_platforms": ["tiktok", "youtube", "instagram", "facebook"],
    }


@app.get("/recipes", response_model=list[RecipeRead])
def list_recipes(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> list[RecipeRead]:
    rows = db.scalars(
        select(Recipe).where(Recipe.user_id == user.id).order_by(Recipe.updated_at.desc())
    ).all()
    return [row_to_read(r) for r in rows]


def _recipe_for_user(db: Session, user: User, recipe_id: int) -> Recipe:
    recipe = db.get(Recipe, recipe_id)
    if recipe is None or recipe.user_id != user.id:
        raise HTTPException(status_code=404, detail="Recipe not found")
    return recipe


@app.get("/recipes/{recipe_id}", response_model=RecipeRead)
def get_recipe(
    recipe_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> RecipeRead:
    return row_to_read(_recipe_for_user(db, user, recipe_id))


@app.get("/recipes/{recipe_id}/thumbnail")
def recipe_thumbnail(
    recipe_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    recipe = _recipe_for_user(db, user, recipe_id)

    cached = get_or_cache_thumbnail(recipe_id, recipe.thumbnail_url, recipe.source_url)
    if cached:
        media = "image/jpeg"
        if cached.suffix == ".webp":
            media = "image/webp"
        elif cached.suffix == ".png":
            media = "image/png"
        return FileResponse(cached, media_type=media, headers={"Cache-Control": "public, max-age=86400"})

    remote = resolve_remote_thumbnail_url(recipe.thumbnail_url, recipe.source_url)
    if remote:
        return RedirectResponse(remote, status_code=302)

    raise HTTPException(status_code=404, detail="No thumbnail")


@app.post("/recipes/extract-from-video", response_model=ExtractFromVideoResponse)
def extract_recipe_from_video(
    body: VideoExtractRequest,
    user: Annotated[User, Depends(get_current_user)],
) -> ExtractFromVideoResponse:
    """Pipeline: yt-dlp + (optional) ffmpeg/Gemini transcription & frame vision -> structured recipe."""
    url = normalize_video_url(str(body.url))
    if len(url) > 2000:
        raise HTTPException(status_code=400, detail="URL too long")

    try:
        result = run_pipeline(url, use_ai=body.use_ai, use_media=body.use_media)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except GeminiUpstreamError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Extraction failed: {e}") from e

    draft = result.draft

    nutrition: NutritionReport | None = None
    want_nutrition = config.ENABLE_NUTRITION if body.compute_nutrition is None else body.compute_nutrition
    if want_nutrition and draft.ingredients:
        nutrition = compute_nutrition(
            draft.ingredients,
            draft.servings,
            context_text=result.source_context_text,
        )
        if nutrition.servings and (draft.servings is None or draft.servings == 1):
            draft.servings = nutrition.servings
        result.steps_log.append(f"computed nutrition ({nutrition.source or 'estimate'})")

    return ExtractFromVideoResponse(
        title=draft.title,
        ingredients=draft.ingredients,
        steps=draft.steps,
        prep_time_min=draft.prep_time_min,
        cook_time_min=draft.cook_time_min,
        servings=draft.servings,
        dietary_flags=draft.dietary_flags,
        source_url=url,
        source_platform=result.platform,
        source_video_title=result.source_video_title,
        had_transcript=result.had_transcript,
        had_description=result.had_description,
        had_audio_transcription=result.had_audio_transcription,
        had_frame_vision=result.had_frame_vision,
        used_ai=result.used_ai,
        nutrition=nutrition,
        pipeline_steps=result.steps_log,
        extraction_note=result.note,
        source_context_text=result.source_context_text,
        thumbnail_url=result.thumbnail_url,
    )


@app.post("/nutrition", response_model=NutritionReport)
def nutrition_for_ingredients(
    body: NutritionRequest,
    user: Annotated[User, Depends(get_current_user)],
) -> NutritionReport:
    """Recompute nutrition for an edited ingredient list (used by the serving adjuster / edits)."""
    if not config.ENABLE_NUTRITION:
        return NutritionReport(servings=body.servings, notes=["Nutrition is disabled on the server."])
    return compute_nutrition(body.ingredients, body.servings, context_text=body.context_text)


@app.post("/nutrition/portion", response_model=PortionResponse)
def nutrition_portion(
    body: PortionRequest,
    user: Annotated[User, Depends(get_current_user)],
) -> PortionResponse:
    """Scale per-serving nutrition to a user portion (g, kg, ml, oz, cups, or servings)."""
    portion, factor, warning = portion_nutrition(body.nutrition, body.amount, body.unit)
    return PortionResponse(portion=portion, scale_factor=round(factor, 4), warning=warning)


def _get_profile_row(db: Session, user: User) -> Profile | None:
    return db.scalars(select(Profile).where(Profile.user_id == user.id).limit(1)).first()


def _get_profile_base(db: Session, user: User) -> ProfileBase | None:
    row = _get_profile_row(db, user)
    if row is None:
        return None
    return profile_row_to_base(row)


@app.get("/profile", response_model=ProfileRead)
def get_profile(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> ProfileRead:
    base = _get_profile_base(db, user)
    if base is None:
        return ProfileRead(targets=None)
    return ProfileRead(**base.model_dump(), targets=compute_targets(base))


@app.put("/profile", response_model=ProfileRead)
def put_profile(
    body: ProfileBase,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> ProfileRead:
    row = _get_profile_row(db, user)
    if row is None:
        row = Profile(user_id=user.id)
        db.add(row)
    row.height_cm = body.height_cm
    row.weight_kg = body.weight_kg
    row.age = body.age
    row.sex = body.sex
    row.activity_level = body.activity_level
    row.goal = body.goal
    row.allergies = json.dumps(body.allergies)
    row.dietary_prefs = json.dumps(body.dietary_prefs)
    row.updated_at = utc_now()
    db.commit()
    db.refresh(row)
    base = profile_row_to_base(row)
    return ProfileRead(**base.model_dump(), targets=compute_targets(base))


@app.get("/daily-log", response_model=DailyLogDay)
def daily_log_get(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    log_date: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
) -> DailyLogDay:
    return get_log_for_date(db, user, log_date)


@app.post("/daily-log", response_model=DailyLogEntryRead, status_code=201)
def daily_log_add(
    body: DailyLogEntryCreate,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> DailyLogEntryRead:
    return add_entry(db, user, body)


@app.delete("/daily-log/{entry_id}", status_code=204)
def daily_log_delete(
    entry_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> None:
    delete_entry(db, user, entry_id)


@app.get("/daily-log/week", response_model=list[DailyLogWeekDay])
def daily_log_week(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    days: int = Query(default=7, ge=1, le=31),
) -> list[DailyLogWeekDay]:
    return week_summary(db, user, days)


@app.post("/insights", response_model=RecipeInsights)
def insights(
    body: InsightsRequest,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> RecipeInsights:
    """Personalized insights, allergy warnings, and substitution suggestions for a recipe/draft."""
    profile = _get_profile_base(db, user)
    return build_insights(body.ingredients, body.nutrition, body.servings, profile)


@app.post("/recipe-upgrades", response_model=RecipeUpgradeResponse)
def recipe_upgrades(
    body: RecipeUpgradeRequest,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> RecipeUpgradeResponse:
    """Grocery pricing, repair suggestions, cheaper swaps, and cook narration support."""
    profile = _get_profile_base(db, user)
    return build_recipe_upgrades(
        title=body.title,
        ingredients=body.ingredients,
        steps=body.steps,
        servings=body.servings,
        nutrition=body.nutrition,
        profile=profile,
    )


@app.post("/grocery-prices", response_model=RecipePriceEstimate)
def grocery_prices(
    body: GroceryPriceRequest,
    user: Annotated[User, Depends(get_current_user)],
) -> RecipePriceEstimate:
    """Estimate shopping-list ingredient prices across configured and built-in stores."""
    return estimate_recipe_price(body.ingredients, body.location)


@app.post("/tts")
def text_to_speech(
    body: TTSRequest,
    user: Annotated[User, Depends(get_current_user)],
) -> Response:
    """Generate cook-mode narration audio with Kokoro when enabled."""
    try:
        audio, media_type = synthesize_kokoro(body.text, body.voice)
    except TTSError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    return Response(
        content=audio,
        media_type=media_type,
        headers={"Cache-Control": "public, max-age=86400"},
    )


def _apply_create(body: RecipeCreate, user: User) -> Recipe:
    ing, st = lists_to_json(body.ingredients, body.steps)
    return Recipe(
        user_id=user.id,
        title=body.title.strip(),
        ingredients=ing,
        steps=st,
        prep_time_min=body.prep_time_min,
        cook_time_min=body.cook_time_min,
        servings=body.servings,
        dietary_flags=json.dumps(body.dietary_flags),
        nutrition=body.nutrition.model_dump_json() if body.nutrition else None,
        source_url=body.source_url,
        source_platform=body.source_platform,
        source_context_text=body.source_context_text,
        thumbnail_url=body.thumbnail_url,
    )


@app.post("/recipes", response_model=RecipeRead, status_code=201)
def create_recipe(
    body: RecipeCreate,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> RecipeRead:
    recipe = _apply_create(body, user)
    db.add(recipe)
    db.commit()
    db.refresh(recipe)
    cache_thumbnail(recipe.id, recipe.thumbnail_url, recipe.source_url)
    return row_to_read(recipe)


@app.patch("/recipes/{recipe_id}", response_model=RecipeRead)
def update_recipe(
    recipe_id: int,
    body: RecipeUpdate,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> RecipeRead:
    recipe = _recipe_for_user(db, user, recipe_id)

    if body.title is not None:
        recipe.title = body.title.strip()
    if body.ingredients is not None:
        recipe.ingredients = json.dumps(body.ingredients)
    if body.steps is not None:
        recipe.steps = json.dumps(body.steps)
    if body.prep_time_min is not None:
        recipe.prep_time_min = body.prep_time_min
    if body.cook_time_min is not None:
        recipe.cook_time_min = body.cook_time_min
    if body.servings is not None:
        recipe.servings = body.servings
    if body.dietary_flags is not None:
        recipe.dietary_flags = json.dumps(body.dietary_flags)
    if body.nutrition is not None:
        recipe.nutrition = body.nutrition.model_dump_json()
    if body.source_context_text is not None:
        recipe.source_context_text = body.source_context_text
    recipe.updated_at = utc_now()

    db.commit()
    db.refresh(recipe)
    return row_to_read(recipe)


@app.post("/recipes/{recipe_id}/refresh-nutrition", response_model=RecipeRead)
def refresh_recipe_nutrition(
    recipe_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> RecipeRead:
    """Re-fetch video caption (if source URL) and recompute macros."""
    recipe = _recipe_for_user(db, user, recipe_id)

    ingredients = json.loads(recipe.ingredients)
    context = recipe.source_context_text

    if recipe.source_url:
        try:
            url = normalize_video_url(recipe.source_url)
            ctx = fetch_video_context(url)
            blob = "\n\n".join(
                x for x in (ctx.description.strip(), ctx.transcript.strip()) if x
            )
            if blob:
                context = blob
                recipe.source_context_text = blob
            if ctx.thumbnail_url:
                recipe.thumbnail_url = ctx.thumbnail_url
                delete_thumbnail(recipe_id)
                cache_thumbnail(recipe_id, ctx.thumbnail_url, url)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e)) from e

    if not config.ENABLE_NUTRITION:
        raise HTTPException(status_code=503, detail="Nutrition is disabled on the server.")

    nutrition = compute_nutrition(ingredients, recipe.servings, context_text=context)
    recipe.nutrition = nutrition.model_dump_json()
    if nutrition.servings and (recipe.servings is None or recipe.servings == 1):
        recipe.servings = nutrition.servings
    recipe.updated_at = utc_now()
    db.commit()
    db.refresh(recipe)
    return row_to_read(recipe)


@app.delete("/recipes/{recipe_id}", status_code=204)
def delete_recipe(
    recipe_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> None:
    recipe = _recipe_for_user(db, user, recipe_id)
    delete_thumbnail(recipe_id)
    db.delete(recipe)
    db.commit()


# Production: serve Vite build from backend/static (see Dockerfile).
mount_spa(app, config.STATIC_DIR)
