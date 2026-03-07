# Progress

## Status
Starting Phase 1 — web app build. CLI tool is complete and running in production.
Full spec in `docs/scaling.md` and `docs/infra-research.md`.

## Current Phase — Phase 1: Backend Foundation
- [ ] Set up FastAPI project structure
- [ ] PostgreSQL schema (users, channels, schedules, videos, classifications, history, user_credentials)
- [ ] Google OAuth login + session management
- [ ] Port pipeline logic to read from DB instead of `config.yaml`

## Upcoming Phases
- **Phase 2** — Core API (channels, schedule, plan endpoints)
- **Phase 3** — Background jobs (Celery + Redis, weekly cron per user)
- **Phase 4** — Frontend (onboarding, plan preview, library browser)
- **Phase 5** — Playlist publishing (server-side OAuth, revoked access handling)

## Blocked / Decisions Needed
- Frontend: HTMX vs Next.js on Vercel — undecided, choose before Phase 4
