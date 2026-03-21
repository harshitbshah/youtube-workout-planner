# Spec: Exercise Breakdown with GIFs

**Created:** 2026-03-11
**Status:** Ready for implementation
**Branch:** `claude/exercise-plan-with-gifs-b1bRg`
**Linked issue:** harshitbshah/youtube-workout-planner - exercise-plan-with-gifs

---

## Goal

When a user views their weekly plan on the dashboard, they can expand any day card to
see a structured exercise list extracted from that video, with an illustrative GIF for
each exercise. The breakdown is generated on-demand the first time a user opens it and
cached forever (the video doesn't change).

---

## User-facing behaviour

1. Each day card on `/dashboard` gains an **"Exercises"** expand button (chevron icon).
2. Clicking it opens an inline panel below the card (not a modal - keeps layout stable
   on mobile).
3. The panel shows a loading skeleton while the extraction runs (first time only).
4. Each exercise is rendered as a row: **GIF thumbnail | name | sets × reps / duration**.
5. If no breakdown can be extracted (no description + no transcript), the panel shows:
   *"No exercise list found for this video."*
6. GIF is omitted per exercise if no match is found in the GIF source - the text row
   is still shown.
7. The breakdown is **read-only** - no editing in v1.

---

## Architecture

### Tiered extraction (cost-first)

```
Tier 1 - Parse description (FREE, ~0 extra tokens)
  ↓ description has ≥ 3 timestamp/exercise lines?
  ✅ send description to Claude for structuring (~300 tokens)
  ❌ fall through to Tier 2

Tier 2 - Fetch full transcript (~4,000–9,000 tokens input)
  ↓ transcript available?
  ✅ send to Claude for exercise extraction
  ❌ store empty result, show "not found" message

Either way → cache result in `exercise_breakdowns` table forever
```

**Cost estimate:**
- Tier 1 (description) hit: ~$0.0002 per video (300-tok Claude Haiku call)
- Tier 2 (transcript) hit: ~$0.007 per video
- Expected split: ~75% Tier 1 (workout creators always list exercises), ~20% Tier 2,
  ~5% no result
- Lifetime cost per video: paid exactly once, then $0 forever

### GIF sourcing

Use the **ExerciseDB** dataset (open-source fork, no API key required):

- Repo: `yuhonas/free-exercise-db` on GitHub - 800+ exercises with hosted GIF URLs
  (`https://raw.githubusercontent.com/yuhonas/free-exercise-db/main/exercises/<id>/0.gif`)
- Download once and store as a local JSON lookup table at
  `api/data/exercise_db.json` (exercise name → gif_url + aliases)
- Matching: lowercase + strip punctuation fuzzy match against the extracted exercise names
- No API key, no rate limits, no ongoing cost

If no match is found in the local DB: omit the GIF for that exercise (graceful
degradation). Do not call GIPHY/Tenor - too generic, unreliable quality, API key
overhead for v1.

---

## Data model

### New table: `exercise_breakdowns` (migration 010)

```python
class ExerciseBreakdown(Base):
    __tablename__ = "exercise_breakdowns"

    video_id    = Column(String, ForeignKey("videos.id"), primary_key=True)
    exercises   = Column(Text, nullable=False)   # JSON-encoded list (see schema below)
    source      = Column(String, nullable=False)  # "description" | "transcript" | "none"
    created_at  = Column(DateTime(timezone=True), server_default=func.now())

    video = relationship("Video", back_populates="breakdown")
```

Add to `Video` model:
```python
breakdown = relationship("ExerciseBreakdown", back_populates="video",
                         uselist=False, cascade="all, delete-orphan")
```

### `exercises` JSON schema

```json
[
  {
    "name": "Goblet Squat",
    "sets": 3,
    "reps": "12",
    "duration_sec": null,
    "notes": "hold for 2s at bottom",
    "gif_url": "https://raw.githubusercontent.com/yuhonas/free-exercise-db/main/exercises/goblet-squat/0.gif"
  },
  {
    "name": "Rest",
    "sets": null,
    "reps": null,
    "duration_sec": 30,
    "notes": null,
    "gif_url": null
  }
]
```

Rules:
- `reps` is a string to handle "10–12", "AMRAP", "to failure"
- `duration_sec` is an int for timed exercises (planks, wall sits), null for rep-based
- `gif_url` is null if no match found in local exercise DB
- `sets` is null for one-off exercises (warm-up circuits, flows)
- Empty array (`[]`) stored when source is `"none"` - means we tried and found nothing

---

## Backend

### New file: `api/services/exercise_extractor.py`

Responsibilities:
1. `_is_description_sufficient(description: str) -> bool`
   - Returns True if description has ≥ 3 lines that look like exercises
   - Heuristic: count lines matching `r'(\d+[:\.]\d+)|([\dx]+\s*sets?)|(reps?)|(min|sec)'`
   - Threshold: ≥ 3 matches → sufficient
2. `_extract_from_description(description: str) -> list[dict]`
   - Sends description to Claude Haiku with a structured extraction prompt
   - Returns parsed exercise list
3. `_extract_from_transcript(video_id: str) -> list[dict]`
   - Fetches FULL transcript (not just intro - exercises can be mid-video)
   - Reuses `YouTubeTranscriptApi` from `src/classifier.py`
   - Sends to Claude Haiku for extraction
   - Returns parsed exercise list; `[]` if transcript unavailable
4. `_match_gifs(exercises: list[dict]) -> list[dict]`
   - Loads `api/data/exercise_db.json` (cached in module-level variable after first load)
   - For each exercise: fuzzy-matches name → appends `gif_url` or `null`
   - Returns updated list
5. `get_or_create_breakdown(video: Video, db: Session) -> ExerciseBreakdown`
   - Check DB cache first - return immediately if found
   - Otherwise: run tiered extraction → match GIFs → write to DB → return

### New file: `api/data/exercise_db.json`

Derived from `yuhonas/free-exercise-db`. Structure:
```json
{
  "goblet squat": {
    "gif_url": "https://raw.githubusercontent.com/.../0.gif",
    "aliases": ["goblet squats", "kb goblet squat"]
  },
  "romanian deadlift": {
    "gif_url": "...",
    "aliases": ["rdl", "stiff leg deadlift"]
  }
}
```

**Generation script:** `scripts/build_exercise_db.py`
- Downloads the raw JSON from the free-exercise-db repo
- Normalises names to lowercase, strips punctuation
- Outputs `api/data/exercise_db.json`
- Run once at setup; re-run to update
- The generated file IS committed to the repo (small, static, avoids runtime download)

### New endpoint: `GET /plan/{day}/exercises`

```
GET /plan/{day}/exercises
Authorization: Bearer <token>
```

**Response (200):**
```json
{
  "video_id": "abc123",
  "source": "description",
  "cached": true,
  "exercises": [
    {
      "name": "Goblet Squat",
      "sets": 3,
      "reps": "12",
      "duration_sec": null,
      "notes": null,
      "gif_url": "https://..."
    }
  ]
}
```

**Response (204):** No video assigned to this day (rest day).

**Response (503):** Extraction failed (log error, do not surface raw exception to client).

Logic:
1. Look up current week's plan for `day` from `ProgramHistory`
2. If rest day (null `video_id`): return 204
3. Call `get_or_create_breakdown(video, db)` from `exercise_extractor.py`
4. Return breakdown

**Router file:** `api/routers/exercises.py`
**Registration:** add `app.include_router(exercises.router)` in `api/main.py`
**Prefix:** `/plan` (keeps it consistent - it IS a plan sub-resource)

### Claude prompt (exercise extraction)

```
You are extracting the exercise list from a workout video's text.

Return a JSON array. Each element must have:
  - "name": exercise name (string)
  - "sets": number of sets (integer or null)
  - "reps": reps per set (string or null, e.g. "12", "10-12", "AMRAP")
  - "duration_sec": duration in seconds for timed exercises (integer or null)
  - "notes": form cue or modification (string or null)

Rules:
  - Omit warm-up/cool-down headers - include their exercises as normal rows
  - "Rest" periods are valid rows (sets=null, duration_sec=30)
  - If a field is unknown, use null - never guess
  - Return ONLY valid JSON, no explanation

Text:
{text}
```

Use `claude-haiku-4-5-20251001`, `max_tokens=800` (exercise lists can be long).
Do NOT use the Batch API - this is synchronous and user-facing.

---

## Frontend

### Dashboard day card changes (`app/dashboard/page.tsx`)

1. Add `expandedDay: string | null` state (only one day expanded at a time).
2. Add `breakdowns: Record<string, ExerciseBreakdown | null>` state.
3. "Exercises" button on each non-rest day card:
   - Chevron-down icon (rotates to chevron-up when open)
   - Calls `GET /plan/{day}/exercises` on first expand; subsequent opens use cached state
   - Shows loading skeleton (3 rows of grey bars) while in-flight
4. Expanded panel (inline below card, above the next card in the grid):
   - Scrollable up to 400px, then overflow-y scroll
   - Each exercise row: `[GIF 48×48] [Name bold] [sets×reps or duration]`
   - GIF renders as `<img>` with lazy loading; no GIF = empty 48px spacer (keeps alignment)
   - "No exercise list found for this video." if exercises array is empty

### New TypeScript types in `lib/api.ts`

```typescript
export interface Exercise {
  name: string;
  sets: number | null;
  reps: string | null;
  duration_sec: number | null;
  notes: string | null;
  gif_url: string | null;
}

export interface ExerciseBreakdown {
  video_id: string;
  source: "description" | "transcript" | "none";
  cached: boolean;
  exercises: Exercise[];
}

export async function getPlanDayExercises(day: string): Promise<ExerciseBreakdown | null> {
  // returns null on 204 (rest day)
}
```

---

## Files to create

| File | Purpose |
|---|---|
| `api/services/exercise_extractor.py` | Tiered extraction + GIF matching logic |
| `api/routers/exercises.py` | `GET /plan/{day}/exercises` endpoint |
| `api/data/exercise_db.json` | Local exercise name → GIF URL lookup table |
| `scripts/build_exercise_db.py` | One-off script to generate exercise_db.json |
| `alembic/versions/010_add_exercise_breakdowns.py` | Migration: exercise_breakdowns table |
| `tests/api/test_exercise_extractor.py` | Unit tests (see below) |
| `tests/integration/test_exercises_api.py` | Integration tests |

## Files to modify

| File | Change |
|---|---|
| `api/models.py` | Add `ExerciseBreakdown` model + `Video.breakdown` relationship |
| `api/main.py` | Register `exercises` router |
| `api/schemas.py` | Add `ExerciseRow`, `ExerciseBreakdownResponse` Pydantic schemas |
| `frontend/src/app/dashboard/page.tsx` | Expand button, breakdown panel, API call |
| `frontend/src/lib/api.ts` | `Exercise`, `ExerciseBreakdown` types + `getPlanDayExercises()` |
| `CLAUDE.md` | Add new route + model to tables |
| `docs/architecture.md` | Update schema + routes sections |

---

## Tests

### Unit tests (`tests/api/test_exercise_extractor.py`)

1. `test_description_sufficient_with_timestamps` - description with 3+ timestamped lines → `_is_description_sufficient()` returns True
2. `test_description_insufficient_short` - 2-line description → returns False
3. `test_description_insufficient_no_exercises` - long prose description → returns False
4. `test_extract_from_description_returns_list` - mock Claude response → parsed correctly
5. `test_extract_from_description_handles_claude_error` - Claude raises exception → returns []
6. `test_extract_from_transcript_no_transcript` - `TranscriptsDisabled` → returns []
7. `test_match_gifs_exact_match` - "goblet squat" → gif_url populated
8. `test_match_gifs_alias_match` - "rdl" → gif_url from Romanian deadlift alias
9. `test_match_gifs_no_match` - "pulsing burpee variation" → gif_url null
10. `test_get_or_create_breakdown_cache_hit` - pre-existing DB row → no Claude call
11. `test_get_or_create_breakdown_tier1` - sufficient description → calls description path, not transcript
12. `test_get_or_create_breakdown_tier2` - insufficient description → calls transcript path
13. `test_get_or_create_breakdown_writes_db` - result stored in exercise_breakdowns table

### Unit tests (`tests/api/test_exercises_api.py`)

14. `test_get_exercises_rest_day` - rest day (null video_id) → 204
15. `test_get_exercises_no_plan` - no plan generated yet → 404
16. `test_get_exercises_cached` - cached breakdown → 200 with exercises
17. `test_get_exercises_unauthenticated` → 401
18. `test_get_exercises_invalid_day` - "funday" → 422

### Integration tests (`tests/integration/test_exercises_api.py`)

19. `test_exercise_breakdown_persisted` - call endpoint twice; assert DB row written once
20. `test_exercise_breakdown_user_isolation` - user A's plan day → cannot see user B's
21. `test_exercise_breakdown_rest_day` - rest day in real DB → 204

---

## Environment variables

No new env vars required. The feature uses:
- `ANTHROPIC_API_KEY` - already set
- GIF source is static local file - no new keys

---

## Out of scope for v1

- Editing/correcting the extracted exercise list
- User-uploaded custom GIFs
- Ordering exercises (trust the extraction order)
- Completed exercise tracking per exercise (only per-day tracking exists)
- Searching the library by exercise name
- ExerciseDB RapidAPI (requires paid key; local file is sufficient for v1)

---

## Open questions for implementing session

1. **GIF loading UX:** lazy-load images with `loading="lazy"` to avoid blocking the
   card render. Consider a blurred placeholder while GIF loads.
2. **Transcript length cap:** the full transcript can be 9,000+ tokens. Consider capping
   at first 4,000 tokens (covers ~60% of a 45-min video) to save cost, since most
   exercise lists are front-loaded. Add `EXERCISE_TRANSCRIPT_MAX_TOKENS` env var if needed.
3. **exercise_db.json size:** the full yuhonas dataset is ~800 exercises × ~5 fields =
   ~200 KB. Fine to commit. Only build/update it when the dataset is stale.
4. **Fuzzy matching library:** `difflib.SequenceMatcher` from stdlib is sufficient -
   no need to add a dependency. Use `cutoff=0.8` ratio.
5. **Migration number:** **010**. Migration 009 is reserved for AI Profile Enrichment user
   profile fields. See [migrations-roadmap.md](migrations-roadmap.md) for the
   full sequence before writing the migration file.

---

## Implementation order (suggested)

1. `scripts/build_exercise_db.py` → generate `api/data/exercise_db.json`
2. Migration 010 + `ExerciseBreakdown` model
3. `api/services/exercise_extractor.py` (with full unit test suite)
4. `api/routers/exercises.py` + schema + register in `main.py`
5. Unit + integration tests - all passing
6. Frontend: dashboard expand button + panel
7. Checkpoint docs update
