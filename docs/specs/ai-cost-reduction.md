# Spec: Minimize Anthropic API Usage

**Last updated:** 2026-03-11
**Goal:** Reduce Anthropic classification costs through 8 layered optimizations.

## Implementation Status

| # | Feature | Status | Notes |
|---|---------|--------|-------|
| F1 | Max tokens 150 → 80 | ✅ Done (2026-03-10) | Phase A |
| F2 | 18-month video cutoff | ✅ Done (2026-03-10) | Phase A |
| F3 | First-scan channel cap (75 videos) | ✅ Done (2026-03-10) | Phase A, migration 006 |
| F4 | Skip inactive channels | ✅ Done (2026-03-10) | Phase A, migration 007 |
| F5 | Adaptive payload trimming | ✅ Done (2026-03-11) | Phase D — `_title_is_descriptive()` |
| F6 | Rule-based title pre-classifier | ✅ Done (2026-03-11) | Phase D — `title_classify()`, ~30–40% fewer AI calls |
| F7 | Per-user monthly budget cap | ⏳ Deferred | Low priority until real users |
| F8 | Global classification cache | ⏳ Deferred | High impact at scale; schema decision needed |

---

## Context

The classifier submits each unclassified video to Claude Haiku via the Batch API. Each request sends title + duration + tags + 800-char description + ~2.5 min transcript. Currently:
- Already uses Batch API (50% discount) and Haiku (cheapest model)
- 300-video cap per run (prevents runaway first scans)
- Multi-layer pre-filter at scan time (shorts, duration, title blocklist)
- But: same video is classified once per user who adds the same channel (no cross-user sharing), first scans of large channels are expensive, old videos are classified but never used by the planner

---

## Recommended Implementation Order (effort / impact)

| # | Feature | Effort | Impact |
|---|---------|--------|--------|
| 1 | Max tokens 150 → 80 | Trivial | Low (saves ~15% output tokens) |
| 2 | 18-month video cutoff | Trivial | Medium |
| 3 | First-scan channel cap | Small | High |
| 4 | Skip scan for inactive channels | Small | Medium |
| 5 | Adaptive payload trimming | Medium | Medium |
| 6 | Rule-based title pre-classifier | Medium | High (30-40% fewer AI calls) |
| 7 | Per-user monthly budget cap | Medium | Safety net |
| 8 | Global classification cache | Large | Highest (at scale) |

---

## Feature 1: Max Tokens Reduction

**Problem:** `max_tokens=150` is generous. Actual JSON response is ~50–70 tokens.

### Files changed
- `api/services/classifier.py`

### Implementation
1. Find `"max_tokens": 150` in `_build_batch_requests()`.
2. Change to `"max_tokens": 80`.
3. Add inline comment: `# JSON response is ~50-70 tokens; 80 gives headroom without waste`.

### Tests
- Unit: assert `max_tokens` in submitted batch request equals 80 (check the built payload).

### Frontend
None.

---

## Feature 2: 18-Month Video Cutoff

**Problem:** Old videos get classified but `src/planner.py` uses recency bias — videos >18 months old are almost never selected.

### Files changed
- `api/services/classifier.py`
- `.env.example` (document new env var)

### Implementation
1. Add env var `CLASSIFY_MAX_AGE_MONTHS` (default `18`).
2. In `_fetch_unclassified_for_user()`, compute cutoff:
   ```python
   max_age = int(os.getenv("CLASSIFY_MAX_AGE_MONTHS", "18"))
   cutoff = datetime.now(timezone.utc) - timedelta(days=max_age * 30)
   cutoff_str = cutoff.isoformat()
   ```
3. Add filter: `.filter(Video.published_at >= cutoff_str)`.
4. Place this filter after the existing `duration_sec >= 180` filter.

### Tests
- Unit: insert two videos — one 6 months old, one 24 months old. Assert only the recent one is fetched.
- Unit: set `CLASSIFY_MAX_AGE_MONTHS=1`, assert only 1-month-old videos are fetched.

### Frontend
None.

---

## Feature 3: First-Scan Channel Cap

**Problem:** Adding a channel with 500 videos immediately queues all 500 for classification.

### Files changed
- `api/models.py` — add `Channel.first_scan_done`
- `api/services/scanner.py` — cap YouTube API fetch on first scan
- `alembic/versions/006_add_channel_first_scan_done.py` — migration

### Schema change
```python
# Channel model — add:
first_scan_done = Column(Boolean, default=False, nullable=False, server_default="false")
```

