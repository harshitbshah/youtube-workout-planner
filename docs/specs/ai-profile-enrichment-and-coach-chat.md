# Spec: AI Profile Enrichment + Coach Chat

**Created:** 2026-03-11
**Status:** Ready for implementation
**Depends on:** Current 7-step onboarding wizard (already shipped)

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

## Phase O1 — Freeform profile enrichment

### What changes in the wizard

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

### What the LLM extracts

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

### DB changes — migration 009

Add four columns to the `users` table:

```python
# In api/models.py — User class
life_stage          = Column(String, nullable=True)    # "beginner"|"adult"|"senior"|"athlete"
goal                = Column(String, nullable=True)    # e.g. "Build muscle"
profile_notes       = Column(Text, nullable=True)      # raw freeform text from step 6
profile_enrichment  = Column(Text, nullable=True)      # JSON string — parsed extraction
```

`life_stage` and `goal` are stored here so the recommendations engine (Phase R3) can find
similar users, and so the coach chat system prompt has them without a separate API call.

Migration file: `alembic/versions/009_add_user_profile_fields.py`

### New endpoint: `POST /auth/me/enrich`

```
POST /auth/me/enrich
Authorization: session cookie
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

### `PATCH /auth/me` extension

Extend the existing endpoint to also accept `life_stage` and `goal`:

```python
class PatchMeRequest(BaseModel):
    display_name: str | None = None   # make optional
    life_stage:   str | None = None
    goal:         str | None = None
```

Called from onboarding after schedule save (step 5) to persist the profile selections.
No separate API call needed — piggybacks on the existing flow.

### Frontend changes

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

### How enrichment flows downstream

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

## Phase O2 — AI Coach Chat

### Where it lives

The coach chat is a **floating panel on the dashboard** — not a new page, not inline.

- A "Coach" button in the dashboard header (between "Library" and "Settings" in the nav)
- Clicking opens a slide-over panel from the right (400px wide on desktop, full-screen on mobile)
- The weekly plan is still visible behind the panel on desktop
- The panel persists within the session; closing it preserves conversation history
- First-time open: shows a brief welcome message with 3 example prompts as tappable chips

### The interface

```
┌──────────────────────────────────────┐
│  Your Coach                      ✕  │
├──────────────────────────────────────┤
│                                      │
│  ┌────────────────────────────────┐  │
│  │ 👋 I'm your fitness coach.    │  │
│  │ Tell me what you need today.  │  │
│  │                               │  │
│  │ Try:                          │  │
│  │  "Give me something quick"    │  │
│  │  "My shoulder is sore today"  │  │
│  │  "I'm travelling this week"   │  │
│  └────────────────────────────────┘  │
│                                      │
│  [User bubble]                       │
│                     [Coach bubble]   │
│                                      │
│    ┌── Video card ───────────────┐   │
│    │ thumbnail | title | 28 min  │   │
│    │ HIIT · Beginner  [Add →]    │   │
│    └────────────────────────────┘   │
│                                      │
├──────────────────────────────────────┤
│  ┌──────────────────────────┐ [→]  │
│  │ Give me 15 mins today... │      │
│  └──────────────────────────┘      │
│  Powered by Claude                  │
└──────────────────────────────────────┘
```

Design notes:
- Message bubbles: user messages right-aligned (white bg), coach left-aligned (zinc-800)
- Typing indicator (three animated dots) while waiting for response
- Video cards appear inline in the coach's reply — same `VideoCard` component from dashboard,
  but compact (horizontal layout: thumbnail left, info right, "Add to [day]" button)
- "Plan updated ✓" confirmation chip appears after a successful plan update
- When plan is updated, dashboard plan grid refreshes automatically via `onPlanChanged` prop

### Conversation state

For v1: conversation history is **React state only** — an array of `Message` objects stored
in the `CoachPanel` component. No DB persistence. History is lost on page refresh.

The full message history is sent to the backend on every turn (same as the Anthropic API
messages array). This is stateless on the backend — no session management needed.

Why no DB persistence for v1:
- Conversation history per user adds DB complexity and storage cost
- Users don't expect chat history to persist after a page refresh in v1
- Can be added in a future phase when the pattern is validated

```typescript
interface Message {
  role: "user" | "assistant";
  content: string;
  videos?: VideoSummary[];      // video cards to display below the message
  plan_updated?: boolean;       // show "Plan updated ✓" chip
  updated_day?: string;         // e.g. "thursday"
}
```

### New endpoint: `POST /coach/chat`

```
POST /coach/chat
Authorization: session cookie
Content-Type: application/json

