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

# Integration tests (real PostgreSQL - requires workout_planner_test DB)
.venv/bin/pytest tests/integration/ -v

# All backend tests
.venv/bin/pytest -q

# Frontend tests (Vitest + React Testing Library)
cd frontend && npm run test:run
```

Current: **340 backend unit + 216 frontend = 556 automated tests passing** (+ integration tests run separately)

New test files added:
- `tests/api/test_jobs.py` - `POST /jobs/scan` (202, 400 no channels, 503 no key, 401 unauth, channel count); `GET /jobs/status` (no pipeline, unauthenticated, reflects live state); scanner filters (upper duration cap, title blocklist); classifier (batch cap limits to 300, `on_progress` callback during polling, resume existing batch, batch ID cleared on completion)
- `tests/api/test_admin.py` - 21 tests: stats shape, user/library counts, last_active_at, AI usage aggregation (7d + all-time), 403 for non-admin, 403 with no ADMIN_EMAIL set, delete user, cannot delete self, 404 nonexistent, retry scan (no channels → 400, with channels → 202), create/list/delete/deactivate announcements, active announcement for regular user, null when none active, inactive not returned
- `tests/integration/test_jobs_api.py` - 5 integration cases for `POST /jobs/scan` against real Postgres (user isolation, FK constraints, channel count)
- `tests/integration/test_schema.py` - updated to expect Alembic version "003" (update to "004" after next migration run)
- `tests/api/test_email.py` - 9 tests for `send_weekly_plan_email`: subject line, HTML content (video titles + URLs), recipient address, missing API key error, display name fallback, FROM_EMAIL env var, all-rest plan, rest days excluded from output
- `tests/api/test_feedback.py` - 13 unit tests for `POST /feedback` router (happy path, all categories, invalid category, blank message, unauthenticated, trim, 503 on email failure) and `send_feedback_email` service (to=admin, reply_to=user, subject label, HTML body, missing API key, display_name fallback)
- `tests/integration/test_feedback_api.py` - 5 integration tests for `POST /feedback` against real PostgreSQL
- `tests/api/helpers.py` - shared `make_mock_user()` factory used by test_email.py and test_feedback.py
- `frontend/src/test/ThemeProvider.test.tsx` - 6 tests: system-dark default, system-light default, explicit dark/light override, toggle persists, system change respects explicit choice
- `frontend/src/test/ThemeToggle.test.tsx` - 3 tests: renders correctly, toggles on click, aria-label reflects current theme
- `frontend/src/app/dashboard/page.test.tsx` - 22 tests: stale plan banner (show/hide/dismiss/generate), plan rendering, week label, announcement banner, swap picker (open, video list, type filter, show-all-types, cancel, swap call, post-swap close), already-set-up banner (from=onboarding param shows banner, dismiss, no-channels does not redirect)
- `frontend/src/app/onboarding/page.test.tsx` - guard tests: redirects to /dashboard?from=onboarding when user has channels, no redirect when no channels, redirects to / when getMe fails, admin user not redirected despite having channels; all 44 tests use async `renderPage()` helper to wait for guard before interacting
- `tests/integration/test_publish_api.py` - 5 integration tests: POST /plan/publish returns 202, `_run_publish` background success sets done + persists playlist ID, revoked token sets failed + marks credentials invalid, no-plan user gets 404, GET /auth/me includes youtube_connected + credentials_valid
- `tests/api/test_auth.py` updated (+6 tests): login does not include YouTube scope, uses select_account prompt; `/auth/youtube/connect` requires auth + redirects to Google with YouTube scope + login_hint; `/auth/youtube/callback` stores refresh token + rejects bad state; delete_me helper refactored to manually seed credentials
- `tests/api/test_admin.py` - 5 new: reset-onboarding removes channels+schedule, preserves channel+videos, does not affect other users, 404 unknown user, 403 non-admin
- `tests/integration/test_admin_reset_api.py` - 2 integration tests: reset clears subscriptions+schedule, does not touch other user subscriptions
- `frontend/src/app/settings/page.test.tsx` - 27 tests: initial render, display name save/error, schedule save/error, delete 2-step confirm/cancel/confirm-calls-API, fitness profile pre-select/save/error/life-stage-change, channel change regenerate banner (add + remove + dismiss + regenerate + error)
- `frontend/src/components/ChannelManager.test.tsx` - channel limit tests: hides search at 5 channels, shows limit message, suggestion cards disabled at limit
- `frontend/src/app/library/page.test.tsx` - 20 tests: video rendering, total count, empty state, filters, clear filters, no-match empty state, assign-to-day success/error, pagination, background-classifying banner (show/hide/dismiss/API failure)
- `frontend/src/components/FeedbackWidget.test.tsx` - 11 tests: floating button, modal open/close, state reset, category selection, submit disabled on empty/whitespace, submit calls API, success state, error state
- `frontend/src/components/ScheduleEditor.test.tsx` - 11 tests: all 7 days render, Rest/Set-rest button counts, toggle rest clears fields, toggle active restores defaults, workout type select, body focus select, clear body focus, duration min/max inputs
- `tests/api/test_channels.py` - 6 new suggestion tests: cache hit (all 3 served from DB, no YouTube call), cache miss (YouTube called + result stored), no API key returns only cached, no profile returns general list, unknown profile falls back to general, unauthenticated 401
- `tests/integration/test_channels_api.py` - 1 new suggestion test: full cache-hit path against real PostgreSQL (all 3 pre-loaded, YouTube not called)
- `tests/api/test_lazy_classification.py` - 33 tests for the lazy classification pipeline (F9):
- `frontend/src/app/onboarding/page.test.tsx` - 6 new tests in "pre-auth onboarding flow" describe block: renders step 1 unauthenticated (no redirect), "Create free account" label on step 6, "Looks good" label when authenticated, saves onboarding_pending to localStorage, restores pending state + calls updateSchedule on OAuth return, shows error if updateSchedule fails on pending restore
- `frontend/src/app/page.test.tsx` - updated: "Sign in nav link points to auth/google URL" (exact match) + "Get started free CTA links point to /onboarding" (split from combined test)
- `frontend/src/app/dashboard/page.test.tsx` - 5 new tests: rest day cards render on all 7 days, all day labels shown, MissingVideoCard renders for scheduled_workout_type days, deterministic messages per day+weekStart, all three card types use uniform height
- `tests/api/test_admin.py` - updated `test_reset_onboarding_removes_channels_schedule_and_plan` to also verify ProgramHistory rows are deleted
- `tests/test_classifier.py` - updated `test_parse_classification_invalid_fields`: replaced "Dance" (now valid) with "Zumba" as the invalid workout type
  - `can_fill_plan()`: all slots satisfied → True; any slot below threshold → False; all-rest schedule → True (edge case); case-insensitive workout_type matching; NULL duration defaults
  - `get_gap_types()`: returns only slots below MIN_PLAN_CANDIDATES; empty schedule; duplicate slot types counted correctly
  - `rule_classify_for_user()`: classifies matching titles, skips non-matching, idempotent on re-run
  - `build_targeted_batch()`: targeted vs remainder split; cap scaling with multiple gap types; unknown gap type "Other" → remainder; NULL title guard (no crash); multi-pattern dedup (video matching multiple patterns counted once); user isolation (only sees own unclassified videos)
  - `classify_for_user()` with `preselected_videos`: uses provided list instead of DB fetch; MAX_CLASSIFY_PER_RUN cap still applied; empty preselected list returns 0
  - Pipeline fast path: `can_fill_plan=True` → Anthropic batch not submitted, background task started, `background_classifying=True` in status
  - Pipeline slow path: `can_fill_plan=False` → targeted batch submitted, plan generated, remainder sent to background

---

## Frontend Tests (Phase B)

```bash
cd frontend && npm run test:run
```

193 tests covering:
- `scheduleTemplates.ts` - `buildSchedule()` logic for all life-stage/goal/days/duration combinations
- `ChannelManager.tsx` - search, add, remove, suggestions chips, minimum-1-channel gate
- Onboarding page steps - step rendering, auto-advance, schedule preview, scan progress
- `ThemeProvider.tsx` + `ThemeToggle.tsx` - theme context, localStorage, system preference
- `DashboardPage` - stale banner, plan rendering, announcements, swap picker
- `SettingsPage` - display name, schedule save, delete account flow
- `LibraryPage` - video rendering, filters, assign-to-day, pagination
- `FeedbackWidget` - modal, category selection, submit, error/success states
- `ScheduleEditor` - toggle rest/active, workout type/focus dropdowns, duration inputs
- `ChannelManager` - suggestion card grid (thumbnail, + Add, ✓ Added, skeleton), one-click add calls API directly (no search), search flow unchanged

---

## Manual E2E - Phase B (onboarding redesign)

Can be run against local dev servers or the live deployment.

- [ ] Complete onboarding as **senior profile** → verify schedule defaults to beginner difficulty + short duration
- [ ] Complete onboarding as **athlete profile** → verify schedule defaults to advanced difficulty + long duration
- [ ] Verify "Customise" on step 5 shows `ScheduleEditor` inline and changes persist when continuing
- [ ] Verify step 7 progress bar advances through all 4 stages (scanning → classifying → generating → done) and auto-navigates to `/dashboard`
- [ ] Verify minimum-1-channel gate on step 6 still blocks the Continue button when no channels are added
- [ ] Verify returning users (already has channels) bypass onboarding and go directly to `/dashboard`

---

## Manual E2E - Phase 4 + 5

Can be run against either local servers or the live deployment.

**Local:**
```bash
# Terminal 1 - backend
cd ~/Projects/youtube-workout-planner
set -a && source .env && set +a
.venv/bin/uvicorn api.main:app --reload