### Migration (006)
```python
def upgrade():
    op.add_column("channels", sa.Column("first_scan_done", sa.Boolean(),
                  nullable=False, server_default="false"))

def downgrade():
    op.drop_column("channels", "first_scan_done")
```

### Implementation
1. Add `FIRST_SCAN_VIDEO_LIMIT = 75` constant in `scanner.py` (or read from `os.getenv("FIRST_SCAN_LIMIT", "75")`).
2. In `scan_channel(session, channel, ...)`:
   - Check `channel.first_scan_done`.
   - If `False`: pass `max_results=FIRST_SCAN_VIDEO_LIMIT` to the YouTube `playlistItems.list` pagination loop — stop fetching after N videos.
   - After saving videos, set `channel.first_scan_done = True` and commit.
   - If `True`: run existing full incremental scan (no cap).
3. The YouTube pagination loop already has a `while page_token` structure — add a `videos_fetched` counter and break when it hits the cap.

### Tests
- Unit: mock YouTube API returning 200 videos. Assert only 75 video rows saved when `first_scan_done=False`.
- Unit: assert `channel.first_scan_done` is `True` after first scan.
- Unit: mock returning 200 videos, `first_scan_done=True`. Assert all 200 are fetched (no cap).
- Integration: create channel, scan, assert `first_scan_done=True` in DB.

### Frontend
None (cap is transparent to user).

---

## Feature 4: Skip Scan for Inactive Channels

**Problem:** Weekly cron calls YouTube API for every user's every channel, even if a channel hasn't posted in months.

### Files changed
- `api/models.py` — add `Channel.last_video_published_at`
- `api/services/scanner.py` — skip logic
- `api/scheduler.py` — pass `skip_inactive=True` for cron runs
- `alembic/versions/007_add_channel_last_video_published_at.py`

### Schema change
```python
# Channel model — add:
last_video_published_at = Column(DateTime(timezone=True), nullable=True)
```

### Migration (007)
```python
def upgrade():
    op.add_column("channels", sa.Column("last_video_published_at",
                  sa.DateTime(timezone=True), nullable=True))

def downgrade():
    op.drop_column("channels", "last_video_published_at")
```

### Implementation
1. In `scan_channel(session, channel, *, skip_if_inactive=False)`:
   - If `skip_if_inactive=True` AND `channel.last_video_published_at` is not None AND `channel.last_video_published_at < now - 60 days` AND `channel.added_at < now - 30 days`:
     → log `"Skipping inactive channel {channel.name}"` and return `0`.
2. After saving new videos, update `channel.last_video_published_at` to the `max(published_at)` of videos just saved (or the most recent video in DB for this channel if no new videos found).
3. In `api/scheduler.py` weekly cron: call `scan_channel(..., skip_if_inactive=True)`.
4. In `api/routers/jobs.py` user-triggered scan: call `scan_channel(..., skip_if_inactive=False)` — always scan when user explicitly requests it.

### Tests
- Unit: channel with `last_video_published_at` = 90 days ago, `added_at` = 60 days ago, `skip_if_inactive=True` → returns 0, no YouTube API call.
- Unit: same channel but `skip_if_inactive=False` → YouTube API is called.
- Unit: channel with `last_video_published_at` = 30 days ago → NOT skipped (active enough).
- Unit: channel with `last_video_published_at = None` → NOT skipped (newly added, unknown).
- Unit: after scan saves videos, assert `last_video_published_at` is updated.

### Frontend
None.

---

## Feature 5: Adaptive Payload Trimming

**Problem:** Full payload (800-char description + transcript) is sent even for videos with clear, descriptive titles.

### Files changed
- `api/services/classifier.py`

### Implementation
1. Add helper `title_is_descriptive(title: str) -> bool`:
   ```python
   _DESCRIPTIVE_PATTERNS = re.compile(
       r"\b(\d+\s*min|\d+\s*minute|beginner|advanced|intermediate|hiit|strength|"
       r"cardio|yoga|pilates|mobility|stretching|full.?body|upper.?body|lower.?body|"
       r"core|abs|glutes|legs|arms|chest|back)\b",
       re.IGNORECASE
   )
   def title_is_descriptive(title: str) -> bool:
       return bool(_DESCRIPTIVE_PATTERNS.search(title))
   ```
2. In `_build_single_request(video: dict) -> dict`:
   - If `title_is_descriptive(video["title"])`:
     - Set `description_limit = 300` (not 800)
     - Set `include_transcript = False`
   - Else:
     - Set `description_limit = 800`
     - Set `include_transcript = True`
