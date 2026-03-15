# Spec: Lazy Classification — Plan-First, Classify-Lazily

**Last updated:** 2026-03-15
**Goal:** Minimise time to first plan and Anthropic API spend by classifying only what is needed to generate the plan, and deferring everything else to the background.

---

## Problem

Today's pipeline always classifies **all** unclassified videos before generating the plan:

```
Scan (75 videos/channel) → Classify ALL → Generate plan
```

The user is blocked on the Anthropic Batch API — which can take minutes — even though the planner only needs a handful of classified videos per schedule slot. The bottleneck is unnecessary.

---

## Core Idea

Before calling Anthropic, check whether the already-classified pool (including rule-based hits) is sufficient to fill the weekly plan. If yes, generate the plan immediately and run remaining classification in the background.

```
Scan
  ↓
Rule-classify all scanned videos  [free, ~instant]
  ↓
can_fill_plan?
  ├── YES → Generate plan immediately
  │         Background: classify remaining videos (non-blocking)
  │
  └── NO  → Build targeted mini-batch for gap slots only
             Wait for mini-batch
             Generate plan
             Background: classify remaining videos
```

---

## Key Concepts

### `can_fill_plan(user_id, db, min_candidates=3) → bool`

Queries the classified pool against the user's schedule. Returns `True` if every schedule slot has at least `min_candidates` matching videos.

"Matching" uses the same logic as the planner's Tier 4 query (any body focus, no history window, no channel limit) — the loosest meaningful filter.

**`min_candidates = 3`** — gives the planner enough choice to avoid same-video repeats across weeks. Configurable via env var `MIN_PLAN_CANDIDATES` (default `3`).

### Targeted mini-batch

When some slots have zero or too few candidates:

1. Identify the **gap slot types** (workout_types with < `min_candidates` candidates).
2. From the pool of unclassified videos, select only those whose titles suggest the missing type using the existing `_title_is_descriptive()` / keyword heuristics.
3. Cap the mini-batch at `max(gap_count × 5, 10)` — enough to fill gaps with margin, not the full library.
4. Submit this small batch to Anthropic, wait for results, then generate plan.
5. Remaining unclassified videos go to background.

### Background classification

After the plan is generated, remaining unclassified videos are submitted to Anthropic as a standard batch — same as today, but non-blocking relative to plan generation. The library fills in over the next few minutes while the user is already viewing their plan.

---

## Weekly Scan Behaviour

On the weekly cron, the same logic applies but the threshold is even easier to meet — the library is already rich from previous weeks. Most weeks:

```
Incremental scan (only new videos since last scan)
  ↓
Rule-classify new videos
  ↓
can_fill_plan? → almost always YES
  ↓
Generate plan immediately, skip Anthropic entirely
```

Anthropic is only called on weekly scans when the user's schedule has a workout type with a very thin classified pool (e.g., they just added a new channel of a type they didn't have before).

---

## Expected Impact

| Scenario | Today | After |
|---|---|---|
| Onboarding — titles descriptive (common) | Classify 75+ videos | 0 Anthropic calls |
| Onboarding — titles vague | Classify 75+ videos | Classify 5–15 (targeted) |
| Weekly scan — 3 new videos | 3 Anthropic calls | 0 (rule-based sufficient) |
| Weekly scan — new channel added | Up to 75 new calls | 5–15 (targeted) |

Time to first plan: drops from "wait for full batch (minutes)" to "rule classify + check (seconds)".

---

## Implementation Plan

### Step 1 — `can_fill_plan()` in `planner.py`

```python
MIN_PLAN_CANDIDATES = int(os.getenv("MIN_PLAN_CANDIDATES", "3"))

def can_fill_plan(user_id: str, session: Session) -> bool:
    """
    Returns True if every non-rest schedule slot has at least MIN_PLAN_CANDIDATES
    classified videos matching its workout_type + duration range.
    Uses Tier-4 style query: any body_focus, no history window, no channel limit.
    """
    slots = session.query(Schedule).filter(Schedule.user_id == user_id).all()
    for slot in slots:
        if slot.workout_type is None:
            continue  # rest day
        count = (
            session.query(func.count(Classification.video_id))
            .join(Video, Video.id == Classification.video_id)
            .join(UserChannel, UserChannel.channel_id == Video.channel_id)
            .filter(
                UserChannel.user_id == user_id,
                func.lower(Classification.workout_type) == slot.workout_type.lower(),
                Video.duration_sec >= slot.duration_min * 60,
                Video.duration_sec <= slot.duration_max * 60,
            )
            .scalar()
        )
        if count < MIN_PLAN_CANDIDATES:
            return False
    return True
```

