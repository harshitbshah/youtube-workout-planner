# Progress

## Status
Phases 1–5 complete. 206/206 tests passing.
Both Railway (backend) and Vercel (frontend) live. E2E testing in progress.

## What's built

### Phase 1–3 (Backend)
FastAPI + PostgreSQL (Alembic), Google OAuth, Fernet encryption, channels/schedule/plan
routers, scanner/classifier/planner services, APScheduler weekly cron, scan endpoint.

### Phase 4 (Frontend) — complete
- Landing/marketing page (`/`) — hero, how it works, features, sign-up CTA
- Onboarding (`/onboarding`) — 3-step: channels → schedule → generate first plan
- Dashboard (`/dashboard`) — 7-day plan grid, regenerate, nav to library/settings
- Library browser (`/library`) — filter by workout type/body focus/difficulty/channel,
  assign video to plan day, pagination
- Settings (`/settings`) — edit display name, manage channels, edit schedule, delete account
- Shared components: `ChannelManager`, `ScheduleEditor` (reused in onboarding + settings)
- Backend: `PATCH /auth/me` (display name), `DELETE /auth/me` (account deletion)
- Bug fix: `GET /library` filters are case-insensitive (`func.lower`) — classifier stores
  mixed-case values ("HIIT", "Strength") but frontend sends lowercase

### Phase 5 (Playlist Publishing) — complete
- `POST /plan/publish` — publishes current plan to user's YouTube playlist
- Server-side OAuth: decrypts stored refresh token → exchanges for access token
- First publish creates a private playlist and stores its ID; subsequent runs reuse it
- Auto-publish in APScheduler cron (Sundays) if credentials are valid
- Revoked access: `google.auth.exceptions.RefreshError` or YouTube 401/403 sets
  `credentials_valid=False` in DB and returns HTTP 403 to client
- `GET /auth/me` now returns `youtube_connected` + `credentials_valid`
- Dashboard: Publish button enabled when connected + valid credentials + plan exists
- Dashboard: amber banner when YouTube access revoked
- Dashboard: green success banner with playlist link after publish
- DB migration 002: `credentials_valid` (bool, default true) + `youtube_playlist_id` columns

### Deployment fixes (2026-03-09) — complete
See "Deployment Bug Log" below for full diagnosis + root causes.
- `api/database.py` + `alembic/env.py`: rewrite `postgres://` → `postgresql://` at runtime
- `requirements.txt`: pinned all unpinned deps (`sqlalchemy>=2.0`, `fastapi>=0.110`, etc.)
- `Dockerfile`: added `exec` before `uvicorn` so it runs as PID 1
- `api/main.py`: `SameSite=none; Secure` on session cookie in production — required for
  cross-domain cookies between Vercel frontend and Railway backend
- Railway dashboard: proxy port corrected from 8000 → 8080

## Next
- Complete E2E testing (Groups 1–7 in `docs/testing.md`)
- Verify full OAuth → onboarding → scan → plan → publish flow end-to-end
- Once E2E passes: share with first users

## Deployment Status
- **Railway (backend):** ✅ Live at `https://youtube-workout-planner-production.up.railway.app`
  - Health check: `{"status":"ok"}`
  - OAuth redirect working (`/auth/google` → Google consent screen)
  - All env vars set and verified via `railway variables`
  - Railway CLI installed (`npm install -g @railway/cli`) and linked to project `endearing-abundance`
- **Vercel (frontend):** ✅ Live at `https://youtube-workout-planner-flame.vercel.app`
  - Branch: `feat/web-app`, root directory: `frontend`
  - `NEXT_PUBLIC_API_URL` set to Railway backend URL

## Deployment Bug Log

### Bug 1 — Railway 502 on all endpoints (root cause: wrong proxy port)
**Symptom:** `/health` returned 502 from external internet; `railway logs` showed internal health
check returning 200 OK; app was clearly running inside the container.
**Root cause:** Railway's reverse proxy was configured to route external traffic to port 8000
(the `${PORT:-8000}` default in the Dockerfile CMD), while Railway injects `PORT=8080` at
runtime, so uvicorn actually bound to 8080. The proxy → container path hit a closed port.
Internal Railway health probes (`100.64.x.x`) bypass the public proxy and connect directly to
the container, so they succeeded while all external traffic failed.
**Fix:** Railway dashboard → service Settings → Networking → changed proxy port from 8000 → 8080.
No redeploy needed; routing updated immediately.
**Also fixed proactively:**
- Added `postgres://` → `postgresql://` rewrite in `api/database.py` and `alembic/env.py`
  (Railway's Postgres service emits `postgres://` URLs; SQLAlchemy 2.x rejects this scheme)
- Pinned all previously unpinned deps in `requirements.txt` to prevent silent breakage on rebuild
- Added `exec` to Dockerfile CMD so uvicorn runs as PID 1 and receives SIGTERM cleanly

### Bug 2 — Post-OAuth redirect lands on homepage instead of dashboard/onboarding
**Symptom:** After Google sign-in, user redirected to homepage. Homepage calls `GET /auth/me`
which returns 401, so the landing page renders instead of redirecting to `/onboarding`.
**Root cause:** `SessionMiddleware` defaults to `SameSite=lax`. With `SameSite=lax`, the session
cookie set on the Railway domain is not forwarded on cross-origin `fetch` requests from Vercel.
The browser only sends it on top-level navigations, not programmatic API calls. So the session
cookie was set correctly after OAuth but never reached `GET /auth/me`.
**Fix:** `api/main.py` — set `same_site="none"` and `https_only=True` in production (detected via
`RAILWAY_ENVIRONMENT` env var). `SameSite=none` allows cross-origin cookie forwarding; `Secure`
flag is required by browsers whenever `SameSite=none` is used. Falls back to `SameSite=lax`
(no HTTPS required) for local dev.

## Future API Ideas
- `PATCH /plan/{day}` with null `video_id` to mark a day as rest for that week only
  (currently only supports swapping to another video — only worth adding with explicit UI)
- Cross-user channel dedup: shared `channels` table + `user_channels` join to avoid
  scanning the same YouTube channel N times. Documented in `docs/scaling.md`.