3. Apply limits when building the message content string.

### Tests
- Unit: `title_is_descriptive("30 Min Full Body HIIT")` → `True`.
- Unit: `title_is_descriptive("My Channel Update")` → `False`.
- Unit: descriptive title → built request has short description, no transcript section.
- Unit: ambiguous title → built request has full description + transcript.

### Frontend
None.

---

## Feature 6: Rule-Based Title Pre-Classifier

**Problem:** Many videos have titles that make their classification unambiguous — no AI needed.

### Files changed
- `api/services/classifier.py` — add `title_classify()`, call before batch building
- `tests/api/test_classifier.py` — new test cases

### Implementation
1. Add `title_classify(title: str, duration_sec: int) -> dict | None` in `classifier.py`:
   - Returns a full classification dict `{workout_type, body_focus, difficulty, has_warmup, has_cooldown}` if confident, else `None`.
   - Rules (match in order, return first hit):
     ```python
     RULES = [
       # (title_regex, duration_range, result_dict)
       (r"\b(hiit|interval)\b", (600, 7200),
        {"workout_type": "HIIT", "body_focus": "full body", "difficulty": "intermediate",
         "has_warmup": False, "has_cooldown": False}),
       (r"\b(yoga|stretch(ing)?|mobility|flexibility)\b", (0, 7200),
        {"workout_type": "Mobility", "body_focus": "full body", "difficulty": "beginner",
         "has_warmup": False, "has_cooldown": False}),
       (r"\b(strength|weight(s)?|dumbbell|barbell|resistance)\b", (600, 7200),
        {"workout_type": "Strength", "body_focus": "full body", "difficulty": "intermediate",
         "has_warmup": False, "has_cooldown": False}),
       (r"\b(cardio|run(ning)?|cycling|bike)\b", (600, 7200),
        {"workout_type": "Cardio", "body_focus": "full body", "difficulty": "intermediate",
         "has_warmup": False, "has_cooldown": False}),
       (r"\b(pilates)\b", (0, 7200),
        {"workout_type": "Mobility", "body_focus": "core", "difficulty": "intermediate",
         "has_warmup": False, "has_cooldown": False}),
     ]
     ```
   - Also check body focus overrides: if title contains `upper body` → set `body_focus="upper body"`, `lower body` → `"lower body"`, `core|abs` → `"core"`, `full body` → `"full body"`.
   - Also check difficulty overrides: `beginner` → `"beginner"`, `advanced` → `"advanced"`.
   - Also check `has_warmup=True` if title contains `warm.?up`, `has_cooldown=True` if `cool.?down`.
   - Return `None` if no rule matches (send to AI).

2. In `_fetch_unclassified_for_user()` (or in the pipeline step before building batch):
   - For each unclassified video, call `title_classify(video["title"], video["duration_sec"])`.
   - If returns a dict: create `Classification` row directly, skip adding to batch.
   - If returns `None`: add to batch for Anthropic.
3. Track pre-classified count separately in logs (add to `ScanLog` or log statement).

### Tests
- Unit: `title_classify("30 Min Full Body HIIT", 1800)` → workout_type=HIIT.
- Unit: `title_classify("Beginner Yoga Flow", 2400)` → workout_type=Mobility, difficulty=beginner.
- Unit: `title_classify("Upper Body Strength", 1800)` → body_focus=upper body.
- Unit: `title_classify("My Vlog", 300)` → None.
- Unit: end-to-end — insert 3 videos (2 obvious, 1 ambiguous). Assert 2 classifications created without API call, 1 submitted to batch.

### Frontend
None. (Could later show "X classified by rules, Y by AI" in admin stats — defer to backlog.)

---

## Feature 7: Per-User Monthly Classification Budget Cap

**Problem:** Users could trigger many manual scans, racking up large API bills.

### Files changed
- `api/models.py` — add `User.monthly_classify_budget`
- `api/services/classifier.py` — check budget before submitting
- `api/routers/jobs.py` — surface 429 response
- `api/routers/admin.py` — allow admin to update budget
- `alembic/versions/013_add_monthly_classify_budget.py`

### Schema change
```python
# User model — add:
monthly_classify_budget = Column(Integer, default=500, nullable=False, server_default="500")
# 0 = unlimited (admin override)
```

