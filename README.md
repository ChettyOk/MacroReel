# MacroReel

Turn a cooking video into a structured, macro-aware recipe. React (Vite) **PWA** + **FastAPI** (Python) API + **SQLite**.

**Pipeline:** share/paste a TikTok/YouTube/Instagram URL → `yt-dlp` reads title/description/captions → *(optional)* `ffmpeg` extracts audio + key frames → **Gemini** transcribes audio and reads on-screen text → **Gemini** (or heuristics) structures it into `{title, ingredients, steps, prep/cook time, servings, dietary flags}` → **USDA FoodData Central** estimates per-serving macros → you edit, then save.

Everything stays on the **Google AI free tier** (no OpenAI Whisper / GPT-4o needed) and **degrades gracefully**: with no `ffmpeg`, no AI key, or no USDA key, it falls back to captions/description + heuristics and still produces an editable draft.

## What maps to the architecture spec

| Spec layer | This app |
|---|---|
| Share to app | **PWA Web Share Target** (`manifest.webmanifest`) + `?url=`/`?text=`/`?title=` prefill & auto-run. Native iOS Share Extension / Android `ACTION_SEND` are documented as next steps below. |
| Download + audio + frames | `app/media.py` (`yt-dlp` + `ffmpeg`), gated by `ENABLE_MEDIA_PIPELINE`. |
| Transcription | `app/gemini_media.py` → Gemini audio (in place of Whisper). |
| Vision / OCR | `app/gemini_media.py` → Gemini reads sampled frames. |
| Recipe parsing | `app/gemini_extract.py` (structured JSON output) with heuristic fallback `app/heuristic_recipe.py`. |
| Nutrition | `app/nutrition.py` → USDA FoodData Central, per-serving macros. |
| Orchestration | `app/pipeline.py` ties all stages together with fallbacks. |
| Features | Macro breakdown, serving-size adjuster, dietary flags, edit-before-save, download. |
| Database | SQLite (dev) with non-destructive auto-migration; swap to PostgreSQL for prod. |

## Authentication (design note)

| Approach | Verdict |
|----------|---------|
| **Client-only “auth”** (e.g. hiding UI with `localStorage` flags) | **Not** sufficient for a real API. Anyone can call your endpoints directly. |
| **Server-side auth** (sessions or signed JWTs validated on every request) | **Correct** when you have multiple users, saved data that must be private, or paid AI usage. |

**This MVP has no login** so you can ship UI + CRUD quickly. When you add accounts, store a **`user_id` on each recipe** (and optionally a `users` table) and require a **session cookie or `Authorization: Bearer` JWT** validated on every mutating route—never trust the client alone to decide who owns a row.

## Run locally

**Backend** (terminal 1):

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env        # then set GEMINI_API_KEY (required when using AI video extract)
uvicorn app.main:app --reload --port 8000
```

**Video import:** set **`GEMINI_API_KEY`** (or **`GOOGLE_API_KEY`**) in `backend/.env` when **`use_ai: true`** (default in the UI). Get a key at [Google AI Studio](https://aistudio.google.com/app/apikey). Optional: **`GEMINI_MODEL`** (default `gemini-2.0-flash-lite`). Uncheck **Use Gemini** (sends `use_ai: false`) to skip the API and use heuristics only. Caption/description availability depends on the site and video; without any text the endpoint returns `422`.

**Macros (optional):** get a free key at [USDA FoodData Central](https://fdc.nal.usda.gov/api-key-signup.html) and set **`USDA_API_KEY`** in `backend/.env`. Without it, the app still works but reports that nutrition is unavailable.

**Full media pipeline (optional):** install **ffmpeg** (`brew install ffmpeg`) and set **`ENABLE_MEDIA_PIPELINE=true`** (or check the box in the UI) to download the video, transcribe its audio, and read on-screen text via Gemini. This is slower and uses more Gemini quota; when off, the app uses page captions/description only.

**YouTube “Sign in to confirm you’re not a bot”:** see [YouTube cookies (step by step)](#youtube-cookies-step-by-step) and [Troubleshooting](#troubleshooting).

**Frontend** (terminal 2):

```bash
cd frontend
npm install
npm run dev
```

Open the URL Vite prints (usually `http://127.0.0.1:5173`). API docs: `http://127.0.0.1:8000/docs`.

## YouTube cookies (step by step)

