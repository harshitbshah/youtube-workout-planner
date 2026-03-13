# Spec: AI Profile Enrichment (Phase O1)

**Created:** 2026-03-11
**Status:** Ready for implementation
**Depends on:** Current 8-step onboarding wizard (Phase B + O1 step insertion)
**Migration:** 009 (shared with Phase O3 — see [migrations-roadmap.md](migrations-roadmap.md))

**Related specs:**
- [ai-coach-chat.md](ai-coach-chat.md) — Phase O2: coach chat (builds on enrichment data)
- [ai-weekly-review.md](ai-weekly-review.md) — Phase O3: weekly review card
- [channel-recommendations.md](channel-recommendations.md) — Phase R1 curated channels uses `preferred_types` from enrichment

---

## App design — how users actually interact

The web app is the primary interface. Users log in, view their auto-generated plan,
optionally swap videos, and click "Publish to YouTube" — all within the app. The
YouTube playlist is a **convenience output only** — it lets users play their week's
videos directly from the YouTube app without signing in to the web app each time.

No feedback flows back from YouTube. All meaningful user-intent signals are captured
in the web app: plan views, video swaps, schedule changes, and the Publish click itself.

**Activity tracking:** Any authenticated request updates `user.last_active_at`. The
Sunday cron only runs for users active within the last 14 days — users who haven't
opened the app (including clicking Publish) are skipped.

**Implicit feedback from the Publish button:**
The plan auto-generates every Sunday. The user's only required action is the Publish
click (if they want the YouTube playlist updated). The gap between the AI-generated
video and the final published video is the feedback signal — if a user swapped Thursday's
video before publishing, the original AI pick was rejected. No manual "mark as done"
checkboxes are needed.

This requires two small additions to `ProgramHistory`:
- `original_video_id` — written at generation time, never overwritten. Lets us detect
  swaps: `original_video_id != video_id` at publish time = rejection signal.
- `published_at` — written when `POST /plan/publish` is called. Records engagement.

These are added in migration 009 alongside the O1 profile fields.

---

## The core insight

The onboarding wizard's strength is scaffolding — it tells users exactly what decisions to
make. Its weakness is rigidity — it can't capture nuance: bad knees, a recent pregnancy,
"I love dancing but hate running", travelling two weeks a month. These are the details that
would make a real trainer say "oh, that changes everything."

A blank "tell me about yourself" chat box would be worse, not better — users don't know
what's relevant to type. The right answer is: keep the wizard as the structural backbone
and add one targeted freeform field where nuance matters most. Then let an LLM extract
structured data from it silently.

The coach chat lives elsewhere entirely — not in onboarding, but on the dashboard, where
users already have context (a plan in front of them, a specific day, a specific constraint)
and know exactly what they want to change.

---

## What changes in the wizard

A new **step 6** is inserted between the schedule confirmation (current step 5) and the
channels step (current step 6). Steps 6 and 7 become 7 and 8.

**New total: 8 steps.**

This placement is intentional: the enrichment is processed before the channels step, so the
curated channel recommendations in step 7 can be personalized using the enrichment output
(e.g. surface postpartum channels, dance channels, bodyweight-only channels).

### The new step — "Anything else?"

```
┌──────────────────────────────────────────────────────────────────┐
│  Step 6 of 8                                                     │
│                                                                  │
│  Anything we should know?              (optional)                │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │                                                            │  │
│  │  e.g. bad knees, just had a baby, love dancing,           │  │
│  │  only have dumbbells at home, travel a lot...             │  │
│  │                                                            │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                  │
│  The more you tell us, the better we'll filter your workouts.   │
│                                                                  │
│   [← Back]                          [Skip]   [Continue →]       │
└──────────────────────────────────────────────────────────────────┘
```

Design notes:
- Textarea, 3 rows, auto-grows up to 6
- Placeholder text carries the full cognitive load — users don't need to think about format
- "Skip" is prominent (same visual weight as "Continue") — this step must never feel mandatory
- "Continue →" is disabled while the enrichment API call is in-flight; shows spinner
- If the user clicks Skip: advance to step 7 immediately, no API call
- On "Continue →": POST to `/auth/me/enrich`, await response, advance to step 7
- If the API call fails: log the error silently, advance to step 7 anyway — enrichment
  failure must never block onboarding

