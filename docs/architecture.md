# Architecture

## Overview

YouTube Workout Planner is a scheduled Python pipeline that runs weekly on GitHub Actions. It scans YouTube channels you follow, classifies every video using Claude AI, selects one video per training day based on your schedule, and pushes the result directly into a YouTube playlist.

The entire system is stateless between runs - all persistent state lives in a single SQLite file (`workout_library.db`) that gets committed back to the repo after each run.

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

**Init mode** (`--init`) runs the same pipeline but does a full back-catalogue scan instead of an 8-day incremental one - used once when adding a new channel.

---

## Components

### `main.py` - Entry point

Parses CLI flags, loads `config.yaml`, and orchestrates the four stages. Four modes:

| Flag | What it does |
|---|---|
| `--init` | Full scan + full classify. Run once after setup. |
| `--classify-only` | Classify without re-scanning. Resumes interrupted classification. |
| `--run` | Weekly: incremental scan → classify → plan → publish. |
| `--dry-run` | Same as `--run` but skips the playlist update. |

---

### `src/scanner.py` - Discover

Resolves each channel URL to its uploads playlist ID, then paginates through it using `playlistItems.list`. Video details (duration, tags) are batch-fetched with `videos.list` (50 per API call).

Two modes:
- **Full scan** - fetches entire back-catalogue; used on `--init`
- **Incremental scan** - fetches only videos newer than `since_date` (8 days); uploads playlist is newest-first so pagination stops early

Deleted/private videos are filtered. New videos are `INSERT OR IGNORE`d into the `videos` table - safe to re-run.

**YouTube API quota:** ~20 units per 500 videos. Daily free quota is 10,000 units.

---

### `src/classifier.py` - Understand

Classifies every video in the `videos` table that has no corresponding row in `classifications`.

**What gets sent to Claude:**
- Title
- Duration
- Tags
- First 800 chars of description
- First ~2.5 minutes of auto-generated captions (fetched via `youtube-transcript-api`)

The transcript intro is the key signal - it's where trainers explain what kind of workout you're about to do, at what difficulty, with what equipment.

**Batch API:** All unclassified videos are submitted in a single Anthropic Batch API call (50% cheaper than standard, processed in parallel). The code polls every 30 seconds until the batch completes, then writes results to the `classifications` table.

**Model:** `claude-haiku-4-5-20251001` - sufficient for structured classification, very cheap.

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

### `src/planner.py` - Plan

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

### `src/playlist.py` - Publish

Authenticates to YouTube via OAuth (using a stored refresh token - no browser needed) and performs a full weekly refresh:

1. List all existing playlist items and delete them one by one (API has no bulk delete)
2. Insert the new videos in Mon → Sun order (rest days skipped)
3. Update the playlist description with the human-readable plan summary

**Sleep reduction:** `time.sleep(0.3)` reduced to `time.sleep(0.05)` between API calls, saving ~3s per publish.

**YouTube API quota:** ~650 units per weekly refresh - well within the 10,000/day free limit.

**Web app publish flow (async):**
`POST /plan/publish` returns 202 immediately and starts a background thread (`_run_publish`). The frontend polls `GET /plan/publish/status` every 2s until `status == "done"` or `"failed"`. Status is stored in the `_publish_status` in-memory dict (keyed by user ID). This mirrors the `_pipeline_status` pattern in `jobs.py`.

---

### `src/db.py` - Persistence

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
| `YOUTUBE_API_KEY` | scanner.py | Read-only API key - scans channels and fetches video details |
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

**SQLite committed to the repo** - no external database needed. The DB is small (~a few MB for thousands of videos), and committing it after each run gives a built-in audit trail of every week's plan via git history.

**Anthropic Batch API** - submitting all videos in one batch instead of sequential calls cuts classification cost by 50% and avoids rate limits. An entire channel back-catalogue (~2,000 videos) costs ~$1–2 total. Weekly incremental runs cost a few cents.