### Step 2 — `get_gap_types()` in `planner.py`

```python
def get_gap_types(user_id: str, session: Session) -> list[dict]:
    """
    Returns list of {workout_type, duration_min, duration_max} for slots
    that have fewer than MIN_PLAN_CANDIDATES classified candidates.
    """
    slots = session.query(Schedule).filter(Schedule.user_id == user_id).all()
    gaps = []
    for slot in slots:
        if slot.workout_type is None:
            continue
        count = ... # same query as above
        if count < MIN_PLAN_CANDIDATES:
            gaps.append({
                "workout_type": slot.workout_type,
                "duration_min": slot.duration_min,
                "duration_max": slot.duration_max,
            })
    return gaps
```

### Step 3 — `build_targeted_batch()` in `classifier.py`

```python
TARGETED_BATCH_MULTIPLIER = 5  # candidates per gap slot

def build_targeted_batch(
    user_id: str,
    gap_types: list[dict],
    session: Session,
) -> list[dict]:
    """
    Returns a subset of unclassified videos most likely to fill the given gaps.
    Selects videos whose titles match the missing workout types via keyword heuristics.
    Capped at max(len(gap_types) * TARGETED_BATCH_MULTIPLIER, 10).
    """
    unclassified = _fetch_unclassified_for_user(user_id, session)
    cap = max(len(gap_types) * TARGETED_BATCH_MULTIPLIER, 10)
    gap_type_names = {g["workout_type"].lower() for g in gap_types}

    # Keyword map — same patterns as rule-based pre-classifier
    TYPE_KEYWORDS = {
        "hiit":      re.compile(r"\b(hiit|interval|tabata)\b", re.I),
        "strength":  re.compile(r"\b(strength|weight|dumbbell|barbell|resistance|lifting)\b", re.I),
        "cardio":    re.compile(r"\b(cardio|run|cycling|bike|walk)\b", re.I),
        "mobility":  re.compile(r"\b(yoga|stretch|mobility|flexibility|pilates)\b", re.I),
    }

    targeted = []
    remainder = []
    for v in unclassified:
        matched = any(
            t in gap_type_names and TYPE_KEYWORDS.get(t, re.compile(r"(?!x)x")).search(v["title"])
            for t in TYPE_KEYWORDS
        )
        if matched and len(targeted) < cap:
            targeted.append(v)
        else:
            remainder.append(v)

    return targeted, remainder
```

### Step 4 — Modify pipeline in `jobs.py`

Replace the current linear `scan → classify_all → generate` with:

```python
async def _run_full_pipeline(user_id, db):
    # Stage 1: Scan
    update_status(user_id, stage="scanning")
    await scan_all_channels(user_id, db)

    # Stage 2: Rule-classify (free, instant — part of classifier.py already)
    # Rule-based hits are saved to Classification immediately during _fetch_unclassified_for_user

    # Stage 3: Check if plan can be filled
    if can_fill_plan(user_id, db):
        # Fast path — skip Anthropic entirely for now
        update_status(user_id, stage="generating")
        await generate_plan(user_id, db)
        update_status(user_id, stage="done")
        # Background: classify remaining videos (non-blocking)
        background_tasks.add_task(_background_classify, user_id)
        return

    # Slow path — targeted mini-batch for gap slots
    gap_types = get_gap_types(user_id, db)
    targeted, remainder = build_targeted_batch(user_id, gap_types, db)

    update_status(user_id, stage="classifying")
    await classify_videos(user_id, targeted, db, progress_callback=...)

    # Generate plan with what we have
    update_status(user_id, stage="generating")
    await generate_plan(user_id, db)
    update_status(user_id, stage="done")

    # Background: classify the rest
    background_tasks.add_task(_background_classify_videos, user_id, remainder)
```

