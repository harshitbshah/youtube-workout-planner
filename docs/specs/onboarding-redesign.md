# Onboarding Redesign - Design Spec

**Status:** ✅ Implemented (2026-03-11)
**Replaces:** `frontend/src/app/onboarding/page.tsx` (current 3-step wizard)
**Last updated:** 2026-03-13

> **Subsequent specs that affect this flow:**
> - [ai-profile-enrichment.md](ai-profile-enrichment.md) - AI Profile Enrichment inserts a new **step 6 ("Anything else?")** between schedule preview and channels, making the total **8 steps** (not 7). It also persists `life_stage` and `goal` to the DB via `PATCH /auth/me`.
> - [channel-recommendations.md](channel-recommendations.md) - Curated Channel Recommendations replaces the hardcoded channel suggestion chips in step 6/7 with a dynamic `GET /channels/curated` card grid. The `suggestions?: string[]` prop on `ChannelManager` becomes `showCurated / profile / goal / scheduleTypes` props.

---

## Why

The current onboarding (Channels → Schedule → Done) has two problems:

1. Users are handed a raw `ScheduleEditor` grid with no context - most just click through
   the default without understanding it.
2. Step 3 is a dead-end confirmation screen. The user presses "Generate my first plan"
   and gets redirected to a dashboard with a spinner and no sense of progress.

The redesign collects the user's *goal* and *life stage* first, then uses those answers
to pre-build a tailored schedule. The user confirms or tweaks - they never stare at a
blank grid.

---

## Flow Overview

```
Step 1 - Life stage     (4 cards)
Step 2 - Goal           (3–4 options, varies by life stage)
Step 3 - Training days  (2–6 visual toggle)
Step 4 - Session length (4 options)
     ↓
  [auto-generate schedule from answers]
     ↓
Step 5 - Schedule preview  (human-readable, confirm or customise)
Step 6 - Add channels      (curated suggestions + free search)
Step 7 - Live scan progress (polls /jobs/status, auto-navigates to /dashboard)
```

Total steps: 7 (but steps 1–4 are fast single-click screens - feels lighter than 3
slow steps).

---

## Step 1 - Life Stage

**Heading:** "First, tell us a bit about yourself"
**Sub-heading:** "We'll tailor your plan to fit."

Four large tap-friendly cards (not a dropdown):

| Value | Label | Sub-label |
|---|---|---|
| `beginner` | Just starting out | New to working out, or getting back into it |
| `adult` | Active adult | Reasonably fit, been training for a while |
| `senior` | 55 and thriving | Low-impact, joint-friendly, no gym required |
| `athlete` | Training seriously | Structured programming, performance goals |

**UX notes:**
- Cards, not a dropdown - one tap, no confirmation needed, advance automatically.
- For `senior` profile: increase base font size (add `text-lg` to step content wrapper),
  use plain language throughout (no jargon), cap options to 3 per screen.

---

## Step 2 - Goal

**Heading:** "What's your main goal?"

Options vary by life stage chosen in step 1:

| Life Stage | Options |
|---|---|
| `beginner` | Build a habit · Lose weight · Feel more energetic |
| `adult` | Build muscle · Lose fat · Improve cardio · Stay consistent |
| `senior` | Stay active & healthy · Improve flexibility · Build strength safely |
| `athlete` | Strength & hypertrophy · Endurance · Athletic performance · Cut weight |

Same card UI as step 1. Advance automatically on tap.

---

## Step 3 - Training Days per Week

**Heading:** "How many days a week can you train?"
**Sub-copy (below selection):** "Even 2 days/week makes a real difference."

Visual toggle buttons: `[2]  [3]  [4]  [5]  [6]`

Rules:
- `senior` profile: show `[2]  [3]  [4]  [5]`, default = `3`
- `beginner` profile: default = `3`
- `adult` profile: default = `4`
- `athlete` profile: default = `5`

Advance on tap (no Continue button needed for single-choice screens).

---

## Step 4 - Session Length

**Heading:** "How long per session?"

| Value | Label | Sub-label |
|---|---|---|
| `short` | 15–20 min | Quick and consistent |
| `medium` | 25–35 min | A solid session |
| `long` | 40–60 min | Full workout |
| `any` | No preference | Let the video decide |

