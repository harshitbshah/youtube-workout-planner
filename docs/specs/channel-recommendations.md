# Spec: Channel Recommendations with Thumbnails + Recommendation Engine

**Created:** 2026-03-11
**Status:** Ready for implementation
**Branch:** `claude/exercise-plan-with-gifs-b1bRg` (or new branch per phase)

---

## Problem

The current channel suggestion system is:
- A static hardcoded list of channel name strings per `LifeStage`
- Shown as plain text chips — no avatar, no subscriber count, no description
- Not personalised by goal (only by life stage)
- Clicking a chip triggers a YouTube search for the name — adds a round-trip and can return
  the wrong channel if the name is ambiguous
- Has no feedback loop — never improves as users accumulate

---

## Goal

Deliver channel recommendations that feel hand-picked and get smarter over time:

| Phase | What it unlocks | Self-improving? |
|---|---|---|
| **R1** — Rich curated channels | Thumbnails, fast one-click add, scored by profile+goal | No (static) |
| **R2** — Content-match scoring | Recommendations from your own library's classification data | Yes (grows with library) |
| **R3** — Collaborative filtering | "Users like you also use…" from real usage patterns | Yes (grows with users) |

Phases are independent and additive. Each can be shipped separately.

---

## Phase R1 — Rich curated channels with thumbnails

### User-facing changes