# Terminal 2 - frontend
cd ~/Projects/youtube-workout-planner/frontend
npm run dev
```
Open `http://localhost:3000` in a fresh browser (or incognito).

**Production (live):**
Open `https://planmyworkout.vercel.app` in a fresh incognito window.
API Swagger: `https://planmyworkout-api.up.railway.app/docs`.

Delete checklist items as you verify them; delete the whole group when all ticked.

---

### Group 1 - Landing page

- [ ] Logo "Workout Planner" left, "Sign in" right
- [ ] Hero: headline, sub-headline, "Get started free →" CTA, "Free · No credit card" badge
- [ ] "How it works" section: 3 numbered steps
- [ ] "Why Workout Planner" section: 3 feature cards
- [ ] Bottom CTA section + footer visible
- [ ] Both CTA buttons navigate to Google OAuth (check URL contains `accounts.google.com`)
- [ ] Already signed-in user visiting `/` gets silently redirected (spinner → dashboard or onboarding)

---

### Group 2 - Sign-in & onboarding (new user)

Sign out first (or use incognito) so you hit onboarding as a new user.

- [ ] "Get started free" → Google OAuth consent screen → redirected back to `localhost:3000`
- [ ] New user lands on `/onboarding` (not dashboard)
- [ ] **Step 1 - Channels:** search returns results with thumbnails + descriptions
- [ ] Adding a channel shows it in the list below; "Continue" enabled only after ≥1 added
- [ ] **Step 2 - Schedule:** grid pre-filled with default split (Mon=Strength/Upper, Sun=Rest, etc.)
- [ ] Can toggle any day to rest; can change workout type / body focus / difficulty / duration
- [ ] "Continue" navigates to Step 3
- [ ] **Step 3 - Generate:** "Generate my first plan now" shows spinner, redirects to `/dashboard?scanning=1`
- [ ] Dashboard shows "Scanning your channels…" banner; plan grid appears automatically when scan finishes (polls every 15s)
- [ ] Returning user (already has channels) goes directly to `/dashboard` - onboarding skipped

