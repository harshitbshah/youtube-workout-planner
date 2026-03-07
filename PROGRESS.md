# Progress

## Status
Starting Phase 1 — web app build. CLI tool is complete and running in production.
Full spec in `docs/scaling.md` and `docs/infra-research.md`.

## Current Phase — Pre-Phase 1: Test Suite for Existing Codebase ✓
Full plan in `docs/testing.md`.

- [x] Add pytest, httpx, pytest-asyncio to `requirements.txt`
- [x] `tests/conftest.py` — temp DB fixture (patches `db.DB_PATH` via monkeypatch)
- [x] `tests/test_db.py` — schema creation
- [x] `tests/test_scanner.py` — `_parse_duration` (pure), `_save_videos` (DB), scanner mocks
- [x] `tests/test_classifier.py` — `_parse_classification`, `_build_user_message` (pure), batch mock
- [x] `tests/test_planner.py` — pure functions + `pick_video_for_slot` (DB)
- [x] All tests green (`pytest tests/`) — 26/26 passed

## Phase 1: Backend Foundation
- [x] FastAPI app structure (`api/main.py`, routers, services)
- [x] PostgreSQL schema via Alembic (`alembic/versions/001_initial_schema.py`)
- [x] SQLAlchemy models — users, channels, videos, classifications, schedules, history, credentials
- [x] Google OAuth login + session management (`api/routers/auth.py`)
- [x] Planner service ported to PostgreSQL/SQLAlchemy (`api/services/planner.py`)
- [x] 51/51 unit tests green (25 API tests + 26 pre-existing)
- [x] Credential encryption at rest — Fernet AES encryption for `youtube_refresh_token` and `anthropic_key` (`api/crypto.py`)
- [x] Startup check — server refuses to start without `ENCRYPTION_KEY` set
- [x] **Manual E2E** — Google OAuth flow verified, user + encrypted refresh token confirmed in Postgres
- [x] **Integration tests** (`tests/integration/`) — 28/28 passing: schema verification, FK constraints, CASCADE deletes, DATE type behaviour, encryption round-trip, planner history window, user isolation

## Next Phase — Phase 2: Core API
- [ ] `GET/POST/DELETE /channels` — manage user's YouTube channels
- [ ] `GET /channels/search?q=` — search YouTube by channel name
- [ ] `GET/PUT /schedule` — get and update weekly training schedule
- [ ] `GET /plan/upcoming` — get next week's generated plan
- [ ] `POST /plan/generate` — trigger re-generation
- [ ] `PATCH /plan/:day` — swap video for a day
- [ ] Tests for all endpoints

## Upcoming Phases
- **Phase 2** — Core API (channels, schedule, plan endpoints)
- **Phase 3** — Background jobs (Celery + Redis, weekly cron per user)
- **Phase 4** — Frontend (onboarding, plan preview, library browser)
- **Phase 5** — Playlist publishing (server-side OAuth, revoked access handling)

## Blocked / Decisions Needed
- Frontend: HTMX vs Next.js on Vercel — undecided, choose before Phase 4