**Onboarding step 6 (Add channels):**
- Replace chip row with a **card grid** (2 columns mobile, 3 desktop)
- Each card shows: channel avatar (48px) | channel name (bold) | subscriber count | 1-line description | goal tags | "Add" button
- "Best match" badge on the top 1–2 cards (highest score for this user's profile+goal)
- One-click add: no search round-trip — channel ID is already known, add immediately
- Already-added cards show a "✓ Added" state (greyed, button disabled)
- "See all suggestions" toggle reveals remaining cards below the top 6

**Settings → Channels section:**
- Same card grid, scoped to user's profile+goal (read from their schedule preferences)
- Shown collapsed under "Discover channels" accordion

### Bootstrapping the curated data

**Step 1 — Discovery script**

New file: `scripts/discover_channels.py`

Run once to search YouTube Data API for top channels per fitness category and dump raw
results to `scripts/channel_candidates.json`. Review and prune manually.

```python
SEARCH_QUERIES = [
    "beginner home workout channel",
    "HIIT workout channel",
    "strength training YouTube channel",
    "powerlifting programming",
    "yoga for seniors",
    "mobility stretching channel",
    "bodyweight workout",
    "cardio workout channel",
]
# Uses channels.list + search.list YouTube Data API
# Returns: channelId, title, description, subscriberCount, thumbnailUrl
# Output: scripts/channel_candidates.json
```

**Step 2 — Manual curation**

Cross-reference `channel_candidates.json` against:
- `r/bodyweightfitness` wiki (community-vetted quality signal)
- `r/fitness` sidebar
- Any top-10 fitness channel article

Pick 25–35 channels. For each, tag manually:
```json
{
  "youtube_channel_id": "UCpQ34nbb_X6gMBBCXNQqHsQ",
  "name": "Heather Robertson",
  "description": "Daily workout plans, no equipment needed",
  "thumbnail_url": "https://yt3.ggpht.com/...",
  "subscriber_count": 2800000,
  "workout_types": ["HIIT", "Strength", "Cardio"],
  "difficulty": "beginner",
  "best_for_goals": ["Build a habit", "Lose weight", "Lose fat"],
  "best_for_profiles": ["beginner", "adult"],
  "equipment": "none",
  "avg_duration_min": 30
}
```

**Step 3 — Commit as static data**

Save final curated set to `api/data/curated_channels.json`.
This file is committed to the repo and loaded by the backend at startup.
Update it whenever a channel is added or a thumbnail URL goes stale.

### Scoring function

When serving suggestions, rank channels by score against the requesting user's profile:

```python
def score_channel(channel: dict, profile: str, goal: str, schedule_types: list[str]) -> int:
    score = 0
    if profile in channel["best_for_profiles"]:   score += 40
    if goal in channel["best_for_goals"]:          score += 30
    for t in schedule_types:
        if t in channel["workout_types"]:          score += 10  # up to +30
    # subscriber_count as tiebreaker (log scale, max 10 pts)
    score += min(10, int(math.log10(channel["subscriber_count"] + 1)) * 2)
    return score
```

Top 2 by score get a `"best_match": true` flag in the response.

### New endpoint: `GET /channels/curated`

```
GET /channels/curated?profile=adult&goal=Build+muscle&types=Strength,HIIT
Authorization: Bearer <token>
```

**Response (200):**
```json
[
  {
    "youtube_channel_id": "UCpQ34nbb_X6gMBBCXNQqHsQ",
    "name": "Heather Robertson",
    "description": "Daily workout plans, no equipment needed",
    "thumbnail_url": "https://yt3.ggpht.com/...",
    "subscriber_count": 2800000,
    "workout_types": ["HIIT", "Strength"],
    "difficulty": "beginner",
    "equipment": "none",
    "avg_duration_min": 30,
    "score": 80,
    "best_match": true,
    "already_added": false
  }
]
```

Sorted by score descending. `already_added` is true if the user already has this channel.

**Router file:** `api/routers/channels.py` (add to existing file)
**Path:** `/channels/curated`

### ChannelManager component changes

Update `Props` interface:
```typescript
interface Props {
  channels: ChannelResponse[];
  onChannelsChange: (channels: ChannelResponse[]) => void;
  // Remove: suggestions?: string[]
  // Add:
  profile?: string;       // passed from onboarding — drives curated fetch
  goal?: string;
  scheduleTypes?: string[];
  showCurated?: boolean;  // default false (settings page opts in)
}
```

New internal state:
```typescript
const [curated, setCurated] = useState<CuratedChannel[]>([]);
const [curatedLoading, setCuratedLoading] = useState(false);
const [showAll, setShowAll] = useState(false);
```

On mount (when `showCurated && profile`): fetch `GET /channels/curated`.

Render order:
1. "Recommended for you" heading (only if curated loaded and non-empty)
2. Top 6 cards (or all if `showAll`)
3. "See X more suggestions" toggle button
4. Existing search bar + search results (unchanged)
5. Existing added channels list (unchanged)

**CuratedChannelCard sub-component** (new, in same file or extracted):
- Avatar img (48×48, rounded-full, lazy)
- Name + "Best match" badge (indigo pill, only on top 2)
- Subscriber count formatted (e.g. "2.8M")
- Description line (1 line, truncated)
- Workout type tags (Badge components, max 2 shown)
- "Add" / "✓ Added" button

### New TypeScript types in `lib/api.ts`

```typescript
export interface CuratedChannel {
  youtube_channel_id: string;
  name: string;
  description: string;
  thumbnail_url: string | null;
  subscriber_count: number;
  workout_types: string[];
  difficulty: string;
  equipment: string;
  avg_duration_min: number;
  score: number;
  best_match: boolean;
  already_added: boolean;
}

export async function getCuratedChannels(
  profile: string,
  goal: string,
  types: string[]
): Promise<CuratedChannel[]>
```

---

## Phase R2 — Content-match scoring from library

### Concept

You already have `classifications` rows for every video in the system. You can compute
a profile for every channel in the DB:

```
Heather Robertson (in DB):
  workout_type dist:  Strength 45%, HIIT 35%, Cardio 20%
  difficulty dist:    beginner 60%, intermediate 40%
  avg_duration_min:   28
```

Compare this against the user's schedule preferences (which workout types and difficulties
they want) → score → rank.

**No new DB tables.** This is a pure query over `classifications` + `videos` + `channels`.

### What it unlocks

- Surfaces channels already in your DB that match the user's schedule, even if they're
  not in the hand-curated list
- Becomes more accurate as more videos are classified
- Personalized by the user's *actual configured schedule*, not just their life stage

### New endpoint: `GET /channels/recommended`

```
GET /channels/recommended
Authorization: Bearer <token>
```

Backend logic:
1. Read the requesting user's schedule (`schedules` table) to get desired workout types,
   difficulties, and durations
2. For all channels in the DB (across all users — this is cross-user data, but it's
   aggregated, not user-identifiable):

```sql
SELECT
  c.youtube_channel_id,
  c.name,
  cl.workout_type,
  cl.difficulty,
  COUNT(*) as count
FROM channels ch
JOIN videos v ON v.channel_id = ch.id
JOIN classifications cl ON cl.video_id = v.id
GROUP BY c.youtube_channel_id, c.name, cl.workout_type, cl.difficulty
```

