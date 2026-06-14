# Deploy MacroReel

MacroReel ships as **one Docker image**: FastAPI serves the API and the built React PWA from the same origin (HTTPS-ready PWA + share target).

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) (local or any host)
- **Gemini API key** ([Google AI Studio](https://aistudio.google.com/app/apikey)) — required for AI video extract
- Optional: **USDA API key** for better nutrition
- Optional: **YouTube cookies** in env if YouTube blocks bot checks (see README)

## 1. Test locally with Docker

```bash
# From repo root — ensure backend/.env has GEMINI_API_KEY=...
docker compose up --build
```

Open **http://localhost:8000**

- API docs: http://localhost:8000/docs
- Health: http://localhost:8000/health
- Data persists in Docker volume `macroreel-data`

### Manual docker commands

```bash
docker build -t macroreel .
docker run --rm -p 8000:8000 \
  -e GEMINI_API_KEY=your_key_here \
  -e USDA_API_KEY=optional_usda_key \
  -v macroreel-data:/data \
  macroreel
```

## 2. Deploy on Render (recommended)

1. Push this repo to GitHub.
2. [Render Dashboard](https://dashboard.render.com/) → **New** → **Blueprint**.
3. Connect the repo; Render reads `render.yaml`.
4. When prompted, set secrets:
   - `GEMINI_API_KEY` (required)
   - `USDA_API_KEY` (optional)
5. Deploy. Render assigns a URL like `https://macroreel-xxxx.onrender.com`.
6. The **1 GB disk** at `/data` keeps SQLite + thumbnails across restarts.

**Note:** Free Render plans spin down when idle; first request may be slow. Use a paid plan for always-on.

### After deploy

- Install the PWA from your browser (Add to Home Screen).
- Share a TikTok, Instagram, or YouTube link to MacroReel (share target uses your deployed origin).
- For YouTube bot errors, add `YTDLP_COOKIES_FILE` or upload cookies — see README.

## 3. Deploy on Fly.io, Railway, or a VPS

Same image works anywhere Docker runs:

```bash
docker build -t macroreel .
# Push to your registry, then run with:
#   -e GEMINI_API_KEY=...
#   -e DATA_DIR=/data
#   -v or persistent volume for /data
#   -p 80:8000 (or reverse proxy → 8000)
```

Set `PORT` if the platform injects it (Render/Fly do automatically).

## Environment variables (production)

| Variable | Required | Description |
|----------|----------|-------------|
| `GEMINI_API_KEY` | Yes (for AI import) | Google AI Studio key |
| `USDA_API_KEY` | No | Better per-ingredient macros |
| `DATA_DIR` | No | Default `/data` in Docker — SQLite + thumbnails |
| `STATIC_DIR` | No | Default `/app/static` in image |
| `PORT` | No | Default `8000` |
| `ENABLE_MEDIA_PIPELINE` | No | `true` if ffmpeg available in image (enabled in Dockerfile) |
| `SPOONACULAR_API_KEY` | No | Enables Spoonacular average ingredient cost estimates |
| `GROCERY_PRICE_FEED_FILE` | No | JSON partner/store price feed inside the container, e.g. `/data/grocery_prices.json` |
| `GROCERY_PRICE_FEED_URL` | No | Hosted JSON partner/store price feed URL |
| `ENABLE_KOKORO_TTS` | No | `true` to use Kokoro TTS for cook-mode narration |
| `HUGGINGFACE_API_KEY` | No | Required when `KOKORO_TTS_PROVIDER=fal-ai` |
| `KOKORO_VOICE` | No | Default `af_heart` |
| `TTS_CACHE_DIR` | No | Default `/data/tts` in production |
| `YTDLP_COOKIES_FILE` | No | Path inside container for YouTube cookies |
| `EXTRA_CORS_ORIGINS` | No | Only if frontend is on a **different** domain |

## Split frontend + API (optional)

If you host the Vite build on Netlify/Vercel and API elsewhere:

1. Build frontend with `VITE_API_URL=https://your-api.example.com npm run build`
2. Deploy `frontend/dist` to static hosting.
3. Set `EXTRA_CORS_ORIGINS=https://your-pwa.example.com` on the API.
4. Do **not** mount `backend/static` — run API only without the SPA module serving files.

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Blank page | Check `/health`; ensure `static/` exists in image (rebuild Docker). |
| API 404 from browser | Production must use same origin or set `VITE_API_URL` at build time. |
| Data lost on restart | Mount persistent volume at `DATA_DIR` (`/data`). |
| YouTube extract fails | Add cookies env vars; see README. |
| PWA install missing | HTTPS required in production (Render provides it). |

## Verify deployment

```bash
curl -sS https://YOUR_URL/health | jq .
curl -sS -o /dev/null -w "%{http_code}\n" https://YOUR_URL/
```

Expect health `status: ok` and homepage `200`.
