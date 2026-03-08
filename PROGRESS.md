# Progress

## Status
Phases 1–4 complete. 194/194 tests passing. Phase 5 upcoming.

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
- "Publish to YouTube" button on dashboard (disabled — wired in Phase 5)
- Shared components: `ChannelManager`, `ScheduleEditor` (reused in onboarding + settings)
- Backend: `PATCH /auth/me` (display name), `DELETE /auth/me` (account deletion)
- Bug fix: `GET /library` filters are case-insensitive (`func.lower`) — classifier stores
  mixed-case values ("HIIT", "Strength") but frontend sends lowercase

## Upcoming — Phase 5: Playlist Publishing
- `POST /plan/publish` backend endpoint
- Server-side YouTube OAuth using stored refresh token
- Handle revoked access (401 → mark credentials invalid, notify user, skip run)
- Enable "Publish to YouTube" button on dashboard
- In-app banner when YouTube access is revoked

## Future API Ideas
- `PATCH /plan/{day}` with null `video_id` to mark a day as rest for that week only
  (currently only supports swapping to another video — only worth adding with explicit UI)
- Cross-user channel dedup: shared `channels` table + `user_channels` join to avoid
  scanning the same YouTube channel N times. Documented in `docs/scaling.md`.
