# Architecture

## Overview

YouTube Workout Planner is a scheduled Python pipeline that runs weekly on GitHub Actions. It scans YouTube channels you follow, classifies every video using Claude AI, selects one video per training day based on your schedule, and pushes the result directly into a YouTube playlist.

The entire system is stateless between runs — all persistent state lives in a single SQLite file (`workout_library.db`) that gets committed back to the repo after each run.

---

## Pipeline

Every Sunday at 6pm UTC, the four stages run in sequence:

```
┌─────────────┐     ┌──────────────┐     ┌────────────┐     ┌──────────────┐
│   DISCOVER  │ --> │  UNDERSTAND  │ --> │    PLAN    │ --> │   PUBLISH    │
│  scanner.py │     │classifier.py │     │ planner.py │     │ playlist.py  │
└─────────────┘     └──────────────┘     └────────────┘     └──────────────┘
  Fetch new videos    Classify with        Pick one video      Clear + repopulate
  from each channel   Claude Haiku         per training day    YouTube playlist
  via YouTube API     Batch API            from the library    via OAuth
```

**Init mode** (`--init`) runs the same pipeline but does a full back-catalogue scan instead of an 8-day incremental one — used once when adding a new channel.

---

## Components

### `main.py` — Entry point

Parses CLI flags, loads `config.yaml`, and orchestrates the four stages. Four modes:

| Flag | What it does |
|---|---|
| `--init` | Full scan + full classify. Run once after setup. |
| `--classify-only` | Classify without re-scanning. Resumes interrupted classification. |
| `--run` | Weekly: incremental scan → classify → plan → publish. |
| `--dry-run` | Same as `--run` but skips the playlist update. |

---

### `src/scanner.py` — Discover

Resolves each channel URL to its uploads playlist ID, then paginates through it using `playlistItems.list`. Video details (duration, tags) are batch-fetched with `videos.list` (50 per API call).

Two modes:
- **Full scan** — fetches entire back-catalogue; used on `--init`
- **Incremental scan** — fetches only videos newer than `since_date` (8 days); uploads playlist is newest-first so pagination stops early

Deleted/private videos are filtered. New videos are `INSERT OR IGNORE`d into the `videos` table — safe to re-run.

**YouTube API quota:** ~20 units per 500 videos. Daily free quota is 10,000 units.

---

### `src/classifier.py` — Understand

Classifies every video in the `videos` table that has no corresponding row in `classifications`.

**What gets sent to Claude:**
- Title
- Duration
- Tags
- First 800 chars of description
- First ~2.5 minutes of auto-generated captions (fetched via `youtube-transcript-api`)

The transcript intro is the key signal — it's where trainers explain what kind of workout you're about to do, at what difficulty, with what equipment.

**Batch API:** All unclassified videos are submitted in a single Anthropic Batch API call (50% cheaper than standard, processed in parallel). The code polls every 30 seconds until the batch completes, then writes results to the `classifications` table.

**Model:** `claude-haiku-4-5-20251001` — sufficient for structured classification, very cheap.

**Output schema per video:**
```json
{
  "workout_type": "HIIT | Strength | Mobility | Cardio | Other",
  "body_focus":   "upper | lower | full | core | any",
  "difficulty":   "beginner | intermediate | advanced",
  "has_warmup":   true | false,
  "has_cooldown": true | false
}
```

Videos under 3 minutes (Shorts, promos) are skipped.

---

### `src/planner.py` — Plan

Picks one video per training day by querying the `videos + classifications` tables, applying scoring, and writing the result to `program_history`.

**Selection process per day slot:**

1. Query candidates matching `workout_type`, `body_focus`, duration range, difficulty
2. Exclude videos used in the last **8 weeks** (from `program_history`)
3. Exclude channels that have hit `max_channel_repeats` for this week
4. Score remaining candidates:
   - `+100` if published within `recency_boost_weeks` (newer = preferred)
   - `+40` if from a channel not yet used this week (spreads across channels)
   - `+0–20` random jitter (keeps variety week to week)
5. Pick randomly from the top 3 scorers

**Fallback tiers** (when strict query returns nothing):