---

## What the LLM extracts

The backend sends the freeform text to **Claude Haiku** (fast, cheap, perfect for extraction)
with a structured extraction prompt. The result is stored as JSON on the user record.

**Enrichment schema:**

```json
{
  "constraints": ["knee_injury", "postpartum"],
  "avoid_types": ["high_impact", "jumping", "heavy_lifting"],
  "preferred_types": ["dance", "yoga"],
  "equipment": ["dumbbells", "resistance_bands"],
  "time_constraints": ["morning_only", "20_mins_max"],
  "lifestyle_notes": "new parent, travels frequently for work",
  "raw_input": "bad knees, just had a baby, love dancing, only have dumbbells"
}
```

**Constraint vocabulary (used by the LLM, then used for filtering):**

| Constraint | Signals to filter |
|---|---|
| `knee_injury` | avoid jumping, deep squats, high-impact |
| `postpartum` | avoid core compression, heavy lifting, high-impact; surface pelvic floor / postnatal content |
| `back_pain` | avoid heavy deadlifts, avoid high-impact |
| `shoulder_injury` | avoid overhead pressing, push-ups with full extension |
| `diastasis_recti` | avoid traditional crunches, heavy core compression |
| `pregnancy` | surface prenatal content, avoid lying on back after first trimester |
| `chronic_fatigue` | prefer shorter, gentler sessions |

**Preferred type vocabulary:**

`dance`, `yoga`, `boxing`, `barre`, `walking`, `pilates`, `strength`, `hiit`, `outdoor`,
`breathwork`, `stretching`

**Extraction system prompt:**

```
You are extracting structured fitness profile data from a user's freeform description.
The user is setting up a fitness app that plans YouTube workouts for them.

Extract the following and return as valid JSON only (no markdown, no explanation):

{
  "constraints": [],        // physical limitations/injuries
  "avoid_types": [],        // workout types/movements to avoid
  "preferred_types": [],    // workout styles the user enjoys
  "equipment": [],          // equipment available at home
  "time_constraints": [],   // time-related preferences
  "lifestyle_notes": "",    // freeform: life situation context
  "raw_input": ""           // copy the original input unchanged
}

Use the exact vocabulary provided. If the input is empty or irrelevant to fitness,
return all empty arrays and empty strings. Never invent constraints not mentioned.
Return only valid JSON.
```

Model: `claude-haiku-4-5-20251001` — this is a simple extraction task, latency matters
(user is waiting), Haiku is ideal.

---

## DB changes — migration 009

Add four columns to the `users` table, plus two `program_history` columns:

```python
# In api/models.py — User class
life_stage          = Column(String, nullable=True)    # "beginner"|"adult"|"senior"|"athlete"
goal                = Column(String, nullable=True)    # e.g. "Build muscle"
profile_notes       = Column(Text, nullable=True)      # raw freeform text from step 6
profile_enrichment  = Column(Text, nullable=True)      # JSON string — parsed extraction

# Also in migration 009 — ProgramHistory:
original_video_id   = Column(String, ForeignKey("videos.id"), nullable=True)
published_at        = Column(DateTime(timezone=True), nullable=True)
```

`life_stage` and `goal` are stored here so the recommendations engine (Phase R3) can find
similar users, and so the coach chat system prompt has them without a separate API call.

Migration file: `alembic/versions/009_add_user_profile_fields.py`

> Note: migration 009 also includes `weekly_review_cache` and `weekly_review_generated_at`
> for Phase O3. Bundle them in one migration to avoid multiple consecutive user-table alterations.

---

## New endpoint: `POST /auth/me/enrich`

```
POST /auth/me/enrich
Authorization: Bearer <token>
Content-Type: application/json

{ "notes": "bad knees, just had a baby, love dancing" }
```

**Response 200:**
```json
{
  "enrichment": {
    "constraints": ["knee_injury", "postpartum"],
    "avoid_types": ["high_impact", "jumping"],
    "preferred_types": ["dance"],
    "equipment": [],
    "time_constraints": [],
    "lifestyle_notes": "just had a baby"
  }
}
```

