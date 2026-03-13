# YouTube Workout Planner — Claude Instructions

## Session Start
1. Read `PROGRESS.md` for current status and next steps
2. Run `git log --oneline -10` to see recent commits
3. Continue from where the last session left off

## Checkpoint — MANDATORY when user says "checkpoint"

When the user says "let's checkpoint" or "take a checkpoint", run the following in order:

**Step 0: Run `/simplify`** — code review and cleanup before locking anything in.
Wait for it to complete and fix all findings before proceeding to the doc updates below.

1. **`PROGRESS.md`** — update status line, test count, and add a dated section summarising
   everything built/fixed this session. Keep it factual and scannable (bullet points).

2. **`docs/architecture.md`** — update if any routes, pages, components, or DB schema changed.

3. **`docs/backlog.md`** — append any new ideas or deferred work that surfaced this session.

4. **`docs/testing.md`** — add new features/pages to the manual checklist if applicable.

5. **`CLAUDE.md` itself** — update the API routes table and file map if new routes or files
   were added.

6. **Claude's memory** (`~/.claude/projects/.../memory/MEMORY.md`) — update status line,
   test count, and any key architectural facts that changed.

7. **Commit all doc changes** with message: `docs: checkpoint — <one-line summary> (<date>)`

The goal: any future session (or a knowledge agent) can read these docs and fully understand
the current state without needing conversation history.

## Testing — MANDATORY

Every code change that adds or modifies backend behaviour **must** include:

1. **Unit test** in `tests/api/` — fast, uses SQLite in-memory, mocks external calls.
   - Test happy path, auth failure (401), and key error cases (400/404/503).
2. **Integration test** in `tests/integration/` — runs against real PostgreSQL.
   - Verify the DB-level behaviour (FK constraints, correct rows written, user isolation).

Run both suites before committing:
```bash
.venv/bin/pytest tests/api/ -q          # unit
.venv/bin/pytest tests/integration/ -q  # integration
```

All tests must pass (0 failures) before any commit. Never skip or defer tests to "add later".

## Maintaining Docs

**PROGRESS.md** — update before every commit. Keep it lean (current state only, no history).
- Check off tasks as completed
- When a phase is done, replace it with the next phase's tasks

**docs/architecture.md** — update whenever routes, pages, components, or DB schema change.
The web app section must stay in sync with the actual codebase.

**docs/testing.md** — add new pages/features to the Phase manual checklist when built.
Delete checklist items as verified; delete the section when fully ticked.

**docs/google-oauth-setup.md** — update if OAuth scopes or the publish flow changes.

**docs/infra-research.md** — mark decisions as "made" when they are; add new decisions as they arise.

**docs/backlog.md** — append new ideas here mid-session whenever something worth
capturing surfaces. Review before starting a new phase.

**docs/user-guide.md** — update when user-facing features are added or change behaviour.
Covers current features only (no speculative content), written for a non-technical reader.

**CLAUDE.md itself** — update the API routes table, file map, and user flows whenever
new routes or pages are added.

### Docs ↔ Admin guide relationship

`docs/` files are the **full source-of-truth** reference documents (detailed, comprehensive).
`frontend/src/app/admin/guide/page.tsx` surfaces **curated operational summaries** of those docs
in the web portal for quick in-app access.

Convention:
- `docs/` is always updated first — it is the canonical record.
- The admin guide sections are summaries, not full copies — do not paste entire docs into the guide.
- Only update the admin guide section for a doc when the change is **operationally significant**
  (e.g. a new stack decision, a new Railway gotcha, a new known limit). Routine feature additions
  do not need an admin guide update.
- When in doubt: update `docs/` always, update the admin guide only if an operator reading it
  mid-incident would need the new information.

---

## Project Overview

Two distinct things live in this repo:

### 1. Original CLI tool (`main.py`, `src/`, `config.yaml`)
Single-user Python script that runs on GitHub Actions every Sunday:
scan channels → classify with Claude → generate plan → update YouTube playlist.
This is **feature-complete and in production**. Do not touch unless explicitly asked.

### 2. Web app — the active focus (`api/`, `frontend/`, `alembic/`, `tests/`)
Multi-user FastAPI + Next.js web application. This is what we are building.
See `docs/architecture.md` for full design.

---

## Web App — Running Locally

```bash
# Backend (from repo root)
cd ~/Projects/youtube-workout-planner
source .venv/bin/activate
set -a && source .env && set +a      # IMPORTANT: set -a exports vars to subprocesses
.venv/bin/uvicorn api.main:app --reload

# Frontend (separate terminal)
cd ~/Projects/youtube-workout-planner/frontend
npm run dev
```

API: `http://localhost:8000` | Swagger: `http://localhost:8000/docs`
Frontend: `http://localhost:3000`

## Web App — Tests

```bash
# Unit tests (SQLite in-memory, no external deps)
.venv/bin/pytest tests/api/ tests/test_*.py -v

# Integration tests (real PostgreSQL — requires workout_planner_test DB)
.venv/bin/pytest tests/integration/ -v

# All backend tests
.venv/bin/pytest -q

# Frontend tests (Vitest + React Testing Library)
cd frontend && npm run test:run
```