| Tier | History window | Body focus | Channel limit |
|---|---|---|---|
| 1 | 8 weeks | exact | enforced |
| 2 | 4 weeks | exact | enforced |
| 3 | 4 weeks | any | enforced |
| 4 | none | any | enforced |
| 5 | none | any | ignored |

The plan is saved to `program_history` before returning so the same video won't be picked again for 8 weeks.

---

### `src/playlist.py` — Publish

Authenticates to YouTube via OAuth (using a stored refresh token — no browser needed) and performs a full weekly refresh:

1. List all existing playlist items and delete them one by one (API has no bulk delete)
2. Insert the new videos in Mon → Sun order (rest days skipped)
3. Update the playlist description with the human-readable plan summary

**YouTube API quota:** ~650 units per weekly refresh — well within the 10,000/day free limit.

---

### `src/db.py` — Persistence

Three SQLite tables:

```
videos                          classifications               program_history
──────────────────────────      ──────────────────────────    ──────────────────────────
id           TEXT PK            video_id    TEXT PK FK        id           INT PK AUTO
channel_id   TEXT               workout_type TEXT             week_start   TEXT
channel_name TEXT               body_focus   TEXT             video_id     TEXT FK
title        TEXT               difficulty   TEXT             assigned_day TEXT
description  TEXT               has_warmup   INT              completed    INT (default 0)
duration_sec INT                has_cooldown INT
published_at TEXT               classified_at TEXT
url          TEXT
tags         TEXT
```

`workout_library.db` is committed back to the repo by the GitHub Actions workflow after each run. This means the library persists across runs without any external database.

---

## Data Flow

```
config.yaml
    │
    ├─ channels list ──────────────────────────────────────────────┐
    │                                                              │
    └─ schedule ────────────────────────────────────┐             │
                                                    │             ▼
                                             planner.py     scanner.py
                                                    │             │
                                                    │         videos table
                                                    │             │
                                                    │       classifier.py
                                                    │             │
                                                    │    classifications table
                                                    │             │
                                                    └─────────────┘
                                                          │
                                                    plan (list of dicts)
                                                          │
                                              program_history table
                                                          │
                                                    playlist.py
                                                          │
                                               YouTube Playlist
```

---

## Credentials & Secrets

| Secret | Used by | How |
|---|---|---|
| `YOUTUBE_API_KEY` | scanner.py | Read-only API key — scans channels and fetches video details |
| `ANTHROPIC_API_KEY` | classifier.py | Batch classification via Claude Haiku |
| `YOUTUBE_CLIENT_ID` | playlist.py | OAuth for playlist write access |
| `YOUTUBE_CLIENT_SECRET` | playlist.py | OAuth for playlist write access |
| `YOUTUBE_OAUTH_REFRESH_TOKEN` | playlist.py | Exchanged for a fresh access token each run |

The refresh token is generated once locally via `scripts/get_oauth_token.py` and stored as a GitHub Secret. It never expires unless explicitly revoked.

---

## GitHub Actions Workflow

`.github/workflows/weekly_plan.yml` runs every Sunday at 18:00 UTC:

```
checkout → setup Python → pip install → python main.py --run → git commit workout_library.db → git push
```

Requires `contents: write` permission so the bot can commit the updated database back to the repo.

Can be triggered manually via `workflow_dispatch` for testing.

---

## Key Design Decisions

**SQLite committed to the repo** — no external database needed. The DB is small (~a few MB for thousands of videos), and committing it after each run gives a built-in audit trail of every week's plan via git history.

**Anthropic Batch API** — submitting all videos in one batch instead of sequential calls cuts classification cost by 50% and avoids rate limits. An entire channel back-catalogue (~2,000 videos) costs ~$1–2 total. Weekly incremental runs cost a few cents.

**Transcript intro as the primary signal** — video titles are unreliable. The first ~2.5 minutes of captions capture the trainer's actual introduction where they describe the workout type, difficulty, and equipment. Falls back gracefully to title + description if captions are unavailable.

**8-day incremental window** — not 7, to give a buffer for timezone differences and avoid videos published at the boundary slipping through.

