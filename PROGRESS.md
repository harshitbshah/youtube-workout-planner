# Progress

## Status
Phases 1–3 complete. 160/160 tests passing. Starting Phase 4 — Frontend.

## Current Phase — Phase 4: Frontend
- [ ] Choose frontend stack (HTMX vs Next.js on Vercel) — decision needed before starting
- [ ] Onboarding flow (sign in with Google, add channels, set schedule)
- [ ] Plan preview page (view next week's plan, swap days)
- [ ] Library browser (browse/filter classified videos)
- [ ] "Publish to YouTube" button (manual publish as engagement gate)

## Upcoming Phases
- **Phase 5** — Playlist publishing (server-side OAuth, `POST /plan/publish`, revoked access handling)

## Blocked / Decisions Needed
- Frontend stack: HTMX (simpler) vs Next.js on Vercel (faster to build with AI tooling) — decide before Phase 4

## Future API Ideas
- `PATCH /plan/{day}` with null `video_id` to mark a scheduled day as rest for that week only.
  Currently only supports swapping to another video. Only worth adding if the frontend has an explicit
  "skip this day" UX — otherwise the schedule already handles structural rest days.
- Cross-user channel dedup: shared `channels` table + `user_channels` join table to avoid scanning
  the same YouTube channel N times for N users. Documented in `docs/scaling.md`. Pre-scale work.