Rules:
- `senior` + `beginner`: default = `short`, show affirming copy:
  *"Short sessions are just as effective when done consistently."*
- `athlete`: default = `long`

---

## Schedule Generation Logic

After step 4, generate a `ScheduleSlot[]` array from the four answers before showing
step 5. No API call needed - pure frontend logic.

The mapping lives in a new file: `frontend/src/lib/scheduleTemplates.ts`

### Duration mapping

```ts
const DURATION_MAP = {
  short:  { min: 15, max: 20 },
  medium: { min: 25, max: 35 },
  long:   { min: 40, max: 60 },
  any:    { min: 20, max: 60 },
};
```

### Difficulty mapping

```ts
const DIFFICULTY_MAP = {
  beginner: "beginner",
  adult:    "intermediate",
  senior:   "beginner",
  athlete:  "advanced",
};
```

### Schedule templates per profile + days

The templates define *slot types* for each active day. Rest days fill remaining days
(prefer Wed/Sun as rest if 5 days; prefer Tue/Thu/Sun if 3 days).

**`senior` - any goal**
```
Priority order: mobility → cardio → strength
Day slots (3-day example): mobility/full, cardio/full, strength/full
Difficulty: beginner
```

**`beginner` - any goal**
```
Priority order: cardio → strength → mobility
Day slots (3-day example): cardio/full, strength/full, mobility/full
Difficulty: beginner
```

**`adult` + `Build muscle` / `Strength & hypertrophy`**
```
5-day example:
  Mon: strength/upper, Tue: hiit/full, Wed: strength/lower,
  Thu: rest,           Fri: strength/full, Sat: cardio/full, Sun: rest
```

**`adult` + `Lose fat` / `Improve cardio` / `Cut weight`**
```
4-day example:
  Mon: hiit/full, Tue: cardio/full, Wed: rest,
  Thu: hiit/core, Fri: cardio/full, Sat: rest, Sun: rest
```

**`adult` + `Stay consistent` / `Feel more energetic`**
```
Mix of cardio + mobility + 1 strength day
```

**`athlete` + `Endurance` / `Athletic performance`**
```
6-day example:
  Mon: strength/upper, Tue: hiit/full,     Wed: strength/lower,
  Thu: strength/full,  Fri: hiit/core,     Sat: cardio/full, Sun: rest
```

Full implementation detail: write a `buildSchedule(profile, goal, days, duration)`
function in `scheduleTemplates.ts` that returns a `ScheduleSlot[]` ready to pass
to `ScheduleEditor` and eventually to `PUT /schedule`.

---

## Step 5 - Schedule Preview

**Heading:** "Here's your personalised plan"
**Sub-heading:** "Based on your goals. Tweak anything you like."

Show a simple, human-readable list (not the full `ScheduleEditor` grid):

```
Mon  · Mobility · 15–20 min · Beginner
Tue  · Recovery day
Wed  · Light cardio · 15–20 min · Beginner
Thu  · Recovery day
Fri  · Strength · 15–20 min · Beginner
Sat  · Recovery day
Sun  · Recovery day
```

**UX notes:**
- Use "Recovery day" not "Rest" for `senior` profile (feels intentional, not lazy).
- Use plain English workout labels: "Light cardio" not "cardio", "Mobility & stretching"
  not "mobility".
- Two buttons: **"Looks good →"** (primary) and **"Customise"** (secondary/ghost).
- "Customise" expands the full `ScheduleEditor` component inline (same component as
  `frontend/src/components/ScheduleEditor.tsx`) - no separate step needed.

---

## Step 6 - Add Channels

**Heading:** "Add your favourite channels"
**Sub-heading:** Varies by profile:
- `senior`: *"Search for YouTube channels focused on gentle movement and healthy ageing."*
- `beginner`: *"Search for beginner-friendly YouTube fitness channels."*
- others: *"Search for YouTube fitness channels to include in your plan."*

**Curated suggestions row** (shown above the search bar):

> **Superseded by Curated Channel Recommendations:** The hardcoded chips below will be replaced by a dynamic
> `GET /channels/curated` card grid once [channel-recommendations.md](channel-recommendations.md)
> is implemented. Until then, the hardcoded list is used as-is.

