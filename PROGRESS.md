# Progress

## Status
Phases 1–5 complete. 206/206 tests passing.
Manual testing for Phase 4 + 5 deferred — ready to do now.

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

## Next
- Debug Railway 502 on `/auth/google` and `/auth/me` — backend crashes after handling OAuth requests
  - Health check passes after deploy but service goes down mid-session
  - Need to find runtime logs (not build logs) in Railway to see traceback
- E2E testing once Railway is stable

## Deployment Status
- **Railway (backend):** ⚠️ Unstable — starts healthy but 502s on OAuth endpoints
  - DB migrations ran (001 + 002), APScheduler running, health check passes on deploy
  - All env vars set: `ENCRYPTION_KEY`, `DATABASE_URL`, `SESSION_SECRET_KEY`, `GOOGLE_CLIENT_ID`,
    `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI`, `YOUTUBE_API_KEY`, `ANTHROPIC_API_KEY`,
    `FRONTEND_URL`, `FRONTEND_ORIGINS`
- **Vercel (frontend):** ✅ Live at `https://youtube-workout-planner-flame.vercel.app`
  - Branch set to `feat/web-app`, root directory set to `frontend`
  - `NEXT_PUBLIC_API_URL` set to Railway backend URL
  - Fixed `vercel.json` — removed invalid `rootDirectory` property (moved to dashboard setting)

## Future API Ideas
- `PATCH /plan/{day}` with null `video_id` to mark a day as rest for that week only
  (currently only supports swapping to another video — only worth adding with explicit UI)
- Cross-user channel dedup: shared `channels` table + `user_channels` join to avoid
  scanning the same YouTube channel N times. Documented in `docs/scaling.md`.