YouTube often requires cookies so **yt-dlp** can read the page as a signed-in user. The backend reads **`backend/.env`** (restart **uvicorn** after every change).

**Pick one method.** If you set both `YTDLP_COOKIES_FILE` and `YTDLP_COOKIES_FROM_BROWSER`, the **cookie file wins**.

### Method A — Cookie file (good for sharing a path or running on a server)

1. In your normal browser, **log in to YouTube** (same Google account you use to watch videos).
2. Export a **Netscape / cookies.txt** file that includes **`youtube.com`** cookies. Official guidance: [How do I pass cookies to yt-dlp?](https://github.com/yt-dlp/yt-dlp/wiki/FAQ#how-do-i-pass-cookies-to-yt-dlp) and [Exporting YouTube cookies](https://github.com/yt-dlp/yt-dlp/wiki/Extractors#exporting-youtube-cookies). Many people use a browser add-on that exports **only** the sites you choose (export **youtube.com** only; avoid exporting your whole browser).
3. Create a folder **`backend/cookies/`** (this repo’s `.gitignore` ignores it so you do not commit secrets).
4. Save the file there, for example **`backend/cookies/youtube.txt`**.
5. Open **`backend/.env`** and add a line (no quotes needed unless the path has spaces):

   ```env
   YTDLP_COOKIES_FILE=cookies/youtube.txt
   ```

   Paths are relative to the **`backend/`** directory. You can instead use an **absolute** path to a file anywhere on disk.
6. **Stop** the backend (Ctrl+C) and start it again: `uvicorn app.main:app --reload --port 8000`.
7. In the app, try **Import from video** with a YouTube URL again.

**Security:** That file is a **session** for your Google/YouTube account. Do not commit it, do not paste it into chat, and restrict who can read the server disk.

### Method B — Read cookies from your browser (fastest on a dev laptop)

1. **Quit** the browser you will use (so the cookie database is not locked), **or** use a browser you are okay closing briefly.
2. Stay **logged in to YouTube** in that browser (e.g. Chrome).
3. Open **`backend/.env`** and add **one** line:

   - **Chrome (default profile):**

     ```env
     YTDLP_COOKIES_FROM_BROWSER=chrome
     ```

   - **Edge:**

     ```env
     YTDLP_COOKIES_FROM_BROWSER=edge
     ```

   - **Firefox** (replace with your profile folder name if yt-dlp cannot find the default):

     ```env
     YTDLP_COOKIES_FROM_BROWSER=firefox
     ```

     If you need a specific profile: `firefox:ProfileName` (see [yt-dlp `--cookies-from-browser`](https://github.com/yt-dlp/yt-dlp/wiki/FAQ#how-do-i-pass-cookies-to-yt-dlp)).

4. **Restart uvicorn** (same as step 6 in Method A).
5. Try **Import from video** again.

If Method B fails (permissions, locked DB, wrong profile), use **Method A** instead.

### Troubleshooting

**Environment file location:** The backend loads the project root **`.env`** (next to this README) first, then **`backend/.env`**, so **values in `backend/.env` override the root file** for the same variable. Put secrets in **`backend/.env`** for predictable behavior.

**Gemini API key / invalid key:** Put **`GEMINI_API_KEY=...`** on one line in `backend/.env` ([Google AI Studio](https://aistudio.google.com/app/apikey)). **`GOOGLE_API_KEY`** is accepted as an alias. Restart uvicorn after edits.

**Gemini `429` / quotas:** The free tier has rate and usage caps. If `gemini-2.0-flash` shows `limit: 0`, set **`GEMINI_MODEL=gemini-2.0-flash-lite`** in `backend/.env`. By default the app **retries other models**, then **falls back to heuristic parsing** (`GEMINI_FALLBACK_ON_QUOTA=true`) instead of crashing. See [Gemini rate limits](https://ai.google.dev/gemini-api/docs/rate-limits).

**YouTube still “Sign in to confirm you’re not a bot” with a cookie file:** (1) Run **`pip install -U yt-dlp`** in the same venv as the app. (2) Export a **new** `cookies.txt` while logged into YouTube in that browser (cookies expire). (3) Try **`YTDLP_COOKIES_FROM_BROWSER=chrome`** instead of a file. (4) Some accounts need extra steps (see [Exporting YouTube cookies](https://github.com/yt-dlp/yt-dlp/wiki/Extractors#exporting-youtube-cookies), including **PO token** guidance for hard cases). The app also rotates **player clients** (`android`, `web`, …) automatically for YouTube URLs; override with **`YTDLP_YOUTUBE_PLAYER_CLIENTS`** in `.env` or set it to **`off`** to disable that behavior.

## Share to app (PWA) & native next steps

- **Web / Android PWA:** the frontend ships a `manifest.webmanifest` with a **Web Share Target**. Install MacroReel (browser “Install” / “Add to Home screen”), then **Share** a TikTok, Instagram, or YouTube link and pick **MacroReel**. The URL arrives as `?url=`/`?text=`/`?title=`, prefills the import box, and auto-runs extraction. The service worker (`public/sw.js`) provides installability. *(Install requires HTTPS in production; `localhost` is treated as secure for dev.)*
- **Deep link:** opening `…/import?url=<video-url>` (optionally `&autorun=0`) prefills/triggers an import — handy for testing or other integrations.
- **Native iOS/Android (future):** wrap the web app or build a thin native shell. iOS = an **App Extension (Share Extension)** target that forwards the URL; Android = an `intent-filter` with `ACTION_SEND` (`text/plain`). Both just need to open `…/import?url=<shared-url>`.

## Pages & personalization

The frontend is a multi-page app (React Router):

- **`/` Cookbook** — your saved recipes (the landing page). When empty it becomes an **“attach a link”** page.
- **`/import`** — paste/share a video URL; on success it hands a draft to the add page.
- **`/new` & `/edit/:id`** — the add/edit form (title, times, servings, dietary flags, ingredients/steps, macros, insights).
- **`/recipe/:id`** — full recipe view with macros, personalized insights, swaps, and downloads.
- **`/profile`** — your stats (height, weight, age, sex, activity, goal, allergies, dietary prefs).

**Profile → targets & insights.** The profile drives:
- **Daily targets** — BMR (Mifflin-St Jeor) × activity = TDEE, adjusted for your goal (lose −500 / maintain / gain +350 kcal), plus protein (g/kg by goal), fat (~27%), and carbs (remainder).
- **Per-recipe insights** (`POST /insights`) — % of your daily calories/protein per serving, **allergy warnings** (ingredient scan vs your declared allergens), **dietary-preference conflicts**, and **ingredient substitution suggestions** (e.g. cream → Greek yogurt) filtered by your goal and allergies. All rule-based, so it works with no API key or quota. *General wellness estimates, not medical advice.*

Endpoints: `GET/PUT /profile`, `POST /insights`.

## Nutrition

Calories and macros are computed automatically on import (no USDA key required). Sources are tried in order:

1. **Creator caption** — parses stated macros from the video description (common on TikTok: “406 calories, 52g carbs…”).
2. **USDA FoodData Central** — if `USDA_API_KEY` is set (free key).
3. **Gemini AI estimate** — if `GEMINI_API_KEY` is set (uses the same Google AI key as recipe import).
4. **Built-in averages** — offline fallback for common ingredients.

The UI shows **total recipe calories** (whole batch), **per serving**, and **your portion** (servings eaten adjuster). `POST /nutrition` accepts optional `context_text` (video caption) for better caption parsing.

## Upgrades

- **Store-aware grocery pricing:** the Upgrades tab estimates ingredient and full-recipe cost. By default it uses built-in rough prices for stores like Walmart, Real Canadian Superstore, and Whole Foods. Configure `SPOONACULAR_API_KEY` for Spoonacular average ingredient costs, or `GROCERY_PRICE_FEED_FILE` / `GROCERY_PRICE_FEED_URL` for store-specific live/partner prices.
- **AI cooking companion:** cook mode can read recipe steps aloud. Enable `ENABLE_KOKORO_TTS=true` with `HUGGINGFACE_API_KEY` to use `hexgrad/Kokoro-82M` voice `af_heart`; the browser voice remains the fallback.
- **Ingredient substitutions:** the app suggests cheaper, easier-to-find, or locally available alternatives while keeping the recipe close to the creator's original intent.
- **Recipe repair:** the app flags missing creator details such as oven temperature, cooking time, serving size, ingredient quantities, and nutrition context.
- **Low-calorie serving options:** when recipes are calorie-dense or vague, the app suggests lower-calorie portions or swaps.

### Grocery pricing providers

Provider priority is:

1. Store-specific JSON feed (`GROCERY_PRICE_FEED_FILE` or `GROCERY_PRICE_FEED_URL`)
2. Spoonacular average ingredient estimated cost (`SPOONACULAR_API_KEY`)
3. Built-in placeholder estimates

Spoonacular uses ingredient search plus ingredient information estimated cost. It is useful for average prices, but it does not represent a specific Walmart, Superstore, or Whole Foods location.

### Grocery price feed format

```json
{
  "currency": "CAD",
  "items": [
    {
      "name": "chicken breast",
      "aliases": ["boneless chicken breast"],
      "store": "Real Canadian Superstore",
      "region": "Canada",
      "price": 13.49,
      "unit": "kg"
    },
    {
      "name": "rice",
      "store": "Walmart",
      "region": "US",
      "price": 6.99,
      "package_size_g": 2000
    }
  ]
}
```

Feed items can use `price_per_kg`, `price` + `unit` (`kg`, `g`, or `lb`), or `price` + `package_size_g`.

### Kokoro voice setup

MacroReel can use [hexgrad/Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M) for cook-mode read-aloud. The default voice is `af_heart`.

```env
ENABLE_KOKORO_TTS=true
KOKORO_TTS_PROVIDER=fal-ai
HUGGINGFACE_API_KEY=your_huggingface_token
KOKORO_MODEL=hexgrad/Kokoro-82M
KOKORO_VOICE=af_heart
TTS_CACHE_DIR=/data/tts
```

Generated audio is cached under `TTS_CACHE_DIR`. If Kokoro is disabled or fails, cook mode falls back to the device/browser voice.

## Deploy to production

**Quick path:** Docker Compose locally, then [Render](https://render.com) via `render.yaml`.

```bash
# Local production test (API + PWA on one port)
docker compose up --build
# → http://localhost:8000
```

Full steps (Render, Fly, VPS, env vars, troubleshooting): **[DEPLOY.md](./DEPLOY.md)**

The Docker image builds the React app, copies it into `backend/static`, and serves everything from FastAPI on one origin (PWA install + share target work over HTTPS).

## Native App Shell

To wrap MacroReel with Capacitor for Android/iOS, follow **[CAPACITOR.md](./CAPACITOR.md)**. The native app bundles the React UI and calls your deployed Render backend via `VITE_API_URL`.

## Production notes

- **Database:** SQLite with `DATA_DIR` on a persistent volume (Docker/Render disk). For multiple users at scale, switch to **PostgreSQL** and add Alembic migrations.
- **Auth:** the MVP has no login. Add a `users` table + `user_id` on recipes and validate a session cookie / `Authorization: Bearer` JWT on every mutating route (Firebase Auth or Supabase are easy options). Never trust the client to decide row ownership.
- **Legal:** TikTok’s ToS restricts scraping — for a commercial app use the official API or get permission. You’re extracting *facts* (ingredients/steps), which generally aren’t copyrightable in the US, but a creator’s specific expression may be. If you store user data you need a privacy policy (GDPR/CCPA) and clear data-collection disclosures for the App/Play stores.

## Stack & module map

- **Frontend:** React 19 + TypeScript + Vite PWA. `App.tsx` (import + edit form, dietary flags, macros), `NutritionPanel.tsx` (macro grid + serving adjuster), `RecipeDetailModal.tsx` (view + download + edit), `api.ts`, `recipeDownload.ts`.
- **Backend:** FastAPI + SQLAlchemy 2 + SQLite (`backend/recipes.db`).
  - `app/pipeline.py` — orchestrates ingest → context → optional media → LLM/heuristic.
  - `app/video_context.py` — `yt-dlp` title/description/captions (+ cookie/YouTube hardening).
  - `app/media.py` — `yt-dlp` download + `ffmpeg` audio/frames.
  - `app/gemini_media.py` — Gemini audio transcription + frame OCR/vision.
  - `app/gemini_extract.py` — Gemini structured recipe JSON (with model fallback).
  - `app/heuristic_recipe.py` — no-API fallback parser.
  - `app/nutrition.py` — USDA FoodData Central macros.
- **Endpoints:** `POST /recipes/extract-from-video`, `POST /nutrition`, CRUD `GET/POST/PATCH/DELETE /recipes`, `GET /health` (reports AI/ffmpeg/nutrition availability).