{
  "message": "give me something shorter, only 15 mins",
  "history": [
    { "role": "user",      "content": "..." },
    { "role": "assistant", "content": "..." }
  ]
}
```

**Response 200:**
```json
{
  "reply": "Sure — here's a quick 15-min cardio from your library that fits well after yesterday's leg session.",
  "videos": [
    {
      "id": "abc123",
      "title": "15 Min Full Body Cardio — No Equipment",
      "url": "https://youtube.com/watch?v=abc123",
      "channel_name": "Heather Robertson",
      "duration_sec": 900,
      "workout_type": "Cardio",
      "body_focus": "full",
      "difficulty": "beginner"
    }
  ],
  "plan_updated": false,
  "updated_day": null
}
```

**Errors:**
- `401` — not authenticated
- `503` — Anthropic API unavailable
- `400` — message too long (cap 1000 chars)
- `429` — rate limit (max 20 coach messages per user per hour; enforced in-memory with a
  per-user counter reset at the top of each hour)

**Router file:** `api/routers/coach.py` (new file)
**Registered in:** `api/main.py` as `/coach`

### System prompt construction

Built dynamically at request time from the user's DB record + current plan. Never cached —
always reflects current state.

```python
def build_coach_system_prompt(user: User, plan: PlanResponse, library_summary: dict) -> str:
    enrichment = json.loads(user.profile_enrichment or "{}")
    constraints = ", ".join(enrichment.get("constraints", [])) or "none mentioned"
    preferences = ", ".join(enrichment.get("preferred_types", [])) or "not specified"
    equipment   = ", ".join(enrichment.get("equipment", [])) or "not specified"
    lifestyle   = enrichment.get("lifestyle_notes", "") or "not mentioned"

    plan_lines = []
    for day in plan.days:
        if day.video:
            plan_lines.append(f"  {day.day.capitalize()}: {day.video.title} ({day.video.workout_type}, {day.video.duration_sec // 60} min)")
        else:
            plan_lines.append(f"  {day.day.capitalize()}: Rest")
    plan_text = "\n".join(plan_lines)

    lib = library_summary
    type_counts = ", ".join(f"{t}: {n}" for t, n in lib["by_type"].items())

    return f"""You are {user.display_name or "the user"}'s personal fitness coach.
You help them get the most from their YouTube workout library.

About them:
- Profile: {user.life_stage or "not set"} — Goal: {user.goal or "not set"}
- Training: {lib["schedule_days"]} days/week
- Physical constraints: {constraints}
- Workout preferences: {preferences}
- Equipment at home: {equipment}
- Lifestyle context: {lifestyle}

This week's plan (week of {plan.week_start}):
{plan_text}

Their library:
- Total videos: {lib["total_videos"]}
- By type: {type_counts}
- Channels: {", ".join(lib["channels"])}

Today is {datetime.now().strftime("%A, %B %-d")}.

Your role:
- Help them adjust today's or this week's workouts
- Recommend specific videos from their library using the search_library tool
- Update their plan directly using update_plan_day when asked
- Give brief, practical coaching advice
- If a constraint matters (e.g. knee injury mentioned), never suggest workouts that
  would aggravate it — this is important

Rules:
- Always use search_library before recommending a specific video — never invent titles
- Be conversational but brief — lead with the recommendation, not the explanation
- If their library doesn't have what they need, say so honestly and suggest what kind of
  channel would fill the gap
- Never make up video URLs or titles
"""
```

### Tool definitions

The backend exposes two tools to Claude:

**Tool 1: `search_library`**
```python
{
    "name": "search_library",
    "description": "Search the user's video library for videos matching given criteria. Always call this before recommending a specific video.",
    "input_schema": {
        "type": "object",
        "properties": {
            "workout_type": {
                "type": "string",
                "enum": ["HIIT", "Strength", "Mobility", "Cardio", "Dance", "Boxing",
                         "Walking", "Barre", "Functional", "Breathwork", "Other"],
                "description": "The workout type to filter by. Omit to search all types."
            },
            "max_duration_min": {
                "type": "integer",
                "description": "Maximum video duration in minutes."
            },
            "min_duration_min": {
                "type": "integer",
                "description": "Minimum video duration in minutes."
            },
            "difficulty": {
                "type": "string",
                "enum": ["beginner", "intermediate", "advanced"],
                "description": "Difficulty level filter. Omit to include all."
            },
            "body_focus": {
                "type": "string",
                "enum": ["full", "upper", "lower", "core"],
                "description": "Body focus filter. Omit to include all."
            },
            "exclude_this_week": {
                "type": "boolean",
                "description": "If true, exclude videos already in this week's plan.",
                "default": True
            },
            "limit": {
                "type": "integer",
                "description": "Max number of results to return.",
                "default": 3
            }
        },
        "required": []
    }
}
```

**Tool 2: `update_plan_day`**
```python
{
    "name": "update_plan_day",
    "description": "Replace the video assigned to a specific day in the user's current week plan. Only call this when the user has explicitly asked to update their plan.",
    "input_schema": {
        "type": "object",
        "properties": {
            "day": {
                "type": "string",
                "enum": ["monday", "tuesday", "wednesday", "thursday",
                         "friday", "saturday", "sunday"],
                "description": "The day to update."
            },
            "video_id": {
                "type": "string",
                "description": "The YouTube video ID to assign to this day (from search_library results)."
            }
        },
        "required": ["day", "video_id"]
    }
}
```

### Tool execution loop

```python
async def run_coach_turn(
    user: User,
    message: str,
    history: list[dict],
    plan: PlanResponse,
    db: Session,
) -> CoachResponse:

    system_prompt = build_coach_system_prompt(user, plan, build_library_summary(user, db))
    messages = history + [{"role": "user", "content": message}]

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    surfaced_videos = []
    plan_updated = False
    updated_day = None

    # Agentic loop — handles multi-step tool use
    while True:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=system_prompt,
            tools=[SEARCH_LIBRARY_TOOL, UPDATE_PLAN_DAY_TOOL],
            messages=messages,
        )

        if response.stop_reason == "end_turn":
            # Extract final text reply
            reply = next(b.text for b in response.content if b.type == "text")
            return CoachResponse(
                reply=reply,
                videos=surfaced_videos,
                plan_updated=plan_updated,
                updated_day=updated_day,
            )

        if response.stop_reason == "tool_use":
            # Execute all tool calls in this response
            tool_results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue

                if block.name == "search_library":
                    videos = _execute_search_library(user.id, block.input, plan, db)
                    surfaced_videos.extend(videos)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps([_video_to_dict(v) for v in videos]),
                    })

                elif block.name == "update_plan_day":
                    success = _execute_update_plan_day(
                        user.id, block.input["day"], block.input["video_id"], db
                    )
                    plan_updated = success
                    updated_day = block.input["day"] if success else None
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": "Plan updated successfully." if success else "Failed to update plan.",
                    })

            # Append assistant turn + tool results, continue loop
            messages = messages + [
                {"role": "assistant", "content": response.content},
                {"role": "user",      "content": tool_results},
            ]
