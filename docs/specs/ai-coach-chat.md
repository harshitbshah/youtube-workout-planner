# Spec: AI Coach Chat

**Created:** 2026-03-11
**Status:** Ready for implementation
**Depends on:** [AI Profile Enrichment](ai-profile-enrichment.md) - profile enrichment data is used in the coach system prompt
**Migration:** None - all schema changes are in migration 009 (see [AI Profile Enrichment](ai-profile-enrichment.md))

**Related specs:**
- [ai-profile-enrichment.md](ai-profile-enrichment.md) - AI Profile Enrichment: data used in system prompt
- [ai-weekly-review.md](ai-weekly-review.md) - Weekly AI Review: uses same coach router

---

## Where it lives

The coach chat is a **floating panel on the dashboard** - not a new page, not inline.

- A "Coach" button in the dashboard header (between "Library" and "Settings" in the nav)
- Clicking opens a slide-over panel from the right (400px wide on desktop, full-screen on mobile)
- The weekly plan is still visible behind the panel on desktop
- The panel persists within the session; closing it preserves conversation history
- First-time open: shows a brief welcome message with 3 example prompts as tappable chips

---

## The interface

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
- Video cards appear inline in the coach's reply - same `VideoCard` component from dashboard,
  but compact (horizontal layout: thumbnail left, info right, "Add to [day]" button)
- "Plan updated ✓" confirmation chip appears after a successful plan update
- When plan is updated, dashboard plan grid refreshes automatically via `onPlanChanged` prop

---

## Conversation state

For v1: conversation history is **React state only** - an array of `Message` objects stored
in the `CoachPanel` component. No DB persistence. History is lost on page refresh.

The full message history is sent to the backend on every turn (same as the Anthropic API
messages array). This is stateless on the backend - no session management needed.

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

---

## New endpoint: `POST /coach/chat`

```
POST /coach/chat
Authorization: Bearer <token>
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
  "reply": "Sure - here's a quick 15-min cardio from your library that fits well after yesterday's leg session.",
  "videos": [
    {
      "id": "abc123",
      "title": "15 Min Full Body Cardio - No Equipment",
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
- `401` - not authenticated
- `503` - Anthropic API unavailable
- `400` - message too long (cap 1000 chars)
- `429` - rate limit (max 20 coach messages per user per hour; enforced in-memory with a
  per-user counter reset at the top of each hour)

**Router file:** `api/routers/coach.py` (new file)
**Registered in:** `api/main.py` as `/coach`

---

## System prompt construction

Built dynamically at request time from the user's DB record + current plan. Never cached -
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
- Profile: {user.life_stage or "not set"} - Goal: {user.goal or "not set"}
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
  would aggravate it - this is important

Rules:
- Always use search_library before recommending a specific video - never invent titles
- Be conversational but brief - lead with the recommendation, not the explanation
- If their library doesn't have what they need, say so honestly and suggest what kind of
  channel would fill the gap
- Never make up video URLs or titles
"""
```

---

## Tool definitions

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

---

## Tool execution loop

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

    # Agentic loop - handles multi-step tool use
    while True:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=system_prompt,
            tools=[SEARCH_LIBRARY_TOOL, UPDATE_PLAN_DAY_TOOL],
            messages=messages,
        )

        if response.stop_reason == "end_turn":
            reply = next(b.text for b in response.content if b.type == "text")
            return CoachResponse(
                reply=reply,
                videos=surfaced_videos,
                plan_updated=plan_updated,
                updated_day=updated_day,
            )

        if response.stop_reason == "tool_use":
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

            messages = messages + [
                {"role": "assistant", "content": response.content},
                {"role": "user",      "content": tool_results},
            ]
```

Model: `claude-sonnet-4-6` - this is the core user-facing AI experience; quality matters.

---

## Library summary helper

Called once per chat turn to build the system prompt context:

```python
def build_library_summary(user: User, db: Session) -> dict:
    """Build a compact summary of the user's library for the system prompt."""
    # Total video count, breakdown by type, channel names, schedule days
    # Queries: classifications GROUP BY workout_type, channels, schedules
    # Returns dict - not a DB model, just plain data for the prompt
```

---

## Frontend components

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

---

## New TypeScript types in `lib/api.ts`

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

## Files to create

| File | Purpose |
|---|---|
| `api/routers/coach.py` | `POST /coach/chat`, `GET /coach/weekly-review` |
| `api/services/coach.py` | `run_coach_turn()`, `build_coach_system_prompt()`, `build_library_summary()`, tool executors |
| `frontend/src/components/CoachPanel.tsx` | Slide-over chat panel |
| `frontend/src/components/VideoRecommendationCard.tsx` | Compact video card for use in chat |
| `tests/api/test_coach.py` | Unit tests for coach chat endpoint + tool execution |
| `tests/integration/test_coach_integration.py` | Integration tests |

## Files to modify

| File | Change |
|---|---|
| `api/schemas.py` | Add `CoachChatRequest`, `CoachChatResponse`, `WeeklyReviewResponse` |
| `api/main.py` | Register `coach` router |
| `frontend/src/app/dashboard/page.tsx` | Add CoachPanel, Coach nav button, `refetchPlan` |
| `frontend/src/lib/api.ts` | Add `sendCoachMessage()`, `getWeeklyReview()`, new types |
| `CLAUDE.md` | Add new routes to API routes table |
| `docs/architecture.md` | Update routes section |

---

## Tests

### Unit tests - `tests/api/test_coach.py`

1.  `test_coach_chat_simple_response` - message with no tool use → text reply returned
2.  `test_coach_chat_search_library_called` - "give me 15 mins" → `search_library` tool executed
3.  `test_coach_chat_search_respects_duration` - `max_duration_min` filter applied in DB query
4.  `test_coach_chat_update_plan_day` - "update Thursday" → `update_plan_day` → history row updated
5.  `test_coach_chat_update_plan_day_returns_flag` - `plan_updated: true`, `updated_day: "thursday"`
6.  `test_coach_chat_excludes_this_week_videos` - search with `exclude_this_week=true` skips plan videos
7.  `test_coach_chat_constraint_in_system_prompt` - enrichment with `knee_injury` → appears in prompt
8.  `test_coach_chat_unauthenticated` → 401
9.  `test_coach_chat_rate_limit` - 21 messages in one hour → 429 on 21st
10. `test_coach_chat_empty_library` - user with 0 videos → coach replies gracefully

### Integration tests - `tests/integration/test_coach_integration.py`

11. `test_coach_update_persists_to_db` - coach updates Thursday → `program_history` row updated

---

## Implementation order

1. `api/services/coach.py` - system prompt builder + library summary
2. Tool definitions + `search_library` executor
3. `update_plan_day` executor (reuse planner service layer)
4. `POST /coach/chat` endpoint - agentic tool loop, no streaming
5. Unit tests 1–10 - all passing
6. Integration test 11 - all passing
7. `CoachPanel.tsx` + `VideoRecommendationCard.tsx` frontend components
8. Dashboard integration (Coach nav button, `onPlanChanged` callback)
9. Ship O2

---

## Key decisions and rationale

| Decision | Rationale |
|---|---|
| Haiku for enrichment, Sonnet for coach | Enrichment is a simple extraction task (latency matters); coach chat is the core UX (quality matters) |
| Conversation history in React state (no DB) | Avoids schema complexity for v1; chat history is low-value to persist; re-evaluate after usage data |
| Tool loop not streaming for v1 | Streaming adds frontend complexity; typing indicator is sufficient for v1 |
| Rate limit 20 msgs/hour in-memory | Prevents runaway API spend; simple to implement; revisit when per-user cost tracking exists |
