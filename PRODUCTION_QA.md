# MacroReel Production QA Checklist

Reusable pass/fail checklist for release readiness. Run **local smoke → critical path → fix P0/P1**, then repeat on production web, then PWA / native.

**Severity:** P0 ship-blocker · P1 major · P2 polish

**How to mark:** `[ ]` pending · `[x]` pass · `[F]` fail (add note in Fault log)

---

## Session info

| Field | Value |
|-------|--------|
| Date | 2026-07-16 |
| Tester | Cursor agent + API/manual smoke |
| App version / commit | `810bfdc` (+ uncommitted QA fixes on `capacitor`) |
| Local URL | API `http://127.0.0.1:8000` · Vite `http://127.0.0.1:5173` |
| Production URL | `https://recipeai-t49x.onrender.com` |
| Native build | Wiring verified in-repo; **device share sheet not exercised this run** |
| Notes | Local video extract OK. Prod video extract blocked by YouTube bot / TikTok IP / IG empty media until cookies configured. Deploy local fixes before re-test. |

---

## 1. Smoke (must pass before deeper work)

### 1A — Local

| ID | Check | Result | Notes |
|----|--------|--------|-------|
| L-S1 | `GET /health` returns 200; `ai` / nutrition flags match env | [x] | ai, oauth, media, nutrition, tts all true |
| L-S2 | `GET /app-config.json` returns `google_client_id` when OAuth configured | [x] | Google client present |
| L-S3 | SPA shell loads (no blank page); API calls no CORS errors | [x] | Vite 200; CORS `http://127.0.0.1:5173` |
| L-S4 | `pytest backend/tests` all green | [x] | 38 passed |

### 1B — Production web

| ID | Check | Result | Notes |
|----|--------|--------|-------|
| P-S1 | `GET /health` 200; expected feature flags | [x] | media_pipeline **false** (matches render.yaml) |
| P-S2 | `GET /app-config.json` + homepage 200 | [x] | home/login/manifest/sw 200 |
| P-S3 | Cold start acceptable (note latency; fail only if unusable) | [x] | ~0.2s when warm |
| P-S4 | `JWT_SECRET` stable (session survives restart/redeploy if testable) | [x] | Register→login→/me OK (secret present in Render) |
| P-S5 | Google OAuth authorized origins include prod URL (if OAuth on) | [ ] | google_oauth true; **manual Console check still needed** |

---

## 2. Critical path

Run against **Local** then **Production**. Mark both columns.

| ID | Flow | Local | Prod | Notes |
|----|------|-------|------|-------|
| C1 | Register new account | [x] | [x] | |
| C2 | Login with email/password | [x] | [x] | |
| C3 | Session survives in-tab refresh | [x] | [x] | `/auth/me` with JWT |
| C4 | Logout clears session; gated routes redirect to `/login` | [x] | [x] | API 401 without token |
| C5 | Forgot password: lookup question → reset → login | [x] | [x] | |
| C6 | Google sign-in (if configured) | [ ] | [ ] | Needs browser interactive OAuth |
| C7 | Onboarding completes → `/home` | [x] | [x] | Profile PUT + targets |
| C8 | Home macro ring / daily targets reflect profile | [x] | [x] | targets.calories etc. returned |
| C9 | Import TikTok URL → draft | [ ] | [F] | Prod: IP blocked (P0 cookies/IP) |
| C10 | Import YouTube URL → draft | [x] | [F] | Local: Carbonara OK; Prod: bot check (P0 cookies) |
| C11 | Import Instagram URL → draft | [ ] | [F] | Prod: empty media / needs cookies |
| C12 | Deep extract fails clearly when media pipeline off | [x] | [x] | UI disables; API returns clear error |
| C13 | Edit draft on `/new` → save recipe | [x] | [x] | Manual + save path via API |
| C14 | Recipe appears in Cookbook | [x] | [x] | `GET /recipes` |
| C15 | Recipe appears in Discover | [x] | [x] | Same list source |
| C16 | Recipe detail: Nutrition tab | [x] | [x] | `/nutrition` 200 |
| C17 | Recipe detail: Cook mode (steps + TTS or browser voice) | [x] | [x] | Local TTS fixed via venv `edge-tts`; UI falls back to browser voice |
| C18 | Recipe detail: Upgrades | [x] | [x] | |
| C19 | Share recipe out (share sheet / clipboard) | [ ] | [ ] | Needs UI; `VITE_WEB_URL` set for native |
| C20 | Add ingredients to shopping cart | [ ] | [ ] | Client-only; needs UI |
| C21 | Log meal → Home remaining calories update | [x] | [x] | Fixed local-date key (see Fault log) |
| C22 | Cart page + grocery price estimate | [x] | [x] | `/grocery-prices` API |
| C23 | Edit recipe (`/edit/:id`) saves | [x] | [x] | |
| C24 | Refresh nutrition | [x] | [x] | |
| C25 | Delete recipe | [x] | [x] | |
| C26 | Profile update persists | [x] | [x] | |
| C27 | Update security question | [x] | [x] | |
| C28 | Shared recipe link host is production origin (not localhost) | N/A | [x] | `.env.capacitor` → `recipeai-t49x.onrender.com` |