**Transcript intro as the primary signal** - video titles are unreliable. The first ~2.5 minutes of captions capture the trainer's actual introduction where they describe the workout type, difficulty, and equipment. Falls back gracefully to title + description if captions are unavailable.

**8-day incremental window** - not 7, to give a buffer for timezone differences and avoid videos published at the boundary slipping through.

**Tiered fallback in the planner** - constraints are relaxed progressively rather than failing hard. A plan is always produced even if the library is sparse for a given slot. Tier 6 (final fallback) ignores `workout_type` entirely and assigns any available video - no active day is ever left blank. The `scheduled_workout_type` field is propagated through the plan dict so the frontend can distinguish a rest day (null) from an active day that exhausted all tiers (show a warning).

**`INSERT OR IGNORE` everywhere** - scanning and classifying are idempotent. Safe to re-run `--init` after adding a new channel without duplicating existing data.

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
  id (uuid PK), google_id, email, display_name, created_at,
  last_scan_error (text, nullable) - set on pipeline failure, cleared on success

channels (global - shared across all users)
  id (uuid PK), name, youtube_url, youtube_channel_id, added_at,
  first_scan_done (bool, default false), last_video_published_at (datetime, nullable)

user_channels (join table - links users to channels they've subscribed to)
  user_id (PK FK → users.id CASCADE), channel_id (PK FK → channels.id CASCADE), added_at
  - deleting a user_channels row unsubscribes the user; channel + videos are preserved

videos
  id (youtube video ID PK), channel_id (FK), title, description,
  duration_sec, published_at, url, tags

classifications
  video_id (PK FK), workout_type, body_focus, difficulty,
  has_warmup, has_cooldown, classified_at
  - workout_type values: "Strength" | "HIIT" | "Cardio" | "Mobility" | "Other"
  - body_focus values: "upper" | "lower" | "full" | "core" | "any"
  - difficulty values: "beginner" | "intermediate" | "advanced"
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
  classifier_batch_id (nullable - persisted Anthropic batch ID for resumable classification)

batch_usage_log
  id (int PK), user_id (FK), batch_id (text), videos_submitted, classified, failed,
  input_tokens, output_tokens, created_at
  - written after each Anthropic batch completes; used by admin stats for cost tracking

announcements
  id (int PK), message (text), is_active (bool, default true), created_at
  - admin-created site-wide banners; only one should be active at a time

scan_log
  id (int PK), user_id (FK), started_at, completed_at (nullable),
  status ("running" | "done" | "failed"), videos_scanned (nullable)
  - one row per _run_full_pipeline invocation; powers "scans/day" chart

user_activity_log
  id (int PK), user_id (FK), active_at
  - one row per 5-min active window per user; powers "active users/day" chart

Migration history:
  001 - initial schema
  002 - credentials_valid + youtube_playlist_id
  003 - classifier_batch_id
  004 - users.last_active_at + batch_usage_log + announcements
  005 - scan_log + user_activity_log
  006 - channels.first_scan_done
  007 - channels.last_video_published_at
  008 - users.last_scan_error
```

---

## API Layer (`api/`)

### Authentication flow
```
GET /auth/google?color_scheme=light|dark
  → redirect to Google consent screen (scopes: openid, email, profile, youtube)
  → color_scheme forwarded to Google OAuth URL so sign-in page matches app theme (default: light)

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
All queries filter by `user_id` - no cross-user data leakage is possible.

`get_current_user` also updates `user.last_active_at` at most once per 5 minutes
(throttled to avoid a DB write on every request).

### Admin routes
Admin routes live in `api/routers/admin.py`. A separate `_require_admin` dependency
reads `ADMIN_EMAIL` env var at request time and raises 403 if the current user's email
doesn't match. Env var is read at request time (not import time) for test isolation.

```
POST /feedback                            → submit user feedback (category: feedback/help/bug; trimmed message; emails admin via Resend; 400 invalid category/blank message; 503 on email failure)

GET  /admin/stats                         → aggregate stats + per-user rows
DELETE /admin/users/{user_id}             → delete any user (blocks self-deletion)
POST /admin/users/{user_id}/scan          → trigger full pipeline for any user
POST /admin/users/{user_id}/reset-onboarding → delete user's UserChannel + Schedule rows (treated as new user on next login; shared channels/videos preserved)
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
api/services/scanner.py          uses src/scanner.py      → scans YouTube channels
api/services/classifier.py       uses src/classifier.py   → Anthropic Batch API classification
                                                             + rule_classify_for_user() (free, regex-only)
                                                             + build_targeted_batch() (gap-slot targeting)
api/services/planner.py          uses src/planner.py      → weekly plan generation
                                                             + can_fill_plan() (check if plan is fillable)
                                                             + get_gap_types() (identify under-provisioned slots)
api/services/email.py                                     → send_weekly_plan_email() + send_feedback_email()
api/services/channel_validator.py                         → validate_channel_fitness() (Claude Haiku, fail-open)
```

### Email service (`api/services/email.py`)

`send_weekly_plan_email(user, plan)` - sends a formatted HTML email with the week's
workout plan via the Resend SDK. Uses `api/templates/weekly_plan_email.html` (Jinja2,
table-based, inline CSS). Only sends if `user.email_notifications` is True. Called by
APScheduler after each successful plan generation; errors are caught and logged - never
break the pipeline.

`send_feedback_email(user, category, message)` - sends admin-facing notification when a
user submits feedback. `to` = `ADMIN_EMAIL`, `reply_to` = user's email (so admin can reply
directly). Raises `RuntimeError` if `RESEND_API_KEY` is not set.

