# Scaling Vision — From CLI Tool to Web App

> **This is a living document.** It captures the current thinking on how to evolve the architecture towards a multi-user web product. It will be updated as decisions are made and prototyping begins.

---

## Related Docs

- [market-research.md](./market-research.md) — competitive landscape, PMF analysis, closest competitors
- [testing.md](./testing.md) — test plan and "done when" criteria per phase
- [infra-research.md](./infra-research.md) — hosting, scheduler, frontend, API decisions

---

## Problem Statement

The current tool works well for a single technical user comfortable editing YAML files, running Python scripts locally, and managing GitHub Secrets. The goal is to make the same functionality available to anyone — no terminal, no config files, no developer account required.

A non-technical user should be able to:
1. Sign up and connect their YouTube account in a browser
2. Add the channels they follow by searching for them by name
3. Set their weekly training schedule via a visual interface
4. Get a workout playlist automatically refreshed every week, same as today

---

## Current Architecture (Baseline)

See [ARCHITECTURE.md](./ARCHITECTURE.md) for the full breakdown. The key constraints of the current design that need to change for multi-user:

| Current | Problem at scale |
|---|---|
| `config.yaml` for channels + schedule | One file, one user |
| SQLite committed to repo | Can't be shared across users or servers |
| GitHub Actions as scheduler | Tied to one repo, one user |
| `scripts/get_oauth_token.py` run locally | Requires terminal, not user-friendly |
| GitHub Secrets for credentials | Per-repo, not per-user |

---

## Target Architecture

### High-Level

```
Browser (Web App)
      │
      ▼
REST API  (FastAPI)
      │
 ┌────┴──────────────────────────────┐
 │                                   │
PostgreSQL                    Task Queue (Celery + Redis)
(users, channels,                    │
 videos, schedules,        ┌─────────┴──────────┐
 classifications,           │                    │
 history)               Scanner             Classifier
                            │                    │
                        Planner ─────────── Playlist
                                            (OAuth per user)
```

### Layers

| Layer | Technology (proposed) | Notes |
|---|---|---|
| Frontend | React (or lightweight alternative) | TBD — keep simple to start |
| API | FastAPI | Natural fit, already Python |
| Database | PostgreSQL | Multi-tenant, replaces SQLite |
| Task queue | Celery + Redis | Async jobs for scan/classify |
| Auth | OAuth 2.0 (Google) | Users sign in with Google — same account as their YouTube |
| Hosting | TBD | Not decided yet |

---

## User Journey (Target)

### First-time setup
1. User visits the web app and clicks **Sign in with Google**
2. OAuth consent screen — user grants access to their YouTube account
3. Onboarding flow:
   - Search for and add channels they follow
   - Configure their weekly schedule (visual week grid)
   - Set playlist preferences (name, visibility)
4. App triggers initial scan + classification in the background
5. User sees progress; gets notified when library is ready
6. First plan is generated and playlist is populated on YouTube

