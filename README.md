# YouTube Workout Planner

You have favourite YouTube fitness creators. You know their style, you trust their programming. But every week you're manually hunting for the right video, second-guessing your split, and eventually just picking whatever feels right.

This tool fixes that. Tell it which channels you follow and what your weekly training split looks like — and every Sunday it automatically builds your next week's workout plan from videos those creators actually published. Monday morning you open YouTube and your playlist is already there, in order, day by day.

No spreadsheets. No decision fatigue. Just train.

---

## How It Works

Every Sunday at 6pm UTC, a scheduled GitHub Actions job runs four steps:

**1. Discover** — scans your configured channels for any videos published in the last 8 days, adding them to a local library.

**2. Understand** — any newly discovered videos get classified by Claude AI: what type of workout is it (HIIT, strength, cardio, mobility)? Which part of the body? How hard? This isn't just reading the title — see [How Classification Works](#how-classification-works) below.

**3. Plan** — picks one video per training day based on your schedule, avoiding anything used in the last 8 weeks, spreading selections across channels, and favouring newer uploads.

**4. Publish** — clears your YouTube playlist and repopulates it in Monday → Sunday order, with the playlist description updated to show the full weekly plan.

The first time you run it (`--init`), it scans the entire back-catalogue of each channel to build a rich library to plan from.

---

## How Classification Works

Titles lie. "30 Min Full Body Workout" could be anything — a sweaty HIIT session, a slow mobility flow, or a beginner bodyweight circuit. The only way to know is to actually listen to what the trainer says.

So that's what this tool does.

It fetches the first ~2.5 minutes of auto-generated captions from each video — the intro, where trainers almost always explain what you're about to do:

> *"Grab your dumbbells, we're doing 4 heavy compound sets today — this is an intermediate to advanced session, no jumping, all strength..."*

That transcript, combined with the title, description, and tags, gets sent to Claude Haiku which returns a structured classification:

| Field | Options |
|---|---|
| `workout_type` | HIIT, Strength, Mobility, Cardio, Other |
| `body_focus` | upper, lower, full, core, any |
| `difficulty` | beginner, intermediate, advanced |
| `has_warmup` | true / false |
| `has_cooldown` | true / false |

If a video has no captions, it falls back gracefully to title and description only.

