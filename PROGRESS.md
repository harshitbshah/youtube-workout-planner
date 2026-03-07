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

## Current Phase — Phase 2: Core API
- [x] `api/schemas.py` — Pydantic request/response models for all Phase 2 endpoints
- [x] `GET/POST/DELETE /channels` — `api/routers/channels.py`
- [x] `GET /channels/search?q=` — YouTube Data API v3 search (requires `YOUTUBE_API_KEY`)
- [x] `GET/PUT /schedule` — `api/routers/schedule.py`
- [x] `GET /plan/upcoming` — most recent generated plan
- [x] `POST /plan/generate` — trigger re-generation (clears + rebuilds current week)
- [x] `PATCH /plan/:day` — swap video for a day (upserts `ProgramHistory`)
- [x] Routers registered in `api/main.py`
- [x] Tests written — `tests/api/test_channels.py`, `test_schedule.py`, `test_plan.py`
- [ ] **Tests need to pass** — pytest environment issue on this machine; run `pytest tests/` locally to verify

## Upcoming Phases
- **Phase 2** — Core API (channels, schedule, plan endpoints)
- **Phase 3** — Background jobs (Celery + Redis, weekly cron per user)
- **Phase 4** — Frontend (onboarding, plan preview, library browser)
- **Phase 5** — Playlist publishing (server-side OAuth, revoked access handling)

## Blocked / Decisions Needed
- Frontend: HTMX vs Next.js on Vercel — undecided, choose before Phase 4

## Future API Ideas
- `PATCH /plan/{day}` with null `video_id` to mark a scheduled day as rest for that week only.
  Currently only supports swapping to another video. Only worth adding if the frontend has an explicit
  "skip this day" UX — otherwise the schedule already handles structural rest days.