**Errors:**
- `401` — not authenticated
- `503` — Anthropic API unavailable (frontend handles gracefully: skip ahead)
- `400` — notes field too long (cap at 500 chars, validate on both frontend and backend)

**Backend location:** `api/routers/auth.py` (add to existing file)

**Service function:** `api/services/enrichment.py` (new file)

```python
# api/services/enrichment.py

import json
import os
import anthropic

ENRICHMENT_SYSTEM_PROMPT = "..."  # as above

def enrich_profile(notes: str) -> dict:
    """
    Call Claude Haiku to extract structured profile data from freeform text.
    Returns a dict matching the enrichment schema.
    Raises anthropic.APIError on failure (caller handles gracefully).
    """
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    msg = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=512,
        system=ENRICHMENT_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": notes or "(no input provided)"}],
    )
    return json.loads(msg.content[0].text)
```

---

## `PATCH /auth/me` extension

Extend the existing endpoint to also accept `life_stage` and `goal`:

```python
class PatchMeRequest(BaseModel):
    display_name: str | None = None   # make optional
    life_stage:   str | None = None
    goal:         str | None = None
```

Called from onboarding after schedule save (step 5) to persist the profile selections.
No separate API call needed — piggybacks on the existing flow.

---

## Frontend changes

**`app/onboarding/page.tsx`:**

1. Add `profileNotes` state: `const [profileNotes, setProfileNotes] = useState("")`
2. Add `enriching` loading state for the step 6 API call
3. Insert step 6 JSX block between steps 5 and 6 (renumber 6→7, 7→8)
4. New `handleEnrich()` async function:
   ```typescript
   async function handleEnrich() {
     if (!profileNotes.trim()) { setStep(7); return; }
     setEnriching(true);
     try {
       await enrichProfile(profileNotes);  // POST /auth/me/enrich
     } catch {
       // silent fail — never block onboarding
     } finally {
       setEnriching(false);
       setStep(7);
     }
   }
   ```
5. In step 5 `handleScheduleConfirm`: also call `patchMe({ life_stage: profile, goal })`.
6. Update `StepIndicator` to reflect 8 steps.

**`lib/api.ts`:** Add:
```typescript
export interface ProfileEnrichment {
  constraints: string[];
  avoid_types: string[];
  preferred_types: string[];
  equipment: string[];
  time_constraints: string[];
  lifestyle_notes: string;
}

export async function enrichProfile(notes: string): Promise<ProfileEnrichment>
```

**Settings page — "About you" section:**

Add a new section to `app/settings/page.tsx` after the profile name field:

```
About you (optional)
────────────────────
┌──────────────────────────────────────────────────┐
│  bad knees, love dancing, just had a baby...     │
└──────────────────────────────────────────────────┘
  [Save]  — re-runs the enrichment on save
```

Allows users to update their constraints/preferences post-onboarding. Calls the same
`POST /auth/me/enrich` endpoint. Shows the current `profile_notes` value on load.

---

## How enrichment flows downstream

Once stored, `profile_enrichment` is read by:

1. **Channel recommendations** (`GET /channels/curated`): `preferred_types` surfaces
   dance/yoga/boxing channels; `constraints` boosts bodyweight/low-impact channels
2. **Plan generation** (`POST /plan/generate`): `avoid_types` filters out video types
   to skip (e.g. knee_injury → no jumping/plyometric videos). See planner changes below.
3. **Coach chat** (Phase O2): included in the system prompt as user context
4. **Weekly review** (Phase O3): referenced when generating advice

**Planner integration — `api/services/planner.py`:**

`pick_video_for_slot_for_user()` currently filters by workout_type + body_focus + difficulty.
Add an `avoid_workout_types` parameter derived from `user.profile_enrichment`:

```python
enrichment = json.loads(user.profile_enrichment or "{}")
avoid_types = enrichment.get("avoid_types", [])
# Map constraint vocabulary → workout type exclusions
if "high_impact" in avoid_types:
    avoid_workout_types.append("HIIT")
if "heavy_lifting" in avoid_types:
    avoid_workout_types.append("Strength")
```