---

### Group 3 - Dashboard

- [ ] Header: user first name shown (e.g. "Harshit's plan"), week-of label beneath
- [ ] Nav buttons present: Library | Settings | Regenerate | Publish to YouTube | Sign out
- [ ] All nav buttons show hand cursor on hover
- [ ] Plan grid: 7 day columns with thumbnails, duration badge (bottom-right of thumbnail)
- [ ] Each card shows title (2-line clamp), channel name, workout/body/difficulty badges
- [ ] Clicking a video card opens YouTube in a new tab
- [ ] Sunday shows "Rest day" placeholder card
- [ ] "Regenerate" (when plan exists) triggers a new plan synchronously - "Generating…" banner shows briefly, grid updates
- [ ] "Generate plan" (when no plan) starts full scan+classify+generate pipeline - scanning banner shows, plan appears when done
- [ ] No plan + no channels: empty state shows "Set up my plan →" link to onboarding (not the scan button)
- [ ] Sign out clears session → redirected to `/`; back button does not restore dashboard

**Publish to YouTube (Phase 5)**
- [ ] "Publish to YouTube" button is active (red border), cursor is pointer
- [ ] Clicking "Publish to YouTube" shows "Publishing…" while in flight
- [ ] On success: green banner appears - "{N} videos added to your playlist" + "Open playlist →" link
- [ ] "Open playlist →" opens the correct YouTube playlist in a new tab
- [ ] Playlist in YouTube contains the correct videos in Mon→Sat order
- [ ] Publishing a second time (after regenerating) updates the same playlist - no duplicate playlist created
- [ ] If YouTube access is revoked: amber banner - "Your YouTube access has been revoked…"
- [ ] Revoked state: Publish button is greyed out with `cursor-not-allowed`; tooltip explains the issue

