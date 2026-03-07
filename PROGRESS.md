# Progress

## Status
Phases 1 and 2 complete. 129/129 tests passing. Starting Phase 3 — background jobs.

## Current Phase — Phase 3: Background Jobs
- [ ] Scanner service ported to PostgreSQL/SQLAlchemy (`api/services/scanner.py`)
- [ ] Classifier service ported to PostgreSQL/SQLAlchemy (`api/services/classifier.py`)
- [ ] `POST /channels/{id}/scan` — trigger channel scan for a user
- [ ] Weekly cron job — scan + classify + generate plan for all users every Sunday
- [ ] Job queue (Celery + Redis) or lightweight alternative — decision needed
- [ ] Tests for scanner and classifier services

## Upcoming Phases
- **Phase 4** — Frontend (onboarding, plan preview, library browser)
- **Phase 5** — Playlist publishing (server-side OAuth, revoked access handling)

## Blocked / Decisions Needed
- Frontend: HTMX vs Next.js on Vercel — undecided, choose before Phase 4

## Future API Ideas
- `PATCH /plan/{day}` with null `video_id` to mark a scheduled day as rest for that week only.
  Currently only supports swapping to another video. Only worth adding if the frontend has an explicit
  "skip this day" UX — otherwise the schedule already handles structural rest days.