3. Compute per-channel distribution, score against user's schedule
4. Filter out channels the user already has
5. Return top 10, sorted by match score

**Response:** same shape as `GET /channels/curated` (reuse `CuratedChannel` type), but
`thumbnail_url` may be null (not stored for non-curated channels yet).

### Thumbnail gap for R2

Channels discovered via classification won't have thumbnails unless they're also in the
curated list. Options (pick one at implementation time):

- **Option A:** Add `thumbnail_url` column to `channels` table; populate from YouTube
  API during channel scan (free, already fetching channel metadata)
- **Option B:** Fetch on-demand only when channel appears in recommendations (lazy, uses
  quota)
- **Option C:** Show a grey avatar placeholder for uncurated channels — acceptable for v1

**Recommendation:** Option A. Store `thumbnail_url` in `channels` during scan — it's
a one-line addition to the scanner and makes the whole system richer (settings page,
library page could use it too).

### Migration for Option A (migration 010 or 011)

```python
# Add to channels table:
thumbnail_url = Column(String, nullable=True)
```

Backfill: one-off script to fetch thumbnails for existing channels via YouTube Data API.

---

## Phase R3 — Collaborative filtering from usage patterns

### Concept

When a user swaps a video on their plan (via `PATCH /plan/{day}`), that's a negative
signal for that video/channel. When a video survives to the next week unchanged (not
swapped), that's a positive signal.

Track these signals → identify which channels consistently produce "kept" videos →
surface those channels to similar users.

### New table: `video_feedback` (migration 011 or 012)

```python
class VideoFeedback(Base):
    __tablename__ = "video_feedback"

    id         = Column(Integer, primary_key=True, autoincrement=True)
    user_id    = Column(String(36), ForeignKey("users.id"), nullable=False)
    video_id   = Column(String, ForeignKey("videos.id"), nullable=False)
    channel_id = Column(String(36), ForeignKey("channels.id"), nullable=False)
    signal     = Column(String, nullable=False)  # "kept" | "swapped"
    week_start = Column(Date, nullable=False)
    recorded_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("user_id", "video_id", "week_start"),
    )
```

### When to write feedback

**Swap signal (negative):** in `PATCH /plan/{day}` — when a video is replaced, write
`signal="swapped"` for the outgoing `video_id`.

**Kept signal (positive):** in `POST /plan/generate` — before overwriting the previous
week's plan, scan the outgoing week's rows. Any video that was NOT swapped (still
present in `program_history` as originally assigned) gets `signal="kept"`.

Both are append-only. No updates. Multiple weeks of feedback accumulate naturally.

### Channel quality score

Derived from feedback:
```python
def channel_quality_score(channel_id: str, db: Session) -> float:
    rows = db.query(VideoFeedback).filter(
        VideoFeedback.channel_id == channel_id
    ).all()
    if len(rows) < 3:      # not enough signal
        return 0.5         # neutral
    kept  = sum(1 for r in rows if r.signal == "kept")
    total = len(rows)
    return kept / total    # 0.0–1.0
```

### Similar-user channel recommendations

```python
def similar_user_channels(user_id: str, db: Session) -> list[str]:
    """Return channel IDs popular among users with the same profile."""
    # 1. Get this user's profile (life_stage, goal) from users table
    #    NOTE: life_stage + goal are not stored yet — see "User profile storage" below
    # 2. Find users with same profile
    # 3. Count which channels those users added (channels table)
    # 4. Exclude channels current user already has
    # 5. Sort by count * channel_quality_score, return top 10 channel IDs
```

### User profile storage (prerequisite for R3)

`life_stage` and `goal` are currently only frontend state — collected in onboarding but
never persisted to the DB. R3 needs them to find "similar users".

**Migration:** add to `users` table:
```python
life_stage = Column(String, nullable=True)   # "beginner"|"adult"|"senior"|"athlete"
goal       = Column(String, nullable=True)   # free text from GOALS constant
```

**Backend:** `PATCH /auth/me` already exists — extend it to also accept `life_stage`
and `goal` fields.

**Frontend:** after `PUT /schedule` in onboarding step 5, also call `PATCH /auth/me`
with `{life_stage: profile, goal: goal}`. This requires no UI change.

### New endpoint: `GET /channels/for-you`