---

### Group 4 - Library

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
- [ ] Assign when no plan exists → shows "Failed - generate a plan first" error
- [ ] After assigning, navigate to dashboard - the newly assigned video appears on that day
- [ ] Pagination: Previous disabled on page 1; Next disabled on last page; no overlapping videos across pages
- [ ] Applying a filter while on page >1 resets to page 1

---

### Group 5 - Settings

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

### Group 6 - API sanity (Swagger at `http://localhost:8000/docs`)

Authenticate via browser first (session cookie), then use Swagger:

- [ ] `GET /auth/me` → 200 with `id`, `email`, `display_name`, `youtube_connected`, `credentials_valid`
- [ ] `PATCH /auth/me` with `{"display_name": "Test"}` → 200 with updated name
- [ ] `DELETE /auth/me` → 204; subsequent `GET /auth/me` → 401
- [ ] `GET /library?workout_type=HIIT` and `?workout_type=hiit` → same result count (case-insensitive)
- [ ] `GET /library?page=0` → 422; `GET /library?limit=101` → 422
- [ ] Unauthenticated `GET /library` → 401
- [ ] `POST /plan/publish` → 200 with `playlist_url` and `video_count`

---

### Group 7 - Mobile (resize browser to ~390px wide)

- [ ] Landing page: single column, CTA button full-width
- [ ] Dashboard grid: 1 column (mobile) → 2 columns (sm) → 4 columns (lg)
- [ ] Dashboard header buttons wrap cleanly (no overflow)
- [ ] Library grid: 1 column (mobile) → 2 columns (sm) → 4 columns (lg)
- [ ] Settings: sections stack vertically, no horizontal overflow
- [ ] Onboarding: all 3 steps usable at mobile width

---

### Group 8 - Theme toggle (all pages)

- [ ] On first visit (no localStorage), page renders in system-preferred theme (light or dark)
- [ ] Floating sun/moon button visible bottom-right on all pages (dashboard, library, settings, guide)
- [ ] Clicking the toggle switches theme immediately (no page reload)
- [ ] Theme persists across page refresh (localStorage)
- [ ] Theme persists when navigating between pages
- [ ] Changing system preference while "system" is active updates theme; explicit user toggle is not overridden by system changes

---

### Group 9 - Feedback widget

- [ ] Floating "Feedback" pill visible bottom-right on dashboard, library, and settings pages
- [ ] Clicking opens a modal with category dropdown (Feedback / Help / Bug report) and a textarea
- [ ] Submitting with blank message shows an inline error (blocked)
- [ ] Submitting valid feedback closes modal and shows success toast
- [ ] Feedback not visible on landing page, guide, admin pages

---

### Group 10 - Guide page (`/guide`)

- [ ] Page loads at `https://planmyworkout.vercel.app/guide`
- [ ] Sticky sidebar nav visible on desktop (≥ lg breakpoint)
- [ ] All 7 sections present: Getting started, Weekly plan, Library, Settings,
      How the plan is built, Publish to YouTube, FAQ
- [ ] "Guide" link in homepage nav navigates to `/guide`
- [ ] "User Guide" link in homepage footer navigates to `/guide`
- [ ] Page readable and not overflowing on mobile

---

### Group 11 - Admin console (`/admin`)

- [ ] Non-admin user hitting `/admin` sees "Access denied" (or redirect)
- [ ] Admin user sees stat cards: Total users, Library size, AI usage (7d), AI usage (all-time)
- [ ] Per-user table shows: email, last active, channels, videos, YouTube connected, last plan, pipeline stage
- [ ] "↺ Scan" button triggers scan for that user → shows "Scan triggered" feedback
- [ ] "Delete" button shows confirmation, then deletes user on confirm
- [ ] Announcements panel: can create new announcement, list existing, deactivate, delete
- [ ] Active announcement appears as dismissible banner on dashboard for all users
- [ ] Dashboard header shows "Admin" nav link when logged in as admin user
- [ ] Admin link not visible for regular users

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