These are hardcoded display names + channel IDs. Show as horizontal scrollable chips
that add the channel on tap (same as clicking search result). Filter by profile:

| Profile | Suggested channels (display only - user still needs to search to find their own) |
|---|---|
| `senior` | "Grow Young Fitness", "HASfit (senior)", "SilverSneakers" |
| `beginner` | "Sydney Cummings Houdyshell", "Heather Robertson", "MommaStrong" |
| `adult` | "Athlean-X", "Heather Robertson", "Jeff Nippard", "Yoga with Adriene" |
| `athlete` | "Athlean-X", "Jeff Nippard", "Renaissance Periodization" |

Implementation note: these are just `ChannelManager` with a suggestions prop added.
The existing `POST /channels` + `GET /channels/search` API is unchanged.

Minimum 1 channel required to continue (same as current flow).

---

## Step 7 - Live Scan Progress

Replace the current dead-end "Done" screen with a live progress tracker.

**Heading:** "Setting up your plan…"

Show a vertical checklist that updates in real time:

```
[✓] Profile saved
[✓] Schedule saved
[⟳] Scanning channels...     ← animates when active
[ ] Classifying videos
[ ] Building your first plan
```

Poll `GET /jobs/status` every 3 seconds (already exists, returns `{stage, total, done}`).

Stage → checklist item mapping:
```ts
"scanning"    → item 3 active
"classifying" → item 3 done, item 4 active
"planning"    → item 4 done, item 5 active
"done"        → all done → auto-navigate to /dashboard after 800ms delay
```

When done, navigate to `/dashboard` automatically - no button needed.
If an error occurs, show a red banner with a "Try again" button that re-calls
`POST /jobs/scan`.

---

## Component / File Changes

| File | Change |
|---|---|
| `frontend/src/app/onboarding/page.tsx` | Full rewrite - new 7-step wizard |
| `frontend/src/lib/scheduleTemplates.ts` | New file - `buildSchedule()` function + templates |
| `frontend/src/components/ChannelManager.tsx` | Add optional `suggestions` prop (array of channel name strings) |
| `frontend/src/components/ScheduleEditor.tsx` | No change needed |
| `frontend/src/lib/api.ts` | No change needed - all required endpoints already exist |

Backend: **no changes needed.** All required endpoints exist:
- `PUT /schedule` - save generated schedule
- `POST /channels` - add a channel
- `POST /jobs/scan` - trigger pipeline
- `GET /jobs/status` - poll progress

---

## StepIndicator Update

Current indicator: `Channels → Schedule → Done`
New indicator: `Profile → Goal → Availability → Channels → Done`
(Steps 3 + 4 are single-tap, so they don't need to be shown in the indicator -
fold them into "Profile" visually.)

Suggested labels: `Profile · Channels · Your Plan`
(3 visible steps even though there are 7 internal steps - keeps the progress bar
from feeling overwhelming.)

---

## What NOT to Change

- The `ScheduleEditor` and `ChannelManager` components are reused as-is.
- The backend API is unchanged.
- The routing logic (`new user → /onboarding`, returning user → /dashboard`) is unchanged
  - it lives in `api/routers/auth.py` and the landing page `useEffect`.

> **Superseded by AI Profile Enrichment:** `life_stage` and `goal` are now persisted to the DB
> via migration 009 and `PATCH /auth/me`. The claim below is no longer accurate
> once AI Profile Enrichment is implemented.

- ~~No new DB columns needed. Life stage and goal are onboarding-only UI state; they
  don't need to be persisted.~~ - **Superseded by AI Profile Enrichment.** See
  [ai-profile-enrichment.md](ai-profile-enrichment.md).

---

## Testing

After implementation, add to `docs/testing.md` manual checklist:

- [ ] Complete onboarding as `senior` profile - verify schedule defaults to beginner/short
- [ ] Complete onboarding as `athlete` profile - verify schedule defaults to advanced/long
- [ ] Verify "Customise" on step 5 shows `ScheduleEditor` and changes persist
- [ ] Verify step 7 progress bar advances through all 4 stages and auto-navigates
- [ ] Verify minimum-1-channel gate on step 6 still blocks the Continue button
- [ ] Verify returning users (has channels) still bypass onboarding to `/dashboard`