```
GET /channels/for-you
Authorization: Bearer <token>
```

Backend logic:
1. Run `similar_user_channels()` → channel IDs from collaborative filtering
2. Run `GET /channels/recommended` logic (R2 content-match) → channel IDs from library
3. Merge: deduplicate, weight R3 results higher (more personalised)
4. Fetch channel metadata (name, thumbnail if stored) for final list
5. Return top 10

**Response:** same `CuratedChannel` shape. Adds `source` field:
```json
{ "source": "collaborative" | "content_match" | "curated" }
```

Frontend surfaces this as a subtle label: "Popular with users like you" vs "Matches
your schedule" vs "Editor's pick".

---

## UI: Unified "Discover channels" experience

After R1+R2+R3 are built, the Onboarding step 6 and Settings channels section show one
unified list, ranked by a blended score:

```
blended_score = (
  curated_score   * 0.3 +   # hand-curated match (R1)
  content_score   * 0.4 +   # classification match (R2)
  collab_score    * 0.3     # collaborative filtering (R3)
)
```

The `source` field on each card controls the label shown under the channel name:
- "Editor's pick" — only in curated list, no content/collab data yet
- "Matches your schedule" — content-match score > 0.6
- "Popular with users like you" — collab signal present

Until R3 has data (< ~20 users), blended_score degrades gracefully:
`collab_score` defaults to 0.5 (neutral) when `len(feedback_rows) < 3`.

---

## Files to create

| File | Purpose |
|---|---|
| `scripts/discover_channels.py` | One-off: YouTube API search → `channel_candidates.json` |
| `api/data/curated_channels.json` | Committed curated channel data (output of manual curation) |
| `api/services/recommender.py` | Scoring functions: `score_channel()`, `content_match_channels()`, `similar_user_channels()`, `blended_recommendations()` |
| `alembic/versions/010_add_channel_thumbnail.py` | Add `thumbnail_url` to `channels` table |
| `alembic/versions/011_add_user_profile.py` | Add `life_stage` + `goal` to `users` table |
| `alembic/versions/012_add_video_feedback.py` | `video_feedback` table |
| `tests/api/test_recommender.py` | Unit tests for scoring functions |
| `tests/api/test_curated_channels.py` | Unit tests for `GET /channels/curated` endpoint |
| `tests/integration/test_recommendations.py` | Integration tests |

## Files to modify

| File | Change |
|---|---|
| `api/models.py` | Add `VideoFeedback` model; `Channel.thumbnail_url`; `User.life_stage` + `User.goal` |
| `api/routers/channels.py` | Add `GET /channels/curated`, `GET /channels/recommended`, `GET /channels/for-you` |
| `api/routers/plan.py` | Record `swapped` feedback in `PATCH /plan/{day}` |
| `api/routers/plan.py` | Record `kept` feedback in `POST /plan/generate` |
| `api/routers/auth.py` | Accept `life_stage` + `goal` in `PATCH /auth/me` |
| `api/schemas.py` | Add `CuratedChannelResponse`, `VideoFeedbackSignal` schemas; extend `UserUpdateRequest` |
| `api/services/scanner.py` | Populate `thumbnail_url` during channel scan |
| `frontend/src/components/ChannelManager.tsx` | Replace chip row with card grid; fetch curated list |
| `frontend/src/app/onboarding/page.tsx` | Pass `profile` + `goal` + `scheduleTypes` to `ChannelManager`; call `PATCH /auth/me` after schedule save |
| `frontend/src/app/settings/page.tsx` | Pass `showCurated` to `ChannelManager` |
| `frontend/src/lib/api.ts` | Add `CuratedChannel` type + `getCuratedChannels()`, `getRecommendedChannels()`, `getForYouChannels()` |
| `CLAUDE.md` | Add new routes to API routes table |
| `docs/architecture.md` | Update schema + routes sections |

---

## Tests

### Unit tests — `tests/api/test_recommender.py`