### Step 5 — `_background_classify` task

A lightweight background task that calls the existing `classify_for_user()` with the remainder list. Runs after the user already sees their plan. No status update — the user is already on the dashboard.

---

## Frontend UX Changes

### Progress bar during onboarding (step 7)

Today the "classifying" stage shows `done / total` and can sit at a large number for minutes. With this change:

- **Fast path:** "classifying" stage may not appear at all (skipped). Progress goes scan → generating → done in seconds.
- **Slow path (targeted batch):** "classifying" appears briefly with a small total (5–15 videos).

No frontend code changes needed for the happy path — the existing stage polling already handles `"generating"` and `"done"`. But consider:

- **Library page:** Add a subtle banner `"Your library is still building — more videos are being classified in the background."` while background classification is running. This requires a new field in `GET /jobs/status`: `background_classifying: bool`.

### New field in `/jobs/status` response

```json
{
  "stage": "done",
  "background_classifying": true,
  "total": 60,
  "done": 12
}
```

`background_classifying: true` means classification is still running but the plan is ready. The library page can show a non-blocking notice. The dashboard ignores it.

---

## Files to Change

| File | Change |
|---|---|
| `api/services/planner.py` | Add `can_fill_plan()`, `get_gap_types()` |
| `api/services/classifier.py` | Add `build_targeted_batch()`, `_background_classify_videos()` |
| `api/routers/jobs.py` | Modify `_run_full_pipeline()` to use fast/slow path; add `background_classifying` to status |
| `api/scheduler.py` | Apply same `can_fill_plan` check in weekly cron before calling classifier |
| `frontend/src/app/library/page.tsx` | Optional: show "library building" banner if `background_classifying=true` |

No DB migration needed. No schema changes.

---

## Tests Required

### Backend unit tests (`tests/api/`)

- `can_fill_plan()` returns `True` when all slots have ≥ 3 candidates
- `can_fill_plan()` returns `False` when any slot has < 3 candidates
- `can_fill_plan()` returns `True` when user has no non-rest schedule slots (edge case)
- `get_gap_types()` returns only slots below threshold
- `build_targeted_batch()` returns only videos matching gap types, capped correctly
- `build_targeted_batch()` returns remainder correctly (non-matching videos)
- Pipeline: when `can_fill_plan=True` → Anthropic batch is **not** submitted, plan is generated
- Pipeline: when `can_fill_plan=False` → targeted batch is submitted, then plan generated
- `background_classifying` flag is `True` after fast-path plan generation, `False` once background task completes

### Backend integration tests (`tests/integration/`)

- Full pipeline: insert pre-classified videos satisfying schedule → trigger scan → assert plan generated without Anthropic call
- Full pipeline: insert no classified videos → trigger scan → assert targeted mini-batch submitted, plan generated

### Frontend tests

- Library page: shows "library building" banner when `background_classifying=true`
- Library page: hides banner when `background_classifying=false`

---

## Configuration

| Env var | Default | Purpose |
|---|---|---|
| `MIN_PLAN_CANDIDATES` | `3` | Min classified videos per slot to consider plan fillable |
| `TARGETED_BATCH_MULTIPLIER` | `5` | Candidates per gap slot in targeted mini-batch |

---

## Docs to Update After Implementation

- `PROGRESS.md` — add to status + checkpoint entry
- `docs/architecture.md` — update pipeline description, note fast/slow path
- `docs/specs/ai-cost-reduction.md` — add F9 entry referencing this spec
- `CLAUDE.md` — add new env vars, update jobs.py pipeline description
- Memory — update status

---

## Implementation Status

| Step | Status |
|---|---|
| `can_fill_plan()` | ✅ Done (2026-03-15) |
| `get_gap_types()` | ✅ Done (2026-03-15) |
| `rule_classify_for_user()` | ✅ Done (2026-03-15) |
| `build_targeted_batch()` | ✅ Done (2026-03-15) |
| Modified pipeline in `jobs.py` | ✅ Done (2026-03-15) |
| `background_classifying` status field | ✅ Done (2026-03-15) |
| Scheduler integration | ✅ Done (2026-03-15) |
| Library "building" banner (optional) | ⏳ Deferred |
