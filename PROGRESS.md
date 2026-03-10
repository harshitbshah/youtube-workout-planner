# Progress

## Status
Phases 1–5 complete + deployment live + post-deploy fixes + pipeline reliability + E2E bug fixes complete.
**227/227 tests passing.**
Both Railway (backend) and Vercel (frontend) live and functional.
First plan loading successfully end-to-end. Ready for E2E checklist testing.

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

### Pipeline reliability + UX (2026-03-09) — complete

**Bug fixes:**
- `_run_full_pipeline` skipped classification when `total_new == 0` (incremental scan) —
  previously failed classifications never retried. Fix: always run `classify_for_user`
  (it's a no-op if nothing to classify)
- Plan with all null days caused UX loop: "Regenerate" button called `POST /plan/generate`
  (no scan) → still empty. Fix: detect all-null plan → show "Rescan channels" button instead

**Pipeline improvements:**
- `GET /jobs/status` endpoint — returns current stage + classify progress (total/done)
- In-memory `_pipeline_status` dict updated at each stage (scanning/classifying/generating/done/failed)
- `classify_for_user` accepts `on_progress` callback — called during transcript fetch phase
  (every 10 videos, negative done = still building) and during Anthropic batch polling
- Batch size capped at 300 videos per run — defers remainder to next scan, keeps first-run
  time manageable (~5 min transcript fetch vs 20+ min for 1000+ videos)
- Resumable batches: `classifier_batch_id` persisted in `user_credentials` (migration 003).
  On restart, resumes polling or retrieves results directly — no resubmission, no double billing

**Scanner pre-classification filters** (reduce Anthropic API cost):
- Title keyword blocklist: skips meal/recipe/vlog/q&a/podcast/unboxing/giveaway/transformation
  etc before fetching video details (no extra API calls)
- Livestream/premiere filter: skips `liveBroadcastContent=live/upcoming` (free, in playlist API)
- Upper duration cap: skips videos > 2 hours (livestreams/podcasts)
- Existing: < 3 min (Shorts) + `#shorts` hashtag filters preserved

**Dashboard UX:**
- Live scanning banner with stage-specific messages (scanning/classifying/generating/failed)
- Progress bar + `X / N done` count during classification batch polling
- Building phase shows `Preparing batch — fetching transcripts (X / N)` with progress bar
- Dashboard auto-detects running pipeline on mount (handles externally triggered scans)
- Polling interval reduced from 15s → 5s during scanning

**Tests:** 227/227 (was 216). New tests for: GET /jobs/status, duration cap, classify cap,
on_progress callback, batch resume logic, batch ID cleared on completion.

## Next
- Complete E2E testing (Groups 1–7 in `docs/testing.md`)
- Rename Vercel project to shorter URL (e.g. `myworkoutplan.vercel.app`)
- Publish Google OAuth app (removes "unverified" warning for basic scopes)
- Once E2E passes: share with first users

### E2E bug fixes (2026-03-09) — complete

**Bug fixes:**
- Dashboard polling stopped when stale plan existed (`if (!scanning || plan) return` short-circuit).
  Fix: poll based on pipeline stage only — stop when stage is `done`/`failed`/`null`.
- Planner returned all Rest days — `NOT IN` subquery included NULL `video_id` rows from Rest days,
  making condition always false in SQL. Fix: added `video_id.is_not(None)` filter.
- Publisher crashed with 404 on newly created playlist — YouTube API has propagation delay.
  Fix: skip `clear_playlist` for new playlists (they're empty anyway).
- Classifier crashed saving results for videos deleted after batch submission.
  Fix: check video exists in DB before inserting classification.
- Page title still showed "Create Next App" — layout.tsx change was never committed.
  Fix: committed and pushed.

**Cleanup:**
- `scripts/cleanup_false_positives.py` — one-off script to remove pre-filter false positives from DB.
  Deleted 93 HASfit videos (recipes, vlogs, reviews, giveaways) from production. 1,076 remain.
- Cleared stale `program_history` entries (14 all-null rows from broken planner runs).
- Cleared stale `youtube_playlist_id` from user_credentials (pointing to deleted playlist).

**Docs:**
- Updated all docs: `testing.md` (227 tests), `architecture.md` (schema, scanner filters,
  batch cap, resumable batches, dashboard UX), `CLAUDE.md` (GET /jobs/status route),
  `backlog.md` (5s polling), `user-guide.md` (scan stages, non-workout filters).

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