**Cost-efficient by design:** rather than calling Claude once per video in sequence, all videos are submitted together via the [Anthropic Batch API](https://docs.anthropic.com/en/docs/build-with-claude/batch-processing) — 50% cheaper than standard API pricing and processed in parallel. Classifying an entire channel back-catalogue of ~2,000 videos costs around **$1–2 total**, and weekly incremental runs (10–30 new videos) cost just a few cents.

---

## Project Structure

```
youtube-workout-planner/
├── main.py                        Entry point (--init / --classify-only / --run / --dry-run)
├── config.yaml                    Your channels + weekly schedule (edit this)
├── requirements.txt
├── workout_library.db             SQLite database (auto-committed by CI after each run)
├── .github/
│   └── workflows/
│       └── weekly_plan.yml        GitHub Actions — runs every Sunday
├── scripts/
│   └── get_oauth_token.py         One-time local helper to generate OAuth refresh token
└── src/
    ├── db.py                      SQLite schema and helpers
    ├── scanner.py                 Fetch videos from YouTube channels
    ├── classifier.py              LLM classification of each video
    ├── planner.py                 Weekly plan generation logic
    └── playlist.py                YouTube playlist management (OAuth write access)
```

---

## Requirements

- **Python 3.10+**
- A Google account (for YouTube API + OAuth)
- An Anthropic account (for Claude video classification)
- A GitHub account (to host the repo and run Actions)

---

## Setup

### 1. Install Dependencies

```bash
cd youtube-workout-planner
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Google Cloud — YouTube API Key (read access)

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Project dropdown (top left) → **New Project** → name it `workout-planner` → **Create**
3. Left menu → **APIs & Services** → **Library** → search `YouTube Data API v3` → **Enable**
4. Left menu → **APIs & Services** → **Credentials** → **+ Create Credentials** → **API Key**
5. Copy the key and save it temporarily

### 3. Google Cloud — OAuth Credentials (playlist write access)

Still on the Credentials page:

1. **+ Create Credentials** → **OAuth client ID**
2. If prompted to configure consent screen:
   - Choose **External** → **Create**
   - Fill in App name (`Workout Planner`) and your email → **Save and Continue** through all steps
   - On the **Test users** step → **+ Add users** → add your own Google email → **Save**
3. Back on **Create OAuth client ID**:
   - Application type: **Desktop app** → Name: `workout-planner` → **Create**
4. Copy the **Client ID** and **Client Secret** from the popup
5. Click **Download JSON** → save it as `scripts/client_secret.json` (this file is gitignored)

### 4. Generate Your OAuth Refresh Token

```bash
python scripts/get_oauth_token.py
```

Your browser opens → log in with your Google account → click **Allow**.
The terminal prints three values — copy all of them:

```
YOUTUBE_CLIENT_ID       xxxxx.apps.googleusercontent.com
YOUTUBE_CLIENT_SECRET   GOCSPX-xxxxx
YOUTUBE_OAUTH_REFRESH_TOKEN   1//xxxxxxxxxxxxxxxxxx
```

### 5. Get an Anthropic API Key

1. Go to [console.anthropic.com](https://console.anthropic.com)
2. **API Keys** → **Create Key** → name it `workout-planner`
3. Copy the key (`sk-ant-...`)

> **Note:** Anthropic API credits are separate from a Claude Pro subscription. You need to add credits under **Plans & Billing** at [console.anthropic.com](https://console.anthropic.com). A $5 top-up comfortably covers the full initial classification run (~2,000+ videos) plus months of weekly runs.

### 6. Create Your YouTube Playlist

1. Open YouTube → **Your channel** → **Playlists** → **New playlist**
2. Name it `Weekly Workout Plan` → set visibility to **Unlisted** or **Public** → **Create**
3. Open the playlist and copy its ID from the URL:
   ```
   youtube.com/playlist?list=PLxxxxxxxxxxxxxxxx
                               ↑ copy this part
   ```
4. Paste it into `config.yaml`:
   ```yaml
   playlist:
     id: "PLxxxxxxxxxxxxxxxx"
   ```

### 7. Configure Your Channels and Schedule

Edit `config.yaml` — the channels are already set to your three channels. Adjust the weekly schedule to match your training split:

```yaml
schedule:
  monday:
    workout_type: Strength   # HIIT | Strength | Mobility | Cardio | Rest
    body_focus: upper        # upper | lower | full | core | any
    duration_min: 20         # minimum video length in minutes (optional, default 0)
    duration_max: 45         # maximum video length in minutes (optional, default 60)
    difficulty: any          # beginner | intermediate | advanced | any (default)
```

### 8. Run the First-Time Scan

Create a `.env` file in the project root (gitignored — never committed):

```bash
YOUTUBE_API_KEY=your_api_key
ANTHROPIC_API_KEY=your_anthropic_key
YOUTUBE_CLIENT_ID=your_client_id
YOUTUBE_CLIENT_SECRET=your_client_secret
YOUTUBE_OAUTH_REFRESH_TOKEN=your_refresh_token
```

Then run:

```bash
set -a && source .env && set +a
python main.py --init
```

This scans the full back-catalogue of all three channels and classifies every video.
Expect **20–40 minutes** on first run — only ever done once per channel.

> **If classification is interrupted** (e.g. API credits ran out), you don't need to re-scan. Just run:
> ```bash
> python main.py --classify-only
> ```
> This skips the channel scan and resumes classification from where it left off.

### 9. Preview Your First Plan

```bash
python main.py --dry-run
```

Prints the weekly plan without touching the playlist. Verify it looks sensible before pushing to GitHub.

### 10. Create a Private GitHub Repo and Push

```bash
git init
git add .
git commit -m "Initial commit"
```

On GitHub → [github.com/new](https://github.com/new) → name: `youtube-workout-planner` → **Private** → **Create**.

```bash
git remote add origin https://github.com/YOUR_USERNAME/youtube-workout-planner.git
git branch -M main
git push -u origin main
```

### 11. Add GitHub Secrets

Repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**.

| Secret | Value |
|--------|-------|
| `YOUTUBE_API_KEY` | From step 2 |
| `YOUTUBE_CLIENT_ID` | From step 4 |
| `YOUTUBE_CLIENT_SECRET` | From step 4 |
| `YOUTUBE_OAUTH_REFRESH_TOKEN` | From step 4 |
| `ANTHROPIC_API_KEY` | From step 5 |

### 12. Trigger a Test Run

Don't wait for Sunday — trigger it manually:

Repo → **Actions** → **Weekly Workout Plan** → **Run workflow** → **Run workflow**

Watch the logs. On success, open YouTube → your playlist → this week's videos appear in day order.

---

## Setup Checklist

```
☐ Python 3.10+
☐ pip install -r requirements.txt
☐ YouTube API key created
☐ OAuth client ID + secret created
☐ scripts/client_secret.json placed (gitignored — never committed)
☐ get_oauth_token.py run → refresh token copied
☐ Anthropic API key created
☐ YouTube playlist created → ID added to config.yaml
☐ config.yaml schedule adjusted to your training split
☐ python main.py --init  completed successfully
☐ python main.py --dry-run  plan looks correct
☐ GitHub private repo created
☐ git push done
☐ 5 GitHub Secrets added
☐ Manual Actions trigger → playlist refreshed on YouTube
```

---

## Configuration Reference

```yaml
# config.yaml

channels:
  - name: "TIFFxDAN"
    url: "https://www.youtube.com/@TIFFxDAN"
  - name: "JuiceandToya"
    url: "https://www.youtube.com/@JuiceandToya"
  - name: "HASfit"
    url: "https://www.youtube.com/@HASfit"

schedule:
  monday:
    workout_type: Strength   # HIIT | Strength | Mobility | Cardio | Rest
    body_focus: upper        # upper | lower | full | core | any
    duration_min: 20         # minimum video length in minutes (default: 0)
    duration_max: 45         # maximum video length in minutes (default: 60)
    difficulty: any          # beginner | intermediate | advanced | any (default)
  sunday:
    workout_type: Rest       # No video assigned on rest days
    body_focus: any
    duration_min: 0
    duration_max: 0

playlist:
  id: "PLxxxxxxxxxxxxxxxx"   # YouTube playlist ID to refresh each week

recency_boost_weeks: 24      # Videos newer than this (in weeks) get selection priority
```

---

## How the Weekly Plan Is Selected

For each day in your schedule, the planner:

1. Queries the library for videos matching `workout_type` + `body_focus` + duration limit
2. Excludes videos used in the last **8 weeks** (prevents repeats)
3. Scores remaining candidates:
   - **+100** if published within `recency_boost_weeks` (newer videos preferred)
   - **+40** if from a channel not yet picked this week (spreads across channels)
   - **+0–20** random jitter (keeps variety week to week)
4. Picks randomly from the top 3 scorers

If the strict query returns no candidates, it progressively relaxes constraints (history window → body focus) until a video is found.

---

## Adding or Removing a Channel

**Add a channel:**
```yaml
# config.yaml
channels:
  - name: "NewChannel"
    url: "https://www.youtube.com/@NewChannel"
```
Then run locally:
```bash
python main.py --init
```
`--init` is safe to re-run — existing videos are skipped, only the new channel is scanned.

**Remove a channel:**
Delete the entry from `config.yaml`. Existing videos from that channel stay in the DB but won't be selected for future plans.

---

## Ambitious Ideas for the Future

### 1. Adaptive Periodization
Right now your weekly schedule is fixed forever — every Monday is always Strength/Upper. A more powerful version would automatically cycle through structured training blocks: a build phase (higher volume, moderate intensity), a peak phase (lower volume, higher intensity), and a deload week — then repeat. The system would adjust which workout types and difficulty levels it selects each week based on where you are in the cycle, implementing real progressive programming without you ever touching `config.yaml`.

### 2. Preference Learning
A feedback loop that makes the plan smarter over time. After each week, you rate your sessions — loved it, skipped it, it was fine. Those signals feed back into the scoring algorithm permanently: creators you consistently enjoy get a long-term score boost, video styles you skip get suppressed, and sessions you abandon mid-week get flagged for reconsideration. Over months, the planner stops being a generic curator and starts feeling like it actually knows you.

### 3. Natural Language Rescheduling
A Telegram or WhatsApp bot that lets you modify your week in plain English. Message it *"I'm too sore for legs today, swap Wednesday for something lighter"* or *"I'm travelling Thursday and Friday, make it a 3-day week"* and it re-generates the plan and updates your YouTube playlist automatically. No config files, no code — just a message from wherever you are.

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `Channel not found` error on init | Double-check the channel URL in `config.yaml` — use the `@handle` format |
| OAuth token expired | Re-run `python scripts/get_oauth_token.py` and update the `YOUTUBE_OAUTH_REFRESH_TOKEN` GitHub Secret |
| YouTube API quota exceeded | Free quota (10,000 units/day) resets at midnight Pacific. Retry next day |
| `No video found for [day]` warning | Your library may lack videos for that type/focus — check classifications or loosen the schedule |
| Video misclassified | LLM classification has edge cases. Open `workout_library.db` in [DB Browser for SQLite](https://sqlitebrowser.org) and edit the `classifications` table manually |
| Classification interrupted mid-run | Run `python main.py --classify-only` — it skips already-classified videos and picks up from where it left off |
| Anthropic API credits exhausted | Top up at [console.anthropic.com](https://console.anthropic.com) → Plans & Billing. Note: API credits are separate from Claude Pro |
| GitHub Actions can't push the DB | Ensure the workflow has `contents: write` permission — check repo Settings → Actions → General |