Required env vars: `RESEND_API_KEY`, `FROM_EMAIL` (sender address), `APP_URL` (included
in weekly plan email CTA link).

### Scanner pre-classification filters (reduce Anthropic API cost)

Applied before fetching video details or sending to classifier:

1. **Title keyword blocklist** - skips videos with meal/recipe/vlog/Q&A/podcast/unboxing/
   giveaway/transformation etc. in the title (no extra API calls needed).
2. **Livestream/premiere filter** - skips `liveBroadcastContent=live/upcoming` (free field
   returned by the playlist API).
3. **Duration cap** - skips videos > 2 hours (livestreams/long-form podcasts that slipped through).
4. **Shorts filter** (existing) - skips videos < 3 min or with `#shorts` hashtag.

### Classifier - batch cap + resumable batches + Phase A cost controls

- **`MAX_CLASSIFY_PER_RUN = 300`** - caps each pipeline run to 300 videos. Keeps first-run
  transcript fetch time to ~5 min instead of 30+ min for large channels. Remainder deferred
  to the next scan.
- **Resumable batches** - `classifier_batch_id` is persisted to `user_credentials` immediately
  after the Anthropic batch is submitted. On restart (e.g. Railway deploy mid-pipeline), the
  next scan call resumes polling the existing batch instead of resubmitting - no double billing.
  The batch ID is cleared when results are saved.