### Migration (013)
```python
def upgrade():
    op.add_column("users", sa.Column("monthly_classify_budget", sa.Integer(),
                  nullable=False, server_default="500"))

def downgrade():
    op.drop_column("users", "monthly_classify_budget")
```

### Implementation
1. Add `get_monthly_classified_count(session, user_id) -> int` in `classifier.py`:
   ```python
   from calendar import monthrange
   from datetime import date
   today = date.today()
   month_start = date(today.year, today.month, 1)
   # Sum classified from BatchUsageLog for this user this calendar month
   result = session.query(func.sum(BatchUsageLog.classified))\
       .filter(BatchUsageLog.user_id == user_id,
               BatchUsageLog.created_at >= month_start)\
       .scalar() or 0
   return result
   ```
2. At the start of `classify_for_user(session, user_id, ...)`:
   ```python
   user = session.get(User, user_id)
   budget = user.monthly_classify_budget
   if budget > 0:
       used = get_monthly_classified_count(session, user_id)
       remaining = budget - used
       if remaining <= 0:
           raise BudgetExceededError(f"Monthly classification budget of {budget} videos reached.")
       # Cap the batch to remaining budget
       videos = videos[:remaining]
   ```
3. In `_run_full_pipeline`, catch `BudgetExceededError` → set pipeline status to `"budget_exceeded"`.
4. In `GET /jobs/status`, return `stage="budget_exceeded"` with a user-friendly message.
5. In admin router: add `PATCH /admin/users/{id}/budget` endpoint accepting `{"monthly_classify_budget": int}`.

### Tests
- Unit: user with budget=10, already classified 10 this month → raises BudgetExceededError.
- Unit: user with budget=0 (unlimited) → no error regardless of usage.
- Unit: user with budget=100, used 90 → only 10 videos submitted in next batch.
- Unit: admin endpoint sets budget successfully, non-admin gets 403.

### Frontend
- `app/admin/page.tsx`: Add budget field to per-user table row. Show current month usage vs budget. Allow admin to edit and call `PATCH /admin/users/{id}/budget`.
- `app/dashboard/page.tsx`: If `jobs/status` returns `stage="budget_exceeded"`, show a dismissible warning banner explaining the monthly limit.

---

## Feature 8: Global Classification Cache (Cross-User Sharing)

**Problem:** The same YouTube video is classified multiple times when multiple users add the same channel. Additionally, `Video.id` is the YouTube video ID (global PK), so if User B adds a channel already scanned by User A, User B's scan skips insertion (video exists with User A's `channel_id`) — User B gets no videos at all.