1. `test_score_channel_profile_match` — profile match adds 40 pts
2. `test_score_channel_goal_match` — goal match adds 30 pts
3. `test_score_channel_type_match` — matching schedule types add 10 pts each
4. `test_score_channel_no_match` — zero overlap → score = subscriber tiebreaker only
5. `test_best_match_flag_top_two` — top 2 by score get `best_match=True`
6. `test_content_match_channels_returns_sorted` — mock classification data → channels sorted by type overlap
7. `test_content_match_excludes_user_channels` — channels user already has are excluded
8. `test_channel_quality_score_no_data` — fewer than 3 feedback rows → returns 0.5
9. `test_channel_quality_score_all_kept` → 1.0
10. `test_channel_quality_score_mixed` — 3 kept, 1 swapped → 0.75
11. `test_similar_user_channels_same_profile` — two users, same profile → channel of user B surfaces for user A
12. `test_similar_user_channels_excludes_already_added` — user already has channel → not returned

### Unit tests — `tests/api/test_curated_channels.py`

13. `test_curated_endpoint_returns_sorted_by_score` — profile+goal match scores correctly
14. `test_curated_endpoint_marks_already_added` — user has channel → `already_added=true`
15. `test_curated_endpoint_unauthenticated` → 401
16. `test_curated_endpoint_invalid_profile_graceful` — unknown profile → returns all channels unsorted (no crash)

### Unit tests — `tests/api/test_plan.py` additions

17. `test_patch_day_records_swapped_feedback` — `PATCH /plan/{day}` with a new video → `video_feedback` row written with `signal="swapped"` for old video
18. `test_generate_plan_records_kept_feedback` — previous week had un-swapped video → `signal="kept"` written before overwrite

### Integration tests — `tests/integration/test_recommendations.py`

19. `test_content_match_real_classifications` — insert channels+videos+classifications → `GET /channels/recommended` returns correct ranking
20. `test_feedback_accumulates_across_weeks` — 2 swaps + 1 kept for same channel → quality score = 0.33
21. `test_for_you_deduplicates_sources` — same channel in curated + content-match → appears once

---

## Implementation order (suggested)

### Phase R1 (ship first — standalone, no DB changes beyond thumbnail)

1. Run `scripts/discover_channels.py` → curate `api/data/curated_channels.json` manually
2. Migration 010: `channels.thumbnail_url`; update scanner to populate it
3. `api/services/recommender.py` — `score_channel()` + `load_curated()` only
4. `GET /channels/curated` endpoint + Pydantic schema
5. Unit tests 1–5, 13–16 — all passing
6. `ChannelManager.tsx` card grid + `getCuratedChannels()` in `lib/api.ts`
7. Onboarding: pass `profile` + `goal` + `scheduleTypes` props to ChannelManager

### Phase R2 (add after R1, no user-facing UX change needed)

8. `content_match_channels()` in `recommender.py`
9. `GET /channels/recommended` endpoint
10. Unit tests 6–7 — all passing
11. Integration test 19
12. Blend into `GET /channels/for-you` (weight 0.4)
13. Frontend: onboarding + settings call `getForYouChannels()` instead of `getCuratedChannels()`

### Phase R3 (add after R2, requires user base)

14. Store `life_stage` + `goal` in onboarding → `PATCH /auth/me`; migration 011
15. Migration 012: `video_feedback` table
16. Record `swapped` in `PATCH /plan/{day}`; record `kept` in `POST /plan/generate`
17. `channel_quality_score()` + `similar_user_channels()` in `recommender.py`
18. `GET /channels/for-you` blends all three sources
19. Unit tests 8–12, 17–18; integration tests 20–21
20. Frontend: `source` label on cards ("Popular with users like you" / "Matches your schedule" / "Editor's pick")

---

## Notes for implementing session

- **Migration numbers:** check `alembic/versions/` — currently at 008. The exercise-breakdown spec claims 009. Confirm actual state before numbering migrations here (010, 011, 012 assumed).
- **curated_channels.json size:** ~35 channels × ~10 fields = ~15 KB. Fine to commit.
- **Thumbnail URL stability:** YouTube channel thumbnail URLs are stable for years. No TTL/refresh needed for v1. If a thumbnail 404s, `<img>` falls back gracefully to a broken-image placeholder — add `onError` to swap to a grey avatar div.
- **Cross-user channel data in R2:** `GET /channels/recommended` queries classifications across all users. This is aggregate usage data (channel profiles), not user-identifiable. No privacy concern, but worth noting in architecture docs.
- **R3 minimum viable signal:** wait until you have ≥ 10 active users before surfacing collaborative recommendations — below that the signal is noise. Add a feature flag or simple count check in `similar_user_channels()`.
