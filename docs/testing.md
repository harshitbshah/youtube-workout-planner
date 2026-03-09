# Testing Plan

---

## Philosophy

- Don't start the next phase until `pytest` is green on the current one
- Pure functions → unit tests (no mocks, no DB)
- DB-dependent logic → integration tests (SQLite unit / real PostgreSQL integration)
- External APIs (YouTube, Anthropic) → mock only, never real calls in automated tests

---

## Automated Tests

Run before every commit:

```bash
# Unit tests (SQLite in-memory, no external deps)
.venv/bin/pytest tests/api/ tests/test_*.py -v

# Integration tests (real PostgreSQL — requires workout_planner_test DB)
.venv/bin/pytest tests/integration/ -v

# All tests
.venv/bin/pytest -q
```

Current: **216/216 passing**

New test files added:
- `tests/api/test_jobs.py` — 5 new cases for `POST /jobs/scan` (202, 400 no channels, 503 no key, 401 unauth, channel count)
- `tests/integration/test_jobs_api.py` — 5 integration cases for `POST /jobs/scan` against real Postgres (user isolation, FK constraints, channel count)

---

## Manual E2E — Phase 4 + 5

Can be run against either local servers or the live deployment.

**Local:**
```bash
# Terminal 1 — backend
cd ~/Projects/youtube-workout-planner
set -a && source .env && set +a
.venv/bin/uvicorn api.main:app --reload

# Terminal 2 — frontend
cd ~/Projects/youtube-workout-planner/frontend
npm run dev
```
Open `http://localhost:3000` in a fresh browser (or incognito).

**Production (live):**
Open `https://youtube-workout-planner-flame.vercel.app` in a fresh incognito window.
API Swagger: `https://youtube-workout-planner-production.up.railway.app/docs`.

Delete checklist items as you verify them; delete the whole group when all ticked.

---

### Group 1 — Landing page

- [ ] Logo "Workout Planner" left, "Sign in" right
- [ ] Hero: headline, sub-headline, "Get started free →" CTA, "Free · No credit card" badge
- [ ] "How it works" section: 3 numbered steps
- [ ] "Why Workout Planner" section: 3 feature cards
- [ ] Bottom CTA section + footer visible
- [ ] Both CTA buttons navigate to Google OAuth (check URL contains `accounts.google.com`)
- [ ] Already signed-in user visiting `/` gets silently redirected (spinner → dashboard or onboarding)

---

### Group 2 — Sign-in & onboarding (new user)

Sign out first (or use incognito) so you hit onboarding as a new user.

- [ ] "Get started free" → Google OAuth consent screen → redirected back to `localhost:3000`
- [ ] New user lands on `/onboarding` (not dashboard)
- [ ] **Step 1 — Channels:** search returns results with thumbnails + descriptions
- [ ] Adding a channel shows it in the list below; "Continue" enabled only after ≥1 added
- [ ] **Step 2 — Schedule:** grid pre-filled with default split (Mon=Strength/Upper, Sun=Rest, etc.)
- [ ] Can toggle any day to rest; can change workout type / body focus / difficulty / duration
- [ ] "Continue" navigates to Step 3
- [ ] **Step 3 — Generate:** "Generate my first plan now" shows spinner, redirects to `/dashboard?scanning=1`
- [ ] Dashboard shows "Scanning your channels…" banner; plan grid appears automatically when scan finishes (polls every 15s)
- [ ] Returning user (already has channels) goes directly to `/dashboard` — onboarding skipped

---

### Group 3 — Dashboard

- [ ] Header: user first name shown (e.g. "Harshit's plan"), week-of label beneath
- [ ] Nav buttons present: Library | Settings | Regenerate | Publish to YouTube | Sign out
- [ ] All nav buttons show hand cursor on hover
- [ ] Plan grid: 7 day columns with thumbnails, duration badge (bottom-right of thumbnail)
- [ ] Each card shows title (2-line clamp), channel name, workout/body/difficulty badges
- [ ] Clicking a video card opens YouTube in a new tab
- [ ] Sunday shows "Rest day" placeholder card
- [ ] "Regenerate" (when plan exists) triggers a new plan synchronously — "Generating…" banner shows briefly, grid updates
- [ ] "Generate plan" (when no plan) starts full scan+classify+generate pipeline — scanning banner shows, plan appears when done
- [ ] No plan + no channels: empty state shows "Set up my plan →" link to onboarding (not the scan button)
- [ ] Sign out clears session → redirected to `/`; back button does not restore dashboard