---

## 3. Full matrix (PWA / native)

| ID | Check | Result | Notes |
|----|--------|--------|-------|
| M1 | PWA install (Add to Home Screen) | [ ] | Device/browser step |
| M2 | PWA share target → `/import` with URL prefilled | [x]* | *Wiring: manifest `share_target` + SW `/import-share` live on prod |
| M3 | After redeploy, share target still works (reinstall if needed) | [ ] | Device step |
| M4 | Android: share sheet “Import to MacroReel” opens Import with URL | [x]* | *`ShareActivity` + intent filters present |
| M5 | Android: `macroreel://import?url=…` deep link | [x]* | Manifest + `parseSharedImportUrl` unit-checked |
| M6 | Android build points at prod API (`VITE_API_URL`) | [x] | `.env.capacitor` |
| M7 | iOS: Share Extension opens app Import with URL | [x]* | Extension writes App Group + opens deep link |
| M8 | iOS: App Groups configured; cold + warm start | [ ] | Requires Xcode signing on device |
| M9 | iOS: share-out from recipe detail | [ ] | Device step |
| M10 | Native: no localhost API calls in production build | [x] | Capacitor env uses Render URL |

\* Code/static verified; physical share-sheet pass still required before ship.

---

## 4. Deeper coverage (after P0/P1 clear)

| ID | Check | Result | Sev if fail | Notes |
|----|--------|--------|-------------|-------|
| D1 | Discover search / filter / sort | [ ] | P2 | UI |
| D2 | Favorites toggle persists (localStorage) | [ ] | P2 | UI |
| D3 | Favorites/cart are device-local (documented, not multi-device) | [x] | P2 | Documented below |
| D4 | Gemini quota/heuristic fallback UX is understandable | [x] | P1 | Empty drafts now 422 with clear message (local fix) |
| D5 | Cook mode without server TTS (browser voice) | [x] | P2 | Fallback in RecipeDetailPage |
| D6 | Facebook URL import (backend-supported) | [x] | P2 | Hint text updated to include Facebook |
| D7 | Empty states: Cookbook / Cart / Discover | [ ] | P2 | UI |
| D8 | API error toasts / offline messaging | [x] | P1 | yt-dlp errors cleaned (no ANSI) locally |
| D9 | Large cookbook still usable | [ ] | P2 | |
| D10 | Bottom nav all tabs; cart header button | [ ] | P2 | UI |

---

## Fault log