- **`max_tokens = 80`** (F1) - reduced from 150. JSON response is ~50–70 tokens; 80 gives headroom without waste.
- **`CLASSIFY_MAX_AGE_MONTHS` env var** (F2, default 18) - videos older than this are skipped before building the Anthropic batch.
- **First-scan channel cap** (F3) - new channels are capped at 75 videos on first scan (`first_scan_done=False`); subsequent scans are uncapped incremental.
- **Skip inactive channels** (F4) - weekly cron skips channels where last published video is >60 days old and channel was added >60 days ago. User-triggered scans always run all channels. `last_video_published_at` updated after each scan.
- **Rule-based pre-classifier - `title_classify()`** (F6) - before building the Anthropic batch, each video title is tested against regex rules for workout type (HIIT/Strength/Cardio/Mobility), body focus (upper/lower/full/core), difficulty (beginner/intermediate/advanced), and warmup/cooldown flags. If a type rule matches, the video is classified directly and never sent to the AI. Returns `None` for ambiguous titles (falls through to Anthropic). Estimated 30–40% reduction in batch submissions. Applied to all unclassified videos before the `MAX_CLASSIFY_PER_RUN` cap.
- **Adaptive payload trimming - `_title_is_descriptive()`** (F5) - for videos that do reach the AI batch, titles containing fitness keywords (duration numbers, body part names, workout type words) are sent with a 300-char description and no transcript. Ambiguous titles use the full 800-char description + transcript. Saves ~20–30% of input tokens for obvious-title videos.
- **Lazy classification - plan-first, classify-lazily** (F9) - the pipeline no longer classifies all unclassified videos before generating a plan. Instead:
  1. `rule_classify_for_user(session, user_id)` runs first - free, no Anthropic calls.
  2. `can_fill_plan(session, user_id)` checks whether every non-rest schedule slot has at least `MIN_PLAN_CANDIDATES` (default 3) classified candidates using a Tier-4 style query (any body_focus, no history window).
  3. **Fast path** (can fill): generate plan immediately. Remaining unclassified videos are submitted to Anthropic in a background thread (`_background_classify_task`) - non-blocking relative to plan delivery.
  4. **Slow path** (cannot fill): `get_gap_types()` identifies which slot types are under-provisioned; `build_targeted_batch()` selects only unclassified videos whose titles suggest those missing types (capped at `max(len(gaps) × TARGETED_BATCH_MULTIPLIER, 10)`). Only this small batch is submitted to Anthropic before plan generation. The remainder goes to background.
  - **`MIN_PLAN_CANDIDATES`** env var (default 3): min classified videos per slot to consider the plan fillable.
  - **`TARGETED_BATCH_MULTIPLIER`** env var (default 5): candidates per gap slot in the targeted mini-batch.
  - **Impact**: onboarding with descriptive titles → 0 Anthropic calls; weekly scans on an established library → almost always 0 Anthropic calls; vague-title onboarding → 5–15 calls instead of 75+.
  - `background_classifying: bool` added to `GET /jobs/status` response - `true` while background thread is running. Library page shows an amber "Your library is still building" banner when this is true.

---

## Scheduler (`api/scheduler.py`)

APScheduler runs inside the FastAPI process. On startup it registers a cron job
that fires every Sunday at 6pm UTC and runs the full scan → classify → plan
pipeline for each **active** user.

### YouTube publish - design intent

The web app is the primary interface. The YouTube playlist publish button is a
convenience feature - it lets users play their week's videos directly from the
YouTube app without having to open the web app each time. It is not the primary
engagement surface.

All meaningful user-intent signals (plan views, video swaps, schedule changes,
publish clicks) are captured within the web app. YouTube is a read-only output;
no feedback flows back from it.

### Lazy classification in the weekly cron

The scheduler applies the same lazy classification logic as the manual pipeline:

```
Incremental scan (new videos only)
  ↓
rule_classify_for_user() - free, no Anthropic
  ↓
can_fill_plan()?
  ├── YES → generate plan immediately, skip Anthropic entirely (most weeks)
  └── NO  → classify_for_user() for all unclassified, then generate plan
```

Most weekly scans produce 0 Anthropic calls because the library is already rich from previous weeks. Anthropic is only called when a new channel was recently added that covers a slot type with a thin pool.

### Active-user gate

Any authenticated request updates `user.last_active_at` (throttled to once per
5 minutes in `get_current_user`). The weekly cron uses this to skip users who
haven't opened the app in **14 days**, saving YouTube API quota and Anthropic
credits. Users absent for 8–13 days (missed one week) still get a plan on the
next Sunday; only users absent for two full weeks are skipped.

The Publish button counts as activity - a user who only opens the app to publish
once a week will always have `last_active_at` within 7 days and will never be
skipped.