### Every week (automated)
- Scheduler runs incrementally for each user (equivalent of today's GitHub Actions cron)
- New videos discovered, classified, plan generated, playlist refreshed
- User opens YouTube on Monday — playlist is already updated

### Ongoing
- User can preview and tweak next week's plan before it publishes
- User can manually swap a video for a day
- User can add/remove channels at any time

---

## Data Model Changes

The core tables from the current schema carry over, extended with a `users` table and foreign keys:

```
users
  id            UUID PK
  google_id     TEXT UNIQUE        -- from OAuth
  email         TEXT
  display_name  TEXT
  created_at    TIMESTAMP

channels                           -- replaces config.yaml [channels]
  id            UUID PK
  user_id       UUID FK → users
  name          TEXT
  youtube_url   TEXT
  youtube_channel_id TEXT
  added_at      TIMESTAMP

videos                             -- largely unchanged
  id            TEXT PK            -- YouTube video ID
  channel_id    UUID FK → channels
  title, description, duration_sec, published_at, url, tags ...

classifications                    -- unchanged
  video_id      TEXT PK FK → videos
  workout_type, body_focus, difficulty, has_warmup, has_cooldown, classified_at ...

schedules                          -- replaces config.yaml [schedule]
  id            UUID PK
  user_id       UUID FK → users
  day           TEXT               -- monday … sunday
  workout_type  TEXT
  body_focus    TEXT
  duration_min  INT
  duration_max  INT
  difficulty    TEXT

program_history                    -- extended with user_id
  id            UUID PK
  user_id       UUID FK → users
  week_start    DATE
  video_id      TEXT FK → videos
  assigned_day  TEXT
  completed     BOOLEAN

user_credentials                   -- stores OAuth tokens server-side
  user_id               UUID PK FK → users
  youtube_refresh_token TEXT (encrypted)
  anthropic_key         TEXT       -- or use a shared platform key
  updated_at            TIMESTAMP
```

---

## API Surface (Draft)

### Auth
```
GET  /auth/google              → redirect to Google OAuth
GET  /auth/google/callback     → exchange code, create session
POST /auth/logout
```

### Channels
```
GET    /channels               → list user's channels
POST   /channels               → add a channel (triggers background scan)
DELETE /channels/:id           → remove channel
GET    /channels/search?q=     → search YouTube for a channel by name
```

### Schedule
```
GET  /schedule                 → get user's current weekly schedule
PUT  /schedule                 → update full schedule (replace)
```

### Library
```
GET /library                   → browse classified videos (filterable)
GET /library/stats             → count by type/focus/channel
PATCH /library/:video_id       → manually correct a classification
```

### Plan
```
GET  /plan/upcoming            → get next week's generated plan
POST /plan/generate            → re-generate (discards current draft)
POST /plan/publish             → push to YouTube playlist
PATCH /plan/:day               → swap video for a specific day
GET  /plan/history             → past weeks
```

### Jobs (internal / admin)
```
GET /jobs/:id                  → poll background job status (scan, classify)
```

---

## Pipeline Changes

The four pipeline stages stay logically identical. What changes is how they're invoked and scoped:

| Stage | Current | Target |
|---|---|---|
| **Discover** | `scan_all_channels()` called from CLI | Celery task, scoped to a `user_id`, triggered on channel add or weekly cron |
| **Understand** | `classify_unclassified_batch()` called from CLI | Celery task, runs after scan completes (chained), scoped to unclassified videos for a user |
| **Plan** | `generate_weekly_plan(config)` | Same logic, config replaced by DB query for user's schedule |
| **Publish** | `refresh_playlist()` called from CLI | Same logic, OAuth credentials loaded from `user_credentials` table |

The core logic in each module (scoring, fallback tiers, Batch API usage, playlist management) does not need to change — it's the invocation layer and config source that changes.

---

## YouTube OAuth — Key Change

Currently: user runs `scripts/get_oauth_token.py` locally, copies 3 values into GitHub Secrets.

Target: standard browser-based OAuth flow:
1. User clicks "Connect YouTube" in the web app
2. Redirected to Google consent screen
3. On approval, the server exchanges the auth code for access + refresh tokens
4. Refresh token stored encrypted in `user_credentials`
5. Each time a user's playlist needs updating, the server refreshes the token silently

No terminal, no copy-pasting, no secrets management by the user.

---

## Open Questions

See [infra-research.md](./infra-research.md) for the full research and recommendations on the questions below.

- **Hosting:** Railway for v1 (fast, usage-based, all services in one project); Render for v2+ (stable billing, autoscaling). → [infra-research.md § Hosting](./infra-research.md#hosting)
- **Shared vs user-supplied Anthropic key:** Shared platform key for v1 with a per-user cap; user-supplied key optional for power users. → [infra-research.md § Anthropic API](./infra-research.md#anthropic-api--shared-vs-user-supplied-key)
- **Frontend complexity:** HTMX (simplest) or Next.js on Vercel (faster to build with AI tooling). → [infra-research.md § Frontend](./infra-research.md#frontend)
- **Multi-user scheduler:** Celery Beat — no extra infrastructure needed; scoped per `user_id`. → [infra-research.md § Scheduler](./infra-research.md#scheduler)
- **YouTube API quota:** Not a blocker for v1; single key covers ~10 users. Per-user keys or quota increase before scaling past that. → [infra-research.md § YouTube API quota](./infra-research.md#youtube-api-quota)
- **Playlist ownership / revoked access:** On OAuth 401, mark credentials invalid, skip run, leave playlist at last good state, notify user by email + in-app banner. → [infra-research.md § Playlist ownership](./infra-research.md#playlist-ownership--revoked-access)
- **Free tier / pricing:** BYOK for v1 (user supplies Anthropic key); switch to platform-pays flat subscription when targeting less technical users. → [infra-research.md § Free tier / pricing](./infra-research.md#free-tier--pricing)

---

## Prototyping Plan

Suggested order — each phase is independently useful and builds on the previous.
See [testing.md](./testing.md) for the full test plan and "done when" criteria per phase.

### Pre-Phase 1 — Test suite for existing codebase
- Write `tests/` covering existing CLI pipeline (db, scanner, classifier, planner)
- Goal: pytest green before starting web app work

### Phase 1 — Backend foundation
- Set up FastAPI project structure
- PostgreSQL schema (users, channels, schedules, videos, classifications, history)
- Auth: Google OAuth login, session management
- Port existing pipeline logic to work against the DB instead of `config.yaml`

### Phase 2 — Core API
- Channel management endpoints (add, remove, scan trigger)
- Schedule endpoints
- Plan generation and retrieval

### Phase 3 — Background jobs
- Celery + Redis setup
- Scan and classify as async tasks with progress tracking
- Weekly cron per user

### Phase 4 — Frontend
- Onboarding flow (connect YouTube, add channels, set schedule)
- Plan preview and manual swap
- Library browser

### Phase 5 — Playlist publishing
- Server-side YouTube OAuth flow
- Automated weekly publish

---

*Last updated: 2026-03-07*