```

Model: `claude-sonnet-4-6` — this is the core user-facing AI experience; quality matters.

### Library summary helper

Called once per chat turn to build the system prompt context:

```python
def build_library_summary(user: User, db: Session) -> dict:
    """Build a compact summary of the user's library for the system prompt."""
    # Total video count, breakdown by type, channel names, schedule days
    # Queries: classifications GROUP BY workout_type, channels, schedules
    # Returns dict — not a DB model, just plain data for the prompt
```

### Frontend components

**`components/CoachPanel.tsx`** (new component):

```typescript
interface CoachPanelProps {
  isOpen: boolean;
  onClose: () => void;
  onPlanChanged: () => void;   // triggers dashboard plan re-fetch
}
```

Internal state:
```typescript
const [messages, setMessages] = useState<Message[]>([WELCOME_MESSAGE]);
const [input, setInput] = useState("");
const [loading, setLoading] = useState(false);
```

Renders:
- Slide-over panel (fixed right-0, z-50, w-96 desktop / w-full mobile)
- Backdrop overlay on mobile
- Message list with auto-scroll to bottom
- Inline `VideoRecommendationCard` components within assistant messages
- "Plan updated ✓ Thursday" confirmation chip when `plan_updated: true`
- Textarea input + send button (Enter to send, Shift+Enter for newline)
- "Powered by Claude" footer (AI disclosure)

**`components/VideoRecommendationCard.tsx`** (new component):

Compact horizontal card for use inside chat bubbles:
- 64×48px thumbnail (left)
- Title (1 line, truncated), channel name, duration
- Workout type + difficulty badges
- "Add to plan" button → opens a day-picker dropdown (Mon–Sun), calls
  `update_plan_day` directly from frontend via `POST /plan/{day}`, triggers `onPlanChanged`

**`app/dashboard/page.tsx`** changes:
- Import `CoachPanel`
- Add `coachOpen` state
- Add "Coach" button to header nav
- Render `<CoachPanel isOpen={coachOpen} onClose={() => setCoachOpen(false)} onPlanChanged={refetchPlan} />`
- Implement `refetchPlan()` that re-calls `getUpcomingPlan()` and updates plan state

### New TypeScript types in `lib/api.ts`

```typescript
export interface CoachMessage {
  role: "user" | "assistant";
  content: string;
}