This replaces GitHub Actions for web app users. The CLI tool on GitHub Actions
still handles the single original user independently.

---

## Frontend (`frontend/`)

### Page map
```
/ ─────────── Landing page (redesigned M1): centered hero with "Stop watching. Start doing." headline + real dashboard screenshot (light/dark) in browser chrome frame; scrolling channel avatar marquee (12 creators via unavatar.io); how it works 3-step; dark rounded bottom CTA. Signed-in users auto-redirected to /dashboard or /onboarding.

/onboarding ─ 7-step onboarding wizard
              Step 1: Life stage (4 cards, auto-advance)
              Step 2: Goal (3–4 options by profile, auto-advance)
              Step 3: Training days (2–6 toggle, auto-advance)
              Step 4: Session length (4 options, auto-advance)
              Step 5: Schedule preview (confirm or customise with inline ScheduleEditor)
              Step 6: Channels (ChannelManager + curated suggestions by profile)
              Step 7: Live scan progress (polls /jobs/status every 2s, auto-navigates to /dashboard)

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
              Re-activation banner (dismissible) shown when plan.week_start < current Monday
              Swap picker: "Swap video" button below each day card opens inline SwapPicker -
                fetches top 10 from GET /library filtered by day's workout_type; "Show all
                types" clears filter; selecting calls PATCH /plan/{day}; updates in place
              - "Generate plan" (no plan): triggers POST /jobs/scan, shows scanning banner,
                polls GET /jobs/status every 5s; polls GET /plan/upcoming until plan appears
              - "Regenerate" (plan exists): calls POST /plan/generate synchronously,
                shows "Generating…" banner in-flight, updates grid on response
              - "Rescan channels" button shown instead of Regenerate when plan has all null days
              - Scanning banner: stage-specific messages (scanning/classifying/generating/failed)
                + progress bar + "X / N done" count during classification phase
              - Building phase: "Preparing batch - fetching transcripts (X / N)" with progress bar
              - Generating banner: spinner + "Generating your plan…" while fast generate runs
              - On mount: calls GET /jobs/status to auto-detect a running pipeline (handles
                externally triggered scans or page refreshes mid-scan)

/library ──── Video library browser
              Filters: workout type, body focus, difficulty, channel
              Cards: thumbnail, duration, badges, "Assign to day" select
              Pagination: 24 per page
              Amber banner: "Your library is still building - more videos are being classified
                in the background." shown when GET /jobs/status returns background_classifying=true.
                Dismissible via ✕ button. Shown once on mount (not polled).

/settings ─── Profile (display name, email)
              Channels (ChannelManager)
              Schedule (ScheduleEditor + save)
              Danger zone (delete account, 2-step confirm)
```

### Shared components
`ChannelManager` and `ScheduleEditor` are extracted to `src/components/` and reused
in both `/onboarding` and `/settings`. The onboarding page wraps them with step
navigation; settings wraps them with save buttons.

`ChannelManager` accepts optional `suggestions?: ChannelSearchResult[]` and
`suggestionsLoading?: boolean` props. When provided, a 3-card grid of curated channels
(thumbnail + name + one-click "+ Add") is shown above the search box. Cards are fetched
from `GET /channels/suggestions?profile=<profile>` by the parent component - onboarding
passes the profile-specific list, settings passes the general list. The backend caches
results in the shared `channels` table (`thumbnail_url`, `description` columns added in
migration 018) so the YouTube API is only called once per unique suggestion channel across
all users and all time.

**Channel fitness validation** - `POST /channels` calls `validate_channel_fitness()` (migration 019
added `users.profile` + `users.goal`; written by `PUT /schedule`). If the user has a profile+goal
set, the channel name + description is sent to Claude Haiku (max_tokens=20). Response "yes" or
"unsure" allows through; "no: <label>" raises 422 with a user-friendly message. Fails open on
any error or missing API key - a sparse description never blocks a legitimate channel.

