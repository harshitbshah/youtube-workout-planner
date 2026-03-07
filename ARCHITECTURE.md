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