export interface CoachResponse {
  reply: string;
  videos: VideoSummary[];
  plan_updated: boolean;
  updated_day: string | null;
}

export async function sendCoachMessage(
  message: string,
  history: CoachMessage[]
): Promise<CoachResponse>
```

---

## Phase O3 — Weekly AI review card

A lightweight extension of the same infrastructure — one read-only Claude call that
generates a brief weekly summary shown on the dashboard on Monday mornings.

### What it shows

```
┌──────────────────────────────────────────────────────────┐
│  Last week — quick take                                   │
│                                                           │
│  You completed 3 of 4 sessions. Strength was your        │
│  strongest category — you've done it consistently for    │
│  3 weeks. You skipped both cardio sessions this month.   │
│  This week I've swapped Friday's HIIT for a dance        │
│  session — might be easier to stick to.                  │
│                                                           │
│  [Open Coach →]                                          │
└──────────────────────────────────────────────────────────┘
```

Shown as a dismissible card at the top of the dashboard, Monday only (or until dismissed).
Clicking "Open Coach →" opens the coach panel.

### New endpoint: `GET /coach/weekly-review`

```
GET /coach/weekly-review
Authorization: session cookie
```

Returns: `{ "review": "string" }` or `{ "review": null }` if not enough history (< 2 weeks).

Backend logic:
1. Load last 2 weeks of `program_history` for the user
2. Load `video_feedback` rows (completion signals) for those weeks (from Phase R3)
3. Build a compact prompt: what was planned, what was completed, what was swapped
4. Single Claude Haiku call (no tools needed — read-only, text generation only)
5. Cache result in `users.weekly_review_cache` (text, nullable) + `weekly_review_generated_at`
   (DateTime) — regenerate once per week (on Monday), return cached otherwise

**Migration:** add `weekly_review_cache` + `weekly_review_generated_at` to `users` table.

---

## Files to create

| File | Purpose |
|---|---|
| `api/routers/coach.py` | `POST /coach/chat`, `GET /coach/weekly-review` |
| `api/services/enrichment.py` | `enrich_profile()` — calls Claude Haiku for extraction |
| `api/services/coach.py` | `run_coach_turn()`, `build_coach_system_prompt()`, `build_library_summary()`, tool executors |
| `alembic/versions/009_add_user_profile_fields.py` | `life_stage`, `goal`, `profile_notes`, `profile_enrichment`, `weekly_review_cache`, `weekly_review_generated_at` on `users` |
| `frontend/src/components/CoachPanel.tsx` | Slide-over chat panel |
| `frontend/src/components/VideoRecommendationCard.tsx` | Compact video card for use in chat |
| `tests/api/test_enrichment.py` | Unit tests for extraction + endpoint |
| `tests/api/test_coach.py` | Unit tests for coach chat endpoint + tool execution |
| `tests/integration/test_coach_integration.py` | Integration tests |

## Files to modify

| File | Change |
|---|---|
| `api/models.py` | Add 6 new columns to `User` |
| `api/routers/auth.py` | Add `POST /auth/me/enrich`; extend `PatchMeRequest` |
| `api/schemas.py` | Add `EnrichRequest`, `EnrichResponse`, `CoachChatRequest`, `CoachChatResponse`, `WeeklyReviewResponse`; extend `PatchMeRequest` |
| `api/main.py` | Register `coach` router |
| `api/services/planner.py` | Read `profile_enrichment` to populate `avoid_workout_types` filter |
| `frontend/src/app/onboarding/page.tsx` | Insert step 6; update step numbering; add `enrichProfile` call; add `patchMe` call after schedule save |
| `frontend/src/app/settings/page.tsx` | Add "About you" section with `profile_notes` textarea |
| `frontend/src/app/dashboard/page.tsx` | Add CoachPanel, Coach nav button, `refetchPlan` |
| `frontend/src/lib/api.ts` | Add `enrichProfile()`, `sendCoachMessage()`, `getWeeklyReview()`, new types |
| `CLAUDE.md` | Add new routes to API routes table |
| `docs/architecture.md` | Update schema + routes sections |

---

## Tests

### Unit tests — `tests/api/test_enrichment.py`

1. `test_enrich_profile_extracts_constraint` — "bad knees" → `constraints: ["knee_injury"]`
2. `test_enrich_profile_extracts_preference` — "love dancing" → `preferred_types: ["dance"]`
3. `test_enrich_profile_empty_input` — empty string → all empty arrays, no crash
4. `test_enrich_profile_irrelevant_input` — "I like pizza" → all empty arrays
5. `test_enrich_endpoint_saves_to_db` — POST → user.profile_notes + profile_enrichment written
6. `test_enrich_endpoint_unauthenticated` → 401
7. `test_enrich_endpoint_too_long` — 501-char input → 400
8. `test_enrich_endpoint_anthropic_failure` — mock Anthropic error → 503

### Unit tests — `tests/api/test_coach.py`

9.  `test_coach_chat_simple_response` — message with no tool use → text reply returned
10. `test_coach_chat_search_library_called` — "give me 15 mins" → search_library tool executed
11. `test_coach_chat_search_respects_duration` — max_duration_min filter applied in DB query
12. `test_coach_chat_update_plan_day` — "update Thursday" → update_plan_day tool → history row updated
13. `test_coach_chat_update_plan_day_returns_flag` — `plan_updated: true`, `updated_day: "thursday"`
14. `test_coach_chat_excludes_this_week_videos` — search with exclude_this_week=true skips plan videos
15. `test_coach_chat_constraint_in_system_prompt` — enrichment with knee_injury → appears in prompt
16. `test_coach_chat_unauthenticated` → 401
17. `test_coach_chat_rate_limit` — 21 messages in one hour → 429 on 21st
18. `test_coach_chat_empty_library` — user with 0 videos → coach replies gracefully
19. `test_weekly_review_no_history` — fewer than 2 weeks → `review: null`
20. `test_weekly_review_returns_cached` — second call within same week → no new Claude call

### Unit tests — planner integration

21. `test_planner_respects_avoid_types` — user with `avoid_types: ["high_impact"]` →
    no HIIT videos in generated plan
22. `test_planner_no_enrichment` — user with null `profile_enrichment` → plan generates normally

### Integration tests — `tests/integration/test_coach_integration.py`

23. `test_full_enrich_and_plan_flow` — POST enrich → plan generated → no avoided types present
24. `test_coach_update_persists_to_db` — coach updates Thursday → `program_history` row updated

---

## Implementation order

### O1 first (no streaming, no tool loop, pure extraction)

1. Migration 009 (profile fields on users)
2. `api/services/enrichment.py` + `POST /auth/me/enrich` endpoint
3. Extend `PATCH /auth/me` to accept `life_stage` + `goal`
4. Unit tests 1–8 — all passing
5. Planner: read `profile_enrichment` for `avoid_workout_types`
6. Unit tests 21–22 — all passing
7. Frontend: onboarding step 6; settings "About you" section
8. Ship O1

### O2 next (more complex — tool loop, streaming deferred)

9. `api/services/coach.py` — system prompt builder + library summary
10. Tool definitions + `search_library` executor
11. `update_plan_day` executor (reuse planner service layer)
12. `POST /coach/chat` endpoint — agentic tool loop, no streaming
13. Unit tests 9–20 — all passing
14. Integration tests 23–24 — all passing
15. `CoachPanel.tsx` + `VideoRecommendationCard.tsx` frontend components
16. Dashboard integration (Coach nav button, `onPlanChanged` callback)
17. Ship O2

### O3 last (simple, read-only)

18. `GET /coach/weekly-review` endpoint (Claude Haiku, cached)
19. Weekly review card component on dashboard
20. Ship O3

---

## Key decisions and rationale

| Decision | Rationale |
|---|---|
| Step 6 inserted before channels (not after) | Enrichment output (`preferred_types`) feeds curated channel recommendations in step 7 |
| Skip is prominent, failure is silent | Enrichment must never block onboarding — it's additive, not required |
| Haiku for enrichment, Sonnet for coach | Enrichment is a simple extraction task (latency matters); coach chat is the core UX (quality matters) |
| Conversation history in React state (no DB) | Avoids schema complexity for v1; chat history is low-value to persist; re-evaluate after usage data |
| Tool loop not streaming for v1 | Streaming adds frontend complexity; typing indicator is sufficient for v1 |
| Rate limit 20 msgs/hour in-memory | Prevents runaway API spend; simple to implement; revisit when per-user cost tracking exists |
| `avoid_workout_types` in planner | The most immediate user value from enrichment — plan immediately respects physical constraints |