**Tiered fallback in the planner** — constraints are relaxed progressively rather than failing hard. A plan is always produced even if the library is sparse for a given slot.

**`INSERT OR IGNORE` everywhere** — scanning and classifying are idempotent. Safe to re-run `--init` after adding a new channel without duplicating existing data.

---

---

# Web App Architecture

The web app is a multi-user version of the CLI pipeline, built as a FastAPI backend + Next.js frontend. The CLI pipeline logic (`src/scanner.py`, `src/classifier.py`, `src/planner.py`) is reused directly by the API services layer.

---

## Stack

| Layer | Technology |
|---|---|
| API | FastAPI (Python 3.12) |
| Database | PostgreSQL (Alembic migrations) |
| Auth | Google OAuth 2.0 + Starlette session middleware |
| Encryption | Fernet (credentials at rest) |
| Scheduler | APScheduler (in-process weekly cron) |
| Frontend | Next.js 16 + Tailwind CSS v4 |
| Frontend hosting | Vercel |
| API hosting | Railway |

---

## Database Schema

```
users
  id (uuid PK), google_id, email, display_name, created_at

channels
  id (uuid PK), user_id (FK), name, youtube_url, youtube_channel_id, added_at

videos
  id (youtube video ID PK), channel_id (FK), title, description,
  duration_sec, published_at, url, tags

classifications
  video_id (PK FK), workout_type, body_focus, difficulty,
  has_warmup, has_cooldown, classified_at
  — workout_type values: "Strength" | "HIIT" | "Cardio" | "Mobility" | "Other"
  — body_focus values: "upper" | "lower" | "full" | "core" | "any"
  — difficulty values: "beginner" | "intermediate" | "advanced"
  NOTE: workout_type is mixed-case (classifier output). All filter comparisons
        use func.lower() on both sides for case-insensitive matching.

schedules
  id (uuid PK), user_id (FK), day, workout_type, body_focus,
  duration_min, duration_max, difficulty

program_history
  id (int PK), user_id (FK), week_start (DATE), video_id (FK),
  assigned_day, completed

user_credentials
  user_id (PK FK), youtube_refresh_token (Fernet-encrypted), anthropic_key, updated_at,
  credentials_valid (bool, default true), youtube_playlist_id (nullable),
  classifier_batch_id (nullable — persisted Anthropic batch ID for resumable classification)

batch_usage_log
  id (int PK), user_id (FK), batch_id (text), videos_submitted, classified, failed,
  input_tokens, output_tokens, created_at
  — written after each Anthropic batch completes; used by admin stats for cost tracking

announcements
  id (int PK), message (text), is_active (bool, default true), created_at
  — admin-created site-wide banners; only one should be active at a time

Migration history:
  001 — initial schema
  002 — credentials_valid + youtube_playlist_id
  003 — classifier_batch_id
  004 — users.last_active_at + batch_usage_log + announcements
```

---

## API Layer (`api/`)

### Authentication flow
```
GET /auth/google
  → redirect to Google consent screen (scopes: openid, email, profile, youtube)

GET /auth/google/callback?code=&state=
  → exchange code for tokens
  → upsert user in DB
  → store youtube_refresh_token encrypted in user_credentials
  → generate signed token: URLSafeTimedSerializer(SECRET).dumps(user_id)
  → redirect to {FRONTEND_URL}?token=<signed_token>

Frontend (page.tsx on mount):
  → extract ?token= from URL, store in localStorage, strip from URL
  → all subsequent API calls send: Authorization: Bearer <token>

GET /auth/me          → current user profile
PATCH /auth/me        → update display_name
DELETE /auth/me       → delete user + all data (cascade), clear session
POST /auth/logout     → clear localStorage token
```

**Why no session cookies across domains:**
`SameSite=lax` blocks cross-origin fetch (Vercel → Railway). `SameSite=none` requires
third-party cookies which Chrome deprecated in 2024. URL token handoff + Bearer header
works regardless of browser cookie policy.