| ID | Sev | Env | Repro | Status | Fix / defer note |
|----|-----|-----|-------|--------|------------------|
| F1 | P1 | Local | `/tts` 503 — `edge-tts` missing from `backend/.venv` while health said TTS on | fixed | Installed `edge-tts` in venv; health now uses `tts_provider_available()` |
| F2 | P1 | Local | Non-recipe YouTube returned 200 with title “Could not parse recipe” | fixed | Pipeline rejects empty drafts with 422 |
| F3 | P1 | Local/Prod | yt-dlp errors showed ANSI / long wiki tails | fixed (local) | `_clean_ytdlp_error` + private-video message; **redeploy needed for prod** |
| F4 | P2 | Local | Error hint omitted Facebook | fixed | `video_urls` + ImportPage copy |
| F5 | P1 | Frontend | Daily log “today” used UTC via `toISOString()` | fixed | `localDateKey()` + LogMealModal/loadTodayLog send local date |
| F6 | P0 | Prod | YouTube extract: “Sign in to confirm you’re not a bot” | deferred | Set `YTDLP_COOKIES_CONTENT` (or cookies file) on Render; redeploy/restart |
| F7 | P0 | Prod | TikTok: IP blocked; Instagram: empty media without cookies | deferred | Same cookie/IP strategy; test with real public cooking links after cookies |

---

## Exit criteria

Ship-ready when:

- [x] All Smoke + Critical Path pass on **local** (API/critical; Google OAuth + some UI still manual)
- [ ] All Smoke + Critical Path pass on **production web** — **blocked on F6/F7 video import**
- [ ] At least one real import per primary platform (TikTok, YouTube, Instagram) on **prod**
- [ ] PWA share **or** native share works on primary launch device(s)
- [x] No open P0 in code; P0s deferred are **ops** (cookies) listed below
- [x] This file dated with results

### Deferred P1s / P0s

| ID | Reason | Owner |
|----|--------|-------|
| F6 | Prod YouTube bot wall — needs `YTDLP_COOKIES_CONTENT` on Render | Ops / you |
| F7 | Prod TikTok/IG extract — cookies / egress IP | Ops / you |
| P-S5 | Confirm Google OAuth JS origins include Render URL | You |
| M1–M9 device | Physical PWA/iOS/Android share sheet | You |
| Deploy | Push QA fixes so prod gets clean errors + empty-draft reject + local-date log | You |

### Known limitations (not bugs)

- Favorites and shopping cart are localStorage-only (not synced across devices).
- JWT lives in `sessionStorage` (cleared when the browser session ends).
- Render free/starter cold starts can be slow.
- Media / Deep extract disabled in production (`ENABLE_MEDIA_PIPELINE=false`).
- Grocery prices may use built-in placeholders unless Spoonacular/feed is configured.

---

## Results summary (fill at end of run)

| Phase | Status | Date |
|-------|--------|------|
| Local smoke | **Pass** | 2026-07-16 |
| Local critical path | **Pass** (YouTube import + CRUD/auth/log; TikTok/IG not re-hit with live cooking URLs) | 2026-07-16 |
| Production smoke + critical | **Partial** — auth/CRUD/TTS OK; **video import blocked** (cookies) | 2026-07-16 |
| PWA / native matrix | **Wiring pass** / device share pending | 2026-07-16 |
| Deeper coverage | Partial (API-level); remaining UI polish unchecked | 2026-07-16 |
| **Ship-ready?** | **No** — until prod cookies + redeploy of QA fixes + one device share pass | 2026-07-16 |

### Fixes landed this run (not yet on Render)

- [`backend/app/tts.py`](backend/app/tts.py) — `tts_provider_available()` for accurate `/health`
- [`backend/app/pipeline.py`](backend/app/pipeline.py) — reject empty “Could not parse recipe” drafts
- [`backend/app/video_context.py`](backend/app/video_context.py) — clean yt-dlp errors
- [`backend/app/video_urls.py`](backend/app/video_urls.py) / ImportPage — Facebook in hint
- [`frontend/src/lib/storage.ts`](frontend/src/lib/storage.ts) + LogMealModal / dailyLog — local calendar date for meal log
- New tests: `test_pipeline_empty.py`, `test_video_context_errors.py`, TTS availability tests

### Next actions for you

1. Add YouTube (and ideally social) cookies to Render: `YTDLP_COOKIES_CONTENT`
2. Deploy current branch so prod gets error/empty-draft/date fixes
3. Re-run C9–C11 on prod with real cooking links
4. One physical pass: PWA share **or** Android/iOS share → Import