### Root cause & fix scope
This requires two changes:
1. Fix the `Video` dedup bug (User B gets no videos from shared channels)
2. Share classifications across users (don't re-classify same YouTube video)

### Files changed
- `api/models.py` — new `GlobalClassificationCache` table
- `api/services/scanner.py` — fix dedup logic for shared channels
- `api/services/classifier.py` — check cache before batch, write cache after
- `alembic/versions/014_add_global_classification_cache.py`

### Schema change — new table
```python
class GlobalClassificationCache(Base):
    __tablename__ = "global_classification_cache"
    youtube_video_id = Column(String, primary_key=True)   # YouTube video ID
    workout_type     = Column(String, nullable=False)
    body_focus       = Column(String, nullable=False)
    difficulty       = Column(String, nullable=False)
    has_warmup       = Column(Boolean, default=False)
    has_cooldown     = Column(Boolean, default=False)
    cached_at        = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
```

### Migration (014)
```python
def upgrade():
    op.create_table(
        "global_classification_cache",
        sa.Column("youtube_video_id", sa.String(), primary_key=True),
        sa.Column("workout_type", sa.String(), nullable=False),
        sa.Column("body_focus", sa.String(), nullable=False),
        sa.Column("difficulty", sa.String(), nullable=False),
        sa.Column("has_warmup", sa.Boolean(), default=False),
        sa.Column("has_cooldown", sa.Boolean(), default=False),
        sa.Column("cached_at", sa.DateTime(timezone=True)),
    )

def downgrade():
    op.drop_table("global_classification_cache")
```

### Part A: Fix scanner dedup bug for shared channels
In `api/services/scanner.py`, when processing a video whose ID already exists in the DB:
- Current: `if session.get(Video, v["id"]): continue` (skips entirely)
- New: check if the existing `Video` row belongs to the current user's channel:
  ```python
  existing = session.get(Video, v["id"])
  if existing:
      if existing.channel_id != channel.id:
          # Video exists but under a different user's channel.
          # Create a second Video row is NOT possible (PK conflict).
          # Instead: if this channel has no association, we treat the
          # existing video as belonging to this channel for query purposes.
          # Simplest fix: store video once globally, remove channel_id FK from Video,
          # add a user_channel_videos join table.
          # Pragmatic short-term fix: skip (accept limitation), log a warning.
          # Recommended: see "Long-term schema fix" below.
          pass
      continue
  ```

  **Long-term schema fix (recommended):**
  Remove `channel_id` from `Video`. Add `UserChannelVideo(user_id, channel_id, video_id)` join table. This allows the same YouTube video to be associated with multiple users' channels. The classifier query changes from joining `Video → Channel → user_id` to joining `UserChannelVideo → user_id`.

  This is the correct fix but requires a larger migration and query refactor. **Implement as a follow-up after the cache is in place.**

  **Short-term pragmatic fix:** When scanning a channel, if `Video.channel_id != channel.id` for an existing video, reassign `Video.channel_id = channel.id` only if the old channel belongs to the same user. Cross-user collisions: log warning and skip (cache still helps for the classification step).

### Part B: Classification cache
1. In `classify_for_user()`, after `_fetch_unclassified_for_user()` returns video list:
   ```python
   to_classify = []
   for video in videos:
       cached = session.get(GlobalClassificationCache, video["id"])
       if cached:
           # Write Classification row from cache — no API call
           session.merge(Classification(
               video_id=video["id"],
               workout_type=cached.workout_type,
               body_focus=cached.body_focus,
               difficulty=cached.difficulty,
               has_warmup=cached.has_warmup,
               has_cooldown=cached.has_cooldown,
               classified_at=datetime.now(timezone.utc).isoformat(),
           ))
           cache_hits += 1
       else:
           to_classify.append(video)
   session.commit()
   ```
2. After saving Anthropic results for each video, also write to `GlobalClassificationCache`:
   ```python
   session.merge(GlobalClassificationCache(
       youtube_video_id=video_id,
       workout_type=cls.workout_type,
       ...
   ))
   ```
3. The rule-based pre-classifier (Feature 6) should also write to cache.

### Tests
- Unit: video ID exists in `GlobalClassificationCache` → `Classification` row created, no Anthropic call.
- Unit: video ID not in cache → added to batch for Anthropic.
- Unit: after Anthropic classifies, `GlobalClassificationCache` row is created.
- Integration: two users add same YouTube channel. Scan user A → classifications saved + cache populated. Scan user B → cache hits, no Anthropic batch submitted.

### Frontend
None directly. Admin stats page could show "Cache hit rate: X%" — defer to backlog.

---

## Migration Sequence

| Migration | Number | Adds | Status |
|-----------|--------|------|--------|
| First-scan cap | 006 | `channels.first_scan_done` | ✅ Live |
| Inactive channel skip | 007 | `channels.last_video_published_at` | ✅ Live |
| Graceful failure | 008 | `users.last_scan_error` | ✅ Live |
| Monthly budget (F7) | 013 | `users.monthly_classify_budget` | ⏳ Deferred |
| Global cache (F8) | 014 | `global_classification_cache` table | ⏳ Deferred |

> Note: 009–012 are claimed by other specs. See [migrations-roadmap.md](migrations-roadmap.md) for the full sequence.

Run `alembic upgrade head` after adding migrations.

---

## Verification (end-to-end testing)

```bash
# 1. Run unit tests
.venv/bin/pytest tests/api/ -q

# 2. Run integration tests
.venv/bin/pytest tests/integration/ -q

# 3. Manual smoke test — start app, add a channel with obvious-title videos,
#    trigger scan, check admin stats for AI token usage vs pre-classified count.

# 4. Check BatchUsageLog table to confirm token counts are lower:
#    SELECT SUM(input_tokens), SUM(output_tokens), SUM(classified)
#    FROM batch_usage_log WHERE created_at > now() - interval '1 day';
```

---

## Docs to Update After Implementation

- `PROGRESS.md` — update phase and task checklist
- `docs/architecture.md` — add `GlobalClassificationCache` table, `UserMonthlyUsage` logic, new Channel columns
- `docs/backlog.md` — add "long-term Video schema fix (UserChannelVideo join table)", "admin cache hit rate stat"
- `CLAUDE.md` — add new env vars (`CLASSIFY_MAX_AGE_MONTHS`, `FIRST_SCAN_LIMIT`), update API routes table for new admin endpoint