`Badge` (`src/components/Badge.tsx`) - shared styled badge pill used in dashboard and
library pages for workout type, body focus, and difficulty tags.

`Tooltip` (`src/components/Tooltip.tsx`) - CSS-only tooltip using Tailwind `group/tip`
pattern. Props: `text`, `children`, `position?: "top" | "bottom"`. Used throughout
the admin console. Hover delay is 300ms (`delay-300`) to reduce accidental triggers.

`ThemeProvider` (`src/components/ThemeProvider.tsx`) - React context that reads system
preference (`prefers-color-scheme: dark`) on first load, persists user choice in
`localStorage`, and toggles the `dark` class on `<html>`. Exposes `useTheme()` hook.
Single `useEffect` merges system detection, localStorage read, and system-change listener.
The system-change listener guards against overriding an explicit user choice (`localStorage` check inside the handler, not at registration time).

`ThemeToggle` (`src/components/ThemeToggle.tsx`) - floating sun/moon button (bottom-right,
`z-40`, `bg-zinc-100 dark:bg-zinc-800`). Mounted once in `layout.tsx`; not imported on
individual pages.

`FeedbackWidget` (`src/components/FeedbackWidget.tsx`) - floating "Feedback" pill button
(bottom-right corner, above ThemeToggle). Opens a modal with category select (feedback /
help / bug) and a free-text textarea. Calls `POST /feedback`; on success shows a toast
and closes. Shown on all post-login pages (dashboard, library, settings).

### Shared utilities (`src/lib/`)
`lib/utils.ts` - `DAY_LABELS` constant (Mon–Sun labels array) and `formatDuration(sec)`
helper. Previously duplicated in dashboard, library, and onboarding pages.

`lib/scheduleTemplates.ts` - `buildSchedule()` function that generates a `ScheduleSlot[]`
from a life-stage profile, goal, number of training days, and session duration. Used in
onboarding step 5 to produce a sensible default schedule before the user customises it.

### Frontend tests (`frontend/src/test/`)
`test/setup.ts` - Vitest + `@testing-library/jest-dom` setup file.

Run: `cd frontend && npm run test:run` - 71 tests covering `scheduleTemplates` logic,
`ChannelManager` component behaviour, onboarding page step flows, ThemeProvider, and ThemeToggle.

### API client (`src/lib/api.ts`)
Single file with all `fetch` calls and TypeScript types. Uses `credentials: "include"`
on every request for session cookie forwarding. Throws on non-OK responses with the
parsed `detail` from the FastAPI error response.

---

## Key Design Decisions (Web App)

**Services reuse `src/` logic** - the core scanner/classifier/planner code is unchanged.
The web app API services are thin adapters that swap raw SQLite for SQLAlchemy sessions.
This avoids duplicating ~2,000 lines of carefully tested business logic.

**APScheduler over Celery** - at early user counts, sequential per-user weekly runs
complete in seconds. APScheduler adds zero infrastructure. Migration path to Celery is
straightforward when scale demands it (see `docs/infra-research.md`).

**Platform-pays for Anthropic classification** - channel init costs ~$1–2 per user
ever; weekly incremental runs cost a few cents. The `user_credentials.anthropic_key`
field exists in the schema for future BYOK support but is unused in v1.

**Fernet encryption for credentials** - YouTube refresh tokens are encrypted at rest.
The `ENCRYPTION_KEY` env var is validated at startup; the server refuses to start
without it to prevent silent unencrypted storage.

**Shared components for channel + schedule editing** - both onboarding and settings
need channel management and schedule editing. Extracting `ChannelManager` and
`ScheduleEditor` to `src/components/` keeps the logic in one place and keeps both
pages consistent.

**Case-insensitive library filters** - the classifier (a language model) returns mixed-case
`workout_type` values ("HIIT", "Strength"). Rather than normalising at write time (risky,
would need a migration), `GET /library` uses `func.lower()` on both the column and the
query param. Frontend filter dropdowns use an explicit label map for display.