**Token details:**
- Signed with `SESSION_SECRET_KEY` via `itsdangerous.URLSafeTimedSerializer`
- Stored in `localStorage` (survives tab close / browser restart)
- Expires after 30 days (`max_age=30*24*3600` in `get_current_user`)
- `api/dependencies.py` checks `Authorization: Bearer` first, falls back to session cookie

### Data access pattern
All user-facing endpoints depend on `get_current_user` which checks the Bearer token
(or session cookie fallback) and returns the `User` ORM object, or raises 401.
All queries filter by `user_id` — no cross-user data leakage is possible.

`get_current_user` also updates `user.last_active_at` at most once per 5 minutes
(throttled to avoid a DB write on every request).

### Admin routes
Admin routes live in `api/routers/admin.py`. A separate `_require_admin` dependency
reads `ADMIN_EMAIL` env var at request time and raises 403 if the current user's email
doesn't match. Env var is read at request time (not import time) for test isolation.

```
GET  /admin/stats                         → aggregate stats + per-user rows
DELETE /admin/users/{user_id}             → delete any user (blocks self-deletion)
POST /admin/users/{user_id}/scan          → trigger full pipeline for any user
GET  /admin/announcements                 → list all announcements
POST /admin/announcements                 → create announcement
DELETE /admin/announcements/{id}          → delete announcement
PATCH /admin/announcements/{id}/deactivate → deactivate announcement

GET /announcements/active                 → active announcement or null (any auth'd user)
```

### Library endpoint
`GET /library` joins Video → Channel → Classification, filters by `Channel.user_id`,
applies optional filters (workout_type, body_focus, difficulty, channel_id),
sorts by `published_at DESC`, paginates with limit/offset.

---

## Services Layer (`api/services/`)

Thin wrappers that adapt the existing `src/` pure functions to use SQLAlchemy sessions
instead of raw SQLite. The business logic lives in `src/`; services handle DB I/O.

```
api/services/scanner.py    uses src/scanner.py      → scans YouTube channels
api/services/classifier.py uses src/classifier.py   → Anthropic Batch API classification
api/services/planner.py    uses src/planner.py      → weekly plan generation
```

### Scanner pre-classification filters (reduce Anthropic API cost)

Applied before fetching video details or sending to classifier:

1. **Title keyword blocklist** — skips videos with meal/recipe/vlog/Q&A/podcast/unboxing/
   giveaway/transformation etc. in the title (no extra API calls needed).
2. **Livestream/premiere filter** — skips `liveBroadcastContent=live/upcoming` (free field
   returned by the playlist API).
3. **Duration cap** — skips videos > 2 hours (livestreams/long-form podcasts that slipped through).
4. **Shorts filter** (existing) — skips videos < 3 min or with `#shorts` hashtag.

### Classifier — batch cap + resumable batches

- **`MAX_CLASSIFY_PER_RUN = 300`** — caps each pipeline run to 300 videos. Keeps first-run
  transcript fetch time to ~5 min instead of 30+ min for large channels. Remainder deferred
  to the next scan.
- **Resumable batches** — `classifier_batch_id` is persisted to `user_credentials` immediately
  after the Anthropic batch is submitted. On restart (e.g. Railway deploy mid-pipeline), the
  next scan call resumes polling the existing batch instead of resubmitting — no double billing.
  The batch ID is cleared when results are saved.

---

## Scheduler (`api/scheduler.py`)

APScheduler runs inside the FastAPI process. On startup it registers a cron job
that fires every Sunday at 6pm UTC, iterates over all users, and runs the full
scan → classify → plan pipeline for each.

This replaces GitHub Actions for web app users. The CLI tool on GitHub Actions
still handles the single original user independently.

---

## Frontend (`frontend/`)

