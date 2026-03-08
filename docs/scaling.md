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

## User Engagement & Cost Control

### The problem

The platform bears the Anthropic classification cost for every user. Running the weekly pipeline for users who have churned wastes money and adds noise. The goal is to only generate plans for users who are actively following them.

### What YouTube API can tell us

**Nothing useful.** The YouTube Data API doesn't expose watch history or play events — this is a privacy restriction, not a quota limitation. You can read/write playlists but cannot know if the user watched any video in it. All engagement signals must come from within the web app itself.

### Signals considered and why they fall short

| Signal | Problem |
|---|---|
| `last_active_at` on User | App logins are the wrong proxy — a user could work out daily from the YouTube playlist and never open the app |
| `ProgramHistory.completed` (user marks days done) | Self-reported, unreliable, requires app interaction |
| OAuth token still valid | Only means they haven't disconnected — says nothing about whether they're working out |
| YouTube playlist still exists | Can check via API but doesn't mean they're using it |
| Weekly check-in email ("did you follow the plan?") | Email ignore rates are high; self-reported data is unreliable |
| Weekly opt-in email ("generate plan for next week?") | Guarantees intent but adds friction and removes the automation value |

### Options considered

**Option A — Two-layer inactivity system (Duolingo model)**
- Layer 1: soft nudge email after 2 weeks no app interaction
- Layer 2: hard pause after 4 weeks no day marked complete
- Problem: the workout happens entirely inside YouTube. The most faithful users — those working out every day from the playlist — never open the app and get incorrectly flagged as inactive. Penalises the exact user you want to keep.

**Option B — Keep running as long as OAuth token is valid**
- Simple: if user revoked access, they've churned
- Problem: OAuth token validity says nothing about whether they're actually using the plan. A user could have the app connected and never look at their playlist.

**Option C — Weekly check-in email / notification**
- Ask "did you follow last week's plan?" with a one-tap response
- Problem: email response rates are low and self-reporting is unreliable. Doesn't solve the fundamental measurement problem.

**Option D — Manual publish button (decided 2026-03-07)**
- No automatic playlist publishing. User must log into the app weekly and click "Publish to YouTube" to update their playlist.
- The publish action IS the engagement signal. No login = no publish = no new plan generated = no cost.
- See below for full rationale.

### Decision: manual publish as the engagement gate

The weekly "Publish to YouTube" button in the web app is the required action to trigger a new plan. This solves the intent measurement problem permanently:

- **Intent is ironclad** — the user physically logs in and clicks publish. No ambiguity, no inference, no self-reporting.
- **Cost control is automatic** — no login = pipeline skipped = zero cost. Works at any scale without additional engineering.
- **Eliminates passive engagement tracking entirely** — no `last_active_at`, no completion flags, no heuristics needed.
- **Forces the app to have weekly value** — the web app becomes a genuine weekly touchpoint (review plan, swap days, publish) rather than a one-time setup tool.
- **Optional in-app workout tracking** — users who want to follow the plan inside the app can; users who prefer YouTube can publish and switch to YouTube. Both workflows supported.

### Trade-offs accepted

- **Removes "set and forget" automation** — the CLI tool's core value was zero weekly effort. The web app requires a weekly login. This is an intentional product direction change.
- **Users must show up weekly** — this is a feature, not a bug. See Product Philosophy below.

### Product philosophy

This app is for people who are serious about their training. The weekly login is the price of admission. Users who find that too much friction self-select out — which is acceptable. Optimising for engaged users over maximising signup numbers leads to:

- Costs that stay proportional to real value delivered
- No guilt-trip re-engagement emails or dark patterns
- Word of mouth from genuinely happy users over growth hacking inactive ones
- A simpler, more honest system at any scale

This applies to the target audience at every stage — friends for v1, broader fitness enthusiasts later. Motivated users are the only target users.

### What this means for the weekly flow

```
User opens app Sunday/Monday →
  Reviews next week's generated plan →
  Swaps days if needed →
  Clicks "Publish to YouTube" →
  Playlist updates + pipeline marked as run for this week
```

If user doesn't log in → playlist stays as last week's → no new plan generated → no Anthropic cost.

### What needs to be built (Phase 5)

- `POST /plan/publish` endpoint — pushes current plan to YouTube playlist, marks week as published
- Weekly scheduler checks if user published last week before running pipeline again
- "Publish to YouTube" button in the frontend (Phase 4)
- In-app plan view as an alternative to YouTube for users who want to track workouts in the app

---

## Returning User Experience

### The scenario

User was active, then went on holiday / got injured / got busy for several weeks. They come back and open the app. What do they find and what should happen?

### Problems to handle on return

| Problem | Impact |
|---|---|
| Stale plan | Last published plan is weeks old; YouTube playlist is outdated |
| Stale video library | Weeks of new uploads from their channels haven't been scanned or classified |
| History window distortion | Gaps in the 8-week dedup window — planner may re-suggest recently done videos or have fewer candidates than expected |
| Unknown reason for absence | Injury, travel, busy — the right experience may differ but the app can't know |

### Options considered

**Option A — Silent catch-up**
On login after a gap, automatically trigger scan → classify → generate plan in the background. User just sees a fresh plan ready to publish.
- Pro: frictionless
- Con: user doesn't know what happened, might be disorienting if they return mid-week with their own plan

**Option B — Welcome back screen (decided 2026-03-07)**
Detect the gap via `last_active_at`, show a banner: *"Welcome back! It's been X weeks. We've caught up your video library — here's a fresh plan for this week."*
Automatically triggers catch-up in background. User reviews and publishes when ready.
- Pro: transparent, feels intentional, no extra decision required
- Con: requires `last_active_at` on the User model

**Option C — Offer a choice on return**
Show: *"Welcome back! Want us to generate a fresh plan for this week?"* with options to generate or browse library first.
- Pro: gives control, useful if returning mid-week
- Con: adds a decision step, more friction

### Decision: Option B — Welcome back screen

```
User logs in after 2+ week gap →
  App detects gap via last_active_at →
  Shows "Welcome back" banner with gap duration →
  Triggers background scan + classify automatically →
  When ready: shows fresh plan with "Publish to YouTube" CTA
```

This makes the catch-up feel like a deliberate feature rather than something that silently happened. The gap threshold for showing the banner is 2 weeks (one missed cycle).

### Why last_active_at is still needed

Even though we dropped activity-based pipeline pausing, `last_active_at` is still required for:
- Detecting the return scenario and showing the welcome back UX
- Knowing how long the gap was (to communicate it clearly to the user)
- Future analytics on usage patterns

Should be added to the User model before launch so data accumulates from day one. Updated on every authenticated request via middleware.

### What needs to be built

- `User.last_active_at` — DB column + Alembic migration + middleware to update on every request
- Welcome back detection in the frontend (Phase 4) — check gap on login, show banner if > 2 weeks
- Background catch-up trigger on return — same scan → classify → generate pipeline as manual publish flow

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
- **Cross-user channel dedup (pre-scale):** Current schema is `users → channels → videos` — each user owns their channel row, so if N users follow the same YouTube channel, it gets scanned N times and videos are stored N times. At v1 scale (friends) this is negligible. Before broader launch, consider a shared `channels` table with a `user_channels` join table so popular channels (e.g. HASfit) are scanned once and their videos stored once, shared across all subscribers. Requires schema migration and scoping changes to the scanner and classifier.

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