---

## Web App — Key Files

### Backend (`api/`)
| File | Purpose |
|---|---|
| `api/main.py` | FastAPI app, CORS, middleware, router registration |
| `api/models.py` | SQLAlchemy ORM models (User, Channel, Video, Classification, Schedule, ProgramHistory, UserCredentials, BatchUsageLog, Announcement, ScanLog, UserActivityLog) |
| `api/schemas.py` | Pydantic request/response schemas |
| `api/dependencies.py` | `get_db`, `get_current_user` (+ last_active_at throttled update) FastAPI dependencies |
| `api/database.py` | SQLAlchemy engine + session factory |
| `api/crypto.py` | Fernet encryption for credentials at rest |
| `api/scheduler.py` | APScheduler weekly cron (replaces GitHub Actions for web users) |
| `api/routers/auth.py` | Google OAuth login/logout + `GET/PATCH/DELETE /auth/me` |
| `api/routers/channels.py` | `GET/POST /channels`, `DELETE /channels/{id}`, `GET /channels/search` |
| `api/routers/schedule.py` | `GET/PUT /schedule` |
| `api/routers/plan.py` | `GET /plan/upcoming`, `POST /plan/generate`, `PATCH /plan/{day}`, `POST /plan/publish` |
| `api/routers/library.py` | `GET /library` — paginated, filtered video browser |
| `api/routers/jobs.py` | `POST /jobs/scan`, `GET /jobs/status`, `get_all_pipeline_statuses()` |
| `api/routers/admin.py` | Admin stats, user management, announcements (ADMIN_EMAIL gated) |
| `api/services/scanner.py` | YouTube channel scanning (uses `src/scanner.py` internals) |
| `api/services/classifier.py` | Video classification via Anthropic Batch API; records BatchUsageLog |
| `api/services/planner.py` | Weekly plan generation (uses `src/planner.py`) |
| `alembic/` | Database migrations (currently at 004) |

### Frontend (`frontend/src/`)
| Path | Purpose |
|---|---|
| `app/page.tsx` | Landing/marketing page (hero, how it works, features, CTA, Guide nav link) |
| `app/onboarding/page.tsx` | 7-step onboarding wizard: life stage → goal → training days → session length → schedule preview → channels → live scan progress |
| `app/dashboard/page.tsx` | Weekly plan grid, responsive header, announcement banner, admin nav link |
| `app/library/page.tsx` | Video library browser with filters + assign-to-day |
| `app/settings/page.tsx` | Profile, channels, schedule, account deletion |
| `app/guide/page.tsx` | User guide with sticky sidebar nav (7 sections) |
| `app/admin/page.tsx` | Admin console: stats, user table, announcements (admin only) |
| `app/admin/guide/page.tsx` | Admin operational guide: admin console, managing users, announcements, monitoring, troubleshooting, railway ops, DB reference, env vars, known issues |
| `lib/api.ts` | All API calls + TypeScript types |
| `lib/scheduleTemplates.ts` | `buildSchedule()` — generates ScheduleSlot[] from profile, goal, days, duration |
| `lib/utils.ts` | Shared `DAY_LABELS` constant + `formatDuration()` utility |
| `components/ChannelManager.tsx` | Reusable channel search/add/remove; optional `suggestions` prop for curated chips (used in onboarding + settings) |
| `components/Badge.tsx` | Shared styled badge pill (used in dashboard + library) |
| `components/ScheduleEditor.tsx` | Reusable weekly schedule grid (used in onboarding + settings) |
| `components/Tooltip.tsx` | CSS-only tooltip component (`group/tip` pattern, `delay-300`) |
| `components/Footer.tsx` | Shared footer with YouTube API attribution; accepts optional `isAdmin` prop — shows "Admin Guide" link beside "User Guide" on admin pages |

---