**Publish to YouTube (Phase 5)**
- [ ] "Publish to YouTube" button is active (red border), cursor is pointer
- [ ] Clicking "Publish to YouTube" shows "Publishing…" while in flight
- [ ] On success: green banner appears — "{N} videos added to your playlist" + "Open playlist →" link
- [ ] "Open playlist →" opens the correct YouTube playlist in a new tab
- [ ] Playlist in YouTube contains the correct videos in Mon→Sat order
- [ ] Publishing a second time (after regenerating) updates the same playlist — no duplicate playlist created
- [ ] If YouTube access is revoked: amber banner — "Your YouTube access has been revoked…"
- [ ] Revoked state: Publish button is greyed out with `cursor-not-allowed`; tooltip explains the issue

---

### Group 4 — Library

- [ ] "← Back" returns to `/dashboard`
- [ ] Total video count shown (e.g. "243 videos")
- [ ] Cards: thumbnail, duration badge, title (2-line clamp), channel name, workout/body/difficulty badges
- [ ] Clicking a card opens YouTube in a new tab
- [ ] Workout type dropdown shows: Strength / HIIT / Cardio / Mobility (not "Hiit")
- [ ] Each filter narrows the grid and updates the total count
- [ ] Combined filters apply as AND (e.g. Strength + Upper = only upper-body strength videos)
- [ ] "Clear filters" resets all dropdowns and restores the full library
- [ ] Channel dropdown hidden when user has only 1 channel
- [ ] "Assign to day" dropdown → success shows "✓ Assigned to Mon" inline for ~2s, then resets
- [ ] Assign when no plan exists → shows "Failed — generate a plan first" error
- [ ] After assigning, navigate to dashboard — the newly assigned video appears on that day
- [ ] Pagination: Previous disabled on page 1; Next disabled on last page; no overlapping videos across pages
- [ ] Applying a filter while on page >1 resets to page 1

---

### Group 5 — Settings

- [ ] "← Dashboard" link returns to `/dashboard`
- [ ] **Profile:** display name editable; "Save" disabled when name is unchanged
- [ ] "Save" shows "Display name updated" confirmation; dashboard header reflects new name on next visit
- [ ] Email shown as read-only (cannot edit)
- [ ] **Channels:** can search and add new channels; newly added channel appears in list
- [ ] Can remove an existing channel (✕ button); removed channel disappears from list
- [ ] **Schedule:** can change workout type / body focus / difficulty / duration for each day
- [ ] Can toggle any day to rest (clears type/focus/duration)
- [ ] "Save schedule" shows "Schedule saved." confirmation
- [ ] Regenerating plan after schedule change uses the new schedule
- [ ] **Danger zone:** "Delete my account" button has red border
- [ ] Clicking shows inline confirmation "Are you sure?" with Yes / Cancel
- [ ] Cancel dismisses confirmation without action
- [ ] Confirming deletion → redirected to `/`; signing in again starts onboarding (fresh account)

---

### Group 6 — API sanity (Swagger at `http://localhost:8000/docs`)

Authenticate via browser first (session cookie), then use Swagger:

- [ ] `GET /auth/me` → 200 with `id`, `email`, `display_name`, `youtube_connected`, `credentials_valid`
- [ ] `PATCH /auth/me` with `{"display_name": "Test"}` → 200 with updated name
- [ ] `DELETE /auth/me` → 204; subsequent `GET /auth/me` → 401
- [ ] `GET /library?workout_type=HIIT` and `?workout_type=hiit` → same result count (case-insensitive)
- [ ] `GET /library?page=0` → 422; `GET /library?limit=101` → 422
- [ ] Unauthenticated `GET /library` → 401
- [ ] `POST /plan/publish` → 200 with `playlist_url` and `video_count`

---

### Group 7 — Mobile (resize browser to ~390px wide)

- [ ] Landing page: single column, CTA button full-width
- [ ] Dashboard grid: 2 columns
- [ ] Library grid: 2 columns, filter bar wraps without overflow
- [ ] Settings: sections stack vertically, no horizontal overflow
- [ ] Onboarding: all 3 steps usable at mobile width

---

## Old CLI Tool Tests

The original `main.py` CLI is feature-complete and not under active development.
Its test coverage is documented in the table below (all passing).

| File | Tests |
|---|---|
| `tests/test_db.py` | `init_db` creates tables, idempotent |
| `tests/test_scanner.py` | Duration parsing, save/dedup logic |
| `tests/test_classifier.py` | JSON parsing, field validation, message building |
| `tests/test_planner.py` | Monday calc, scoring, fallback tiers, history avoidance |
