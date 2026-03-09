# Progress

## Status
Phases 1–5 complete + deployment live + critical post-deploy bugs fixed.
**216/216 tests passing.**
Both Railway (backend) and Vercel (frontend) live and functional.
E2E testing in progress.

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

### Post-deploy fixes (2026-03-09) — complete
See "Deployment Bug Log" below for full diagnosis.

**Infrastructure:**
- `api/database.py` + `alembic/env.py`: rewrite `postgres://` → `postgresql://` at runtime
- `requirements.txt`: pinned all unpinned deps
- `Dockerfile`: added `exec` before `uvicorn` so it runs as PID 1
- Railway dashboard: proxy port corrected from 8000 → 8080

**Auth — cross-domain cookie replacement:**
- Replaced `SameSite=lax` session cookies with URL token handoff
- OAuth callback now redirects to `{FRONTEND_URL}?token=<signed_token>` (itsdangerous)
- Frontend extracts token from URL, stores in `localStorage`, sends as `Authorization: Bearer`
- `api/dependencies.py` checks Bearer token first, falls back to session cookie
- Tokens expire after 30 days; signed with `SESSION_SECRET_KEY`

**UX — scan progress:**
- `POST /jobs/scan` router prefix was missing (`/scan` → `/jobs/scan`) — endpoint was
  silently 404-ing on every "Generate plan" click since it was added
- `api/routers/jobs.py` fixed: `router = APIRouter(prefix="/jobs", ...)`
- Dashboard "Generate plan" (no plan yet) now calls `POST /jobs/scan` (full background
  pipeline) showing a scanning banner + polls `GET /plan/upcoming` every 15s
- Dashboard "Regenerate" (plan exists) calls `POST /plan/generate` (fast, synchronous)
  showing an inline "Generating…" banner while in flight
- Onboarding → redirects to `/dashboard?scanning=1` after triggering scan; dashboard
  reads this flag on mount to start scanning state without an extra API call

**Tests:**
- 5 new unit tests for `POST /jobs/scan` in `tests/api/test_jobs.py`
- 5 new integration tests in `tests/integration/test_jobs_api.py` (new file)
- Updated all tests using old per-channel route (`/channels/{id}/scan` → `/jobs/channels/{id}/scan`)
- `CLAUDE.md`: mandatory unit + integration test rule added; must pass before every commit

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
**Symptom:** `/health` returned 502 from external internet; internal health checks returned 200.
**Root cause:** Railway proxy routing to port 8000; app bound to `PORT=8080` (Railway-injected).
Internal probes (`100.64.x.x`) bypass the public proxy — misleading green health check.
**Fix:** Railway dashboard → Settings → Networking → changed proxy port 8000 → 8080.

### Bug 2 — Post-OAuth redirect lands on homepage (SameSite=lax)
**Root cause:** `SameSite=lax` blocks cross-origin fetch. Session cookie set on Railway domain
never reached `GET /auth/me` from Vercel fetch calls.
**Attempted fix:** `SameSite=none; Secure` — worked briefly, then broke in Chrome (third-party
cookie deprecation, 2024).
**Final fix:** Dropped cookies entirely for cross-domain auth. OAuth callback redirects to
`{FRONTEND_URL}?token=<signed_token>`. Frontend stores in `localStorage` and sends as
`Authorization: Bearer`. No cookies needed across domains.

### Bug 3 — POST /jobs/scan was 404 (missing router prefix)
**Symptom:** "Generate plan" and "Scan channels" clicks silently failed; error state showed
nothing because the scan ran in a background context where errors weren't surfaced.
**Root cause:** `router = APIRouter(tags=["jobs"])` had no prefix. Endpoint was registered
at `/scan`, not `/jobs/scan`. The frontend always called `/jobs/scan`.
**Fix:** `router = APIRouter(prefix="/jobs", tags=["jobs"])`.

## Future API Ideas
- `PATCH /plan/{day}` with null `video_id` to mark a day as rest for that week only
  (currently only supports swapping to another video — only worth adding with explicit UI)
- Cross-user channel dedup: shared `channels` table + `user_channels` join to avoid
  scanning the same YouTube channel N times. Documented in `docs/scaling.md`.
