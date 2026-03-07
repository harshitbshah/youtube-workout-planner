# Progress

## Current Status
Setup complete. System is running weekly in production via GitHub Actions.

## What's Done
- [x] Full pipeline working end-to-end (scan → classify → plan → publish)
- [x] YouTube API + OAuth configured
- [x] Anthropic Batch API classification integrated
- [x] GitHub Actions scheduled job live (Sundays 6pm UTC)
- [x] SQLite library auto-committed by CI after each run
- [x] Docs written: architecture, scaling vision, infra research

## Next Steps — Web App Build

The planned next phase is building the multi-user web app. Full spec in `docs/scaling.md` and `docs/infra-research.md`.

### Phase 1 — Backend foundation
- [ ] Set up FastAPI project structure
- [ ] PostgreSQL schema (users, channels, schedules, videos, classifications, history, user_credentials)
- [ ] Google OAuth login + session management
- [ ] Port pipeline logic to read from DB instead of `config.yaml`

### Phase 2 — Core API
- [ ] Channel endpoints: add, remove, search YouTube by name
- [ ] Schedule endpoints: get/update weekly schedule
- [ ] Plan endpoints: generate, retrieve, publish, swap day

### Phase 3 — Background jobs
- [ ] Celery + Redis setup
- [ ] Scan and classify as async tasks with progress tracking
- [ ] Weekly cron per user (Celery Beat, scoped by `user_id`)

### Phase 4 — Frontend
- [ ] Onboarding flow (connect YouTube, add channels, set schedule, BYOK Anthropic key)
- [ ] Plan preview + manual day-swap
- [ ] Library browser

### Phase 5 — Playlist publishing
- [ ] Server-side YouTube OAuth flow (no more local `get_oauth_token.py`)
- [ ] Automated weekly publish per user
- [ ] Handle revoked access: mark invalid, skip run, email + in-app banner

## Stack Decisions (already made)
| Layer | Decision |
|---|---|
| API | FastAPI |
| Database | PostgreSQL (Railway v1, Render v2+) |
| Task queue + scheduler | Celery + Redis |
| Auth | Google OAuth |
| Frontend | HTMX or Next.js on Vercel (TBD) |
| Hosting v1 | Railway (usage-based, all services in one project) |
| Anthropic | BYOK for v1 (user pastes `sk-ant-...` during onboarding) |
| YouTube API | Shared key to start; per-user or quota increase past ~10 users |

## Notes
- YouTube playlist revoked access is a known limitation — documented in `docs/infra-research.md`
- BYOK (Bring Your Own Key) model chosen over hosted API to avoid per-user Anthropic costs
- Channel back-catalogue classification cost: ~$1–2 one-time; weekly incremental: cents

## Session Log
| Date | What happened |
|---|---|
| 2026-03-07 | Added CLAUDE.md and PROGRESS.md for session continuity |