This is the highest-value downstream use of enrichment — the plan immediately respects
the user's physical constraints without any manual intervention.

---

## Files to create

| File | Purpose |
|---|---|
| `api/services/enrichment.py` | `enrich_profile()` — calls Claude Haiku for extraction |
| `alembic/versions/009_add_user_profile_fields.py` | Migration 009: profile columns on `users` + O3 review cache + `program_history` additions |
| `tests/api/test_enrichment.py` | Unit tests for extraction + endpoint |

## Files to modify

| File | Change |
|---|---|
| `api/models.py` | Add 6 new columns to `User`; 2 new columns to `ProgramHistory` |
| `api/routers/auth.py` | Add `POST /auth/me/enrich`; extend `PatchMeRequest` with `life_stage` + `goal` |
| `api/schemas.py` | Add `EnrichRequest`, `EnrichResponse`; extend `PatchMeRequest` |
| `api/services/planner.py` | Read `profile_enrichment` to populate `avoid_workout_types` filter |
| `api/services/publisher.py` | Write `published_at = now()` on `ProgramHistory` rows on publish |
| `frontend/src/app/onboarding/page.tsx` | Insert step 6; update step numbering; add `enrichProfile` call; add `patchMe` after schedule save |
| `frontend/src/app/settings/page.tsx` | Add "About you" section with `profile_notes` textarea |
| `frontend/src/lib/api.ts` | Add `enrichProfile()`, `ProfileEnrichment` type |
| `CLAUDE.md` | Add new route to API routes table |
| `docs/architecture.md` | Update schema + routes sections |

---

## Tests

### Unit tests — `tests/api/test_enrichment.py`

1. `test_enrich_profile_extracts_constraint` — "bad knees" → `constraints: ["knee_injury"]`
2. `test_enrich_profile_extracts_preference` — "love dancing" → `preferred_types: ["dance"]`
3. `test_enrich_profile_empty_input` — empty string → all empty arrays, no crash
4. `test_enrich_profile_irrelevant_input` — "I like pizza" → all empty arrays
5. `test_enrich_endpoint_saves_to_db` — POST → `profile_notes` + `profile_enrichment` written
6. `test_enrich_endpoint_unauthenticated` → 401
7. `test_enrich_endpoint_too_long` — 501-char input → 400
8. `test_enrich_endpoint_anthropic_failure` — mock Anthropic error → 503

### Unit tests — planner integration

9.  `test_planner_respects_avoid_types` — user with `avoid_types: ["high_impact"]` → no HIIT in generated plan
10. `test_planner_no_enrichment` — user with null `profile_enrichment` → plan generates normally

### Integration tests — `tests/integration/test_enrichment_integration.py`

11. `test_full_enrich_and_plan_flow` — POST enrich → plan generated → no avoided types present

---

## Implementation order

1. Migration 009 (all profile fields + O3 review cache fields + ProgramHistory additions)
2. `api/services/enrichment.py` + `POST /auth/me/enrich` endpoint
3. Extend `PATCH /auth/me` to accept `life_stage` + `goal`
4. Unit tests 1–8 — all passing
5. Planner: read `profile_enrichment` for `avoid_workout_types`
6. Unit tests 9–10 — all passing
7. Frontend: onboarding step 6; settings "About you" section
8. Ship O1

---

## Key decisions and rationale

| Decision | Rationale |
|---|---|
| Step 6 inserted before channels (not after) | Enrichment output (`preferred_types`) feeds curated channel recommendations in step 7 |
| Skip is prominent, failure is silent | Enrichment must never block onboarding — it's additive, not required |
| Haiku for enrichment | Simple extraction task; latency matters (user is waiting) |
| `avoid_workout_types` in planner | The most immediate user value from enrichment — plan immediately respects physical constraints |
| `life_stage` + `goal` persisted to DB | Required by Phase R3 for collaborative filtering; used in coach system prompt |
| O1 + O3 user fields in one migration | Both add columns to `users`; bundling avoids two consecutive user-table alterations |