### Page map
```
/ ─────────── Landing page (hero, how it works, features, CTA)
              Signed-in users auto-redirected to /dashboard or /onboarding

/onboarding ─ 3-step sign-up wizard
              Step 1: Add channels (ChannelManager component)
              Step 2: Set schedule (ScheduleEditor component)
              Step 3: Trigger first scan → /dashboard

/guide ────── User guide (7 sections with sticky desktop sidebar)
              Linked from homepage nav and footer

/admin ─────── Admin console (admin users only, gated by is_admin flag)
              Stat cards: total users, library size, AI usage (7d + all-time, cost estimate)
              Active pipelines monitor (stage + progress per user)
              Per-user table: last_active_at, channels, videos, YouTube status, last plan,
                             pipeline stage, ↺ Scan and Delete action buttons
              Announcements panel: create / deactivate / delete site-wide banners
              Auto-refreshes every 30s; admin nav link shown in dashboard header for admins

/dashboard ── Weekly plan grid (7 days, thumbnails, badges)
              Nav: Library | Settings | Generate plan / Regenerate | Publish to YouTube
                   | Admin (admin users only) | Sign out
              Announcement banner (dismissible) shown when active announcement exists
              - "Generate plan" (no plan): triggers POST /jobs/scan, shows scanning banner,
                polls GET /jobs/status every 5s; polls GET /plan/upcoming until plan appears
              - "Regenerate" (plan exists): calls POST /plan/generate synchronously,
                shows "Generating…" banner in-flight, updates grid on response
              - "Rescan channels" button shown instead of Regenerate when plan has all null days
              - Scanning banner: stage-specific messages (scanning/classifying/generating/failed)
                + progress bar + "X / N done" count during classification phase
              - Building phase: "Preparing batch — fetching transcripts (X / N)" with progress bar
              - Generating banner: spinner + "Generating your plan…" while fast generate runs
              - On mount: calls GET /jobs/status to auto-detect a running pipeline (handles
                externally triggered scans or page refreshes mid-scan)

/library ──── Video library browser
              Filters: workout type, body focus, difficulty, channel
              Cards: thumbnail, duration, badges, "Assign to day" select
              Pagination: 24 per page

/settings ─── Profile (display name, email)
              Channels (ChannelManager)
              Schedule (ScheduleEditor + save)
              Danger zone (delete account, 2-step confirm)
```

### Shared components
`ChannelManager` and `ScheduleEditor` are extracted to `src/components/` and reused
in both `/onboarding` and `/settings`. The onboarding page wraps them with step
navigation; settings wraps them with save buttons.

`Tooltip` (`src/components/Tooltip.tsx`) — CSS-only tooltip using Tailwind `group/tip`
pattern. Props: `text`, `children`, `position?: "top" | "bottom"`. Used throughout
the admin console. Hover delay is 300ms (`delay-300`) to reduce accidental triggers.

### API client (`src/lib/api.ts`)
Single file with all `fetch` calls and TypeScript types. Uses `credentials: "include"`
on every request for session cookie forwarding. Throws on non-OK responses with the
parsed `detail` from the FastAPI error response.

---

## Key Design Decisions (Web App)

**Services reuse `src/` logic** — the core scanner/classifier/planner code is unchanged.
The web app API services are thin adapters that swap raw SQLite for SQLAlchemy sessions.
This avoids duplicating ~2,000 lines of carefully tested business logic.

**APScheduler over Celery** — at early user counts, sequential per-user weekly runs
complete in seconds. APScheduler adds zero infrastructure. Migration path to Celery is
straightforward when scale demands it (see `docs/infra-research.md`).

**Platform-pays for Anthropic classification** — channel init costs ~$1–2 per user
ever; weekly incremental runs cost a few cents. The `user_credentials.anthropic_key`
field exists in the schema for future BYOK support but is unused in v1.

**Fernet encryption for credentials** — YouTube refresh tokens are encrypted at rest.
The `ENCRYPTION_KEY` env var is validated at startup; the server refuses to start
without it to prevent silent unencrypted storage.

**Shared components for channel + schedule editing** — both onboarding and settings
need channel management and schedule editing. Extracting `ChannelManager` and
`ScheduleEditor` to `src/components/` keeps the logic in one place and keeps both
pages consistent.

**Case-insensitive library filters** — the classifier (a language model) returns mixed-case
`workout_type` values ("HIIT", "Strength"). Rather than normalising at write time (risky,
would need a migration), `GET /library` uses `func.lower()` on both the column and the
query param. Frontend filter dropdowns use an explicit label map for display.