## Web App — API Routes Summary

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/health` | No | Health check |
| GET | `/auth/google` | No | Redirect to Google OAuth |
| GET | `/auth/google/callback` | No | OAuth callback, set session |
| GET | `/auth/me` | Yes | Current user profile |
| PATCH | `/auth/me` | Yes | Update display name |
| PATCH | `/auth/me/notifications` | Yes | Update email_notifications preference |
| DELETE | `/auth/me` | Yes | Delete account + all data |
| POST | `/auth/logout` | Yes | Clear session |
| GET | `/channels` | Yes | List user's channels |
| POST | `/channels` | Yes | Add channel |
| DELETE | `/channels/{id}` | Yes | Remove channel |
| GET | `/channels/search?q=` | Yes | Search YouTube channels |
| GET | `/schedule` | Yes | Get weekly schedule |
| PUT | `/schedule` | Yes | Update weekly schedule |
| GET | `/plan/upcoming` | Yes | Latest generated plan |
| POST | `/plan/generate` | Yes | Generate/regenerate plan |
| PATCH | `/plan/{day}` | Yes | Swap a day's video |
| POST | `/plan/publish` | Yes | Publish plan to YouTube playlist |
| GET | `/library` | Yes | Paginated/filtered video library |
| POST | `/jobs/scan` | Yes | Trigger manual channel scan |
| GET | `/jobs/status` | Yes | Pipeline stage + classify progress `{stage, total, done}` |
| GET | `/announcements/active` | Yes | Active announcement or null (any auth'd user) |
| GET | `/admin/stats` | Admin | Aggregate stats + per-user rows |
| DELETE | `/admin/users/{id}` | Admin | Delete any user (blocks self-deletion) |
| POST | `/admin/users/{id}/scan` | Admin | Trigger pipeline for any user |
| GET | `/admin/announcements` | Admin | List all announcements |
| POST | `/admin/announcements` | Admin | Create announcement |
| DELETE | `/admin/announcements/{id}` | Admin | Delete announcement |
| PATCH | `/admin/announcements/{id}/deactivate` | Admin | Deactivate announcement |
| GET | `/admin/charts?days=N` | Admin | Daily time-series: signups, active users, AI cost, scans |

---

## Web App — User Flows

```
/ (landing page)
  ↓ [click "Get started free"]
Google OAuth → /auth/google → Google → /auth/google/callback → /

  → New user (no channels): /onboarding
      Step 1: Life stage (4 cards, auto-advance)
      Step 2: Goal (3–4 options by profile, auto-advance)
      Step 3: Training days (2–6 toggle, auto-advance)
      Step 4: Session length (4 options, auto-advance)
      Step 5: Schedule preview (confirm or customise with ScheduleEditor)
      Step 6: Channels (ChannelManager + curated suggestions by profile)
      Step 7: Live scan progress (polls /jobs/status, auto-navigates to /dashboard)

  → Returning user (has channels): /dashboard
      Header nav: Library | Settings | Regenerate | Publish | Admin (admin only) | Sign out
      Announcement banner (dismissible) shown if active announcement exists
      ↓ Library → /library
          Filters: workout type / body focus / difficulty / channel
          Cards: assign to plan day via PATCH /plan/{day}
      ↓ Settings → /settings
          Profile: edit display name, read-only email
          Channels: ChannelManager (add/remove)
          Schedule: ScheduleEditor + save
          Danger zone: delete account (2-step confirm)
      ↓ Admin (admin only) → /admin
          Stats: users, library size, AI token usage + cost
          Active pipelines monitor
          Per-user management: scan, delete
          Announcements: create/deactivate/delete

/ → nav "Guide" link → /guide
    User guide, 7 sections, sticky desktop sidebar
```

---

## Web App — Key Conventions

### Authentication
- Session cookie via Starlette `SessionMiddleware`
- `get_current_user` dependency raises 401 if no valid session
- All user data is strictly isolated by `user_id` (never cross-user leakage)

### Classifier output casing
The classifier stores `"Strength"`, `"HIIT"`, `"Cardio"`, `"Mobility"`, `"Other"` (mixed case).
The `GET /library` filter uses `func.lower()` on both sides for case-insensitive matching.
Frontend filter values are lowercase; display labels are set explicitly in `WORKOUT_TYPE_LABELS`.

### Credentials encryption
`UserCredentials.youtube_refresh_token` is Fernet-encrypted at rest.
`ENCRYPTION_KEY` env var must be set before starting the server (Fernet key, base64).
`ENCRYPTION_KEY` is checked at startup; the server refuses to start without it.

### Running .env
Always use `set -a && source .env && set +a` — plain `source .env` does not export
vars to subprocesses, so uvicorn (a subprocess) won't see them.

### Admin gating
`ADMIN_EMAIL` env var on Railway identifies the single admin user.
Read at request time inside `_require_admin()` (not at module import time) to allow
test isolation via `monkeypatch.setenv`. On Railway: set `ADMIN_EMAIL=harshitspeaks@gmail.com`.

### Test isolation
- Unit tests: SQLite in-memory, `StaticPool`, tables recreated per test
- Integration tests: real PostgreSQL (`workout_planner_test` DB), Alembic migrations,
  tables truncated between tests (schema preserved)

---

## Documentation Map

| Doc | Contents | Updated when |
|---|---|---|
| `PROGRESS.md` | Current phase status and next tasks | Every commit |
| `docs/architecture.md` | Full system design — CLI pipeline + web app API + data model | Routes, pages, schema change |
| `docs/testing.md` | Test philosophy + phase manual checklist | New features built or verified |
| `docs/user-guide.md` | Product readme for non-technical users | User-facing features added/changed |
| `docs/backlog.md` | Running list of ideas and future features | Mid-session as ideas surface |
| `docs/google-oauth-setup.md` | OAuth warning, how to publish app, sign-in checklist | OAuth scopes or publish flow changes |
| `docs/infra-research.md` | Hosting, scheduler, frontend, API key decisions | Decisions made or reconsidered |
| `docs/scaling.md` | Future scale considerations | Phase milestones or architecture shifts |
