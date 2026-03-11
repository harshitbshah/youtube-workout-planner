# Implementation TODO

Ordered by priority. Each item links to its spec.

---

## Phase A — AI Cost Reduction (features 1–4)
> Spec: [ai-cost-reduction.md](ai-cost-reduction.md)
> Do before first users arrive. All trivial–small effort.

- [x] **F1** — Reduce `max_tokens` 150 → 80 in `classifier.py`
  - [x] Unit: assert `max_tokens` in built batch payload equals 80

- [x] **F2** — 18-month video cutoff (`CLASSIFY_MAX_AGE_MONTHS` env var)
  - [x] Unit: insert a 6-month-old video and a 24-month-old video — assert only the recent one is fetched
  - [x] Unit: set `CLASSIFY_MAX_AGE_MONTHS=1` — assert only videos within 1 month are fetched

- [x] **F3** — First-scan channel cap (migration 006, `first_scan_done` column, 75-video limit)
  - [x] Unit: mock YouTube returning 200 videos, `first_scan_done=False` — assert only 75 rows saved
  - [x] Unit: assert `channel.first_scan_done=True` after first scan completes
  - [x] Unit: mock YouTube returning 200 videos, `first_scan_done=True` — assert all 200 fetched (no cap)
  - [x] Integration: create channel, run scan, assert `first_scan_done=True` in DB

- [x] **F4** — Skip inactive channels (migration 007, `last_video_published_at` column)
  - [x] Unit: `last_video_published_at=90d ago`, `added_at=60d ago`, `skip_if_inactive=True` → returns 0, no YouTube API call
  - [x] Unit: same channel but `skip_if_inactive=False` → YouTube API is called
  - [x] Unit: `last_video_published_at=30d ago` → NOT skipped (still active)
  - [x] Unit: `last_video_published_at=None` → NOT skipped (newly added, unknown history)
  - [x] Unit: after scan saves videos, assert `last_video_published_at` updated to most recent video date

- [x] **Graceful scanner failure** — add `last_scan_error` to user record; show error banner on dashboard if pipeline fails
  - [x] Unit: pipeline exception sets `last_scan_error` on user record
  - [x] Unit: `GET /jobs/status` includes error message when `last_scan_error` is set
  - [x] Unit: successful pipeline run clears `last_scan_error` to `None`
  - [x] Integration: trigger pipeline that raises, assert `last_scan_error` persisted in DB

### Phase A — Manual E2E
- [ ] **F1** — Trigger a scan on Railway, then check `batch_usage_log` in DB: `output_tokens` should average ≤80 per video
- [ ] **F2** — In Railway psql, verify no `classifications` rows exist for videos with `published_at` older than 18 months after a fresh scan
- [ ] **F3** — Add a brand-new channel, trigger scan, confirm in DB that `first_scan_done=True` and `videos` count ≤75 for that channel
- [ ] **F3** — Trigger a second scan on the same channel, confirm video count grows beyond 75 (incremental, no cap)
- [ ] **F4** — In DB, manually set `last_video_published_at = now() - interval '90 days'` on a channel, wait for Sunday cron (or trigger `run_weekly_pipeline` via Railway shell), confirm that channel's scan is skipped in logs
- [ ] **F4** — Confirm a user-triggered scan (`POST /jobs/scan`) still scans the same "inactive" channel
- [ ] **F4** — Confirm `last_video_published_at` is populated after a normal scan (check in DB)
- [ ] **Graceful failure** — `GET /jobs/status` returns `error: null` for a healthy user with no prior failures

---

## Phase B — Onboarding Redesign
> Spec: [onboarding-redesign.md](onboarding-redesign.md)
> Frontend-only rewrite — no backend changes, no unit/integration tests needed.

- [x] Create `frontend/src/lib/scheduleTemplates.ts` — `buildSchedule()` function + templates
- [x] Add `suggestions` prop to `ChannelManager.tsx`
- [x] Rewrite `frontend/src/app/onboarding/page.tsx` — 7-step wizard
  - [x] Step 1 — Life stage cards
  - [x] Step 2 — Goal cards (varies by life stage)
  - [x] Step 3 — Training days toggle
  - [x] Step 4 — Session length cards
  - [x] Step 5 — Schedule preview + inline customise
  - [x] Step 6 — Add channels with curated suggestions
  - [x] Step 7 — Live scan progress (polls `/jobs/status`, auto-navigate)
- [x] Update `StepIndicator` labels → `Profile · Channels · Your Plan`
- [ ] Manual: senior profile → schedule defaults to beginner difficulty + short duration
- [ ] Manual: athlete profile → schedule defaults to advanced difficulty + long duration
- [ ] Manual: "Customise" on step 5 expands `ScheduleEditor` inline, changes persist
- [ ] Manual: step 7 progress bar advances through all 4 stages and auto-navigates to `/dashboard`
- [ ] Manual: minimum-1-channel gate on step 6 blocks Continue button
- [ ] Manual: returning users (has channels) bypass onboarding to `/dashboard`
- [ ] **"Curated by AI" badge** — add small disclosure badge to plan dashboard (FTC AI disclosure)

---

## Phase C — Weekly Plan Email
> Spec: [email-weekly-plan.md](email-weekly-plan.md)
> Requires Resend account + verified domain before starting.

- [ ] Sign up for Resend, verify `planmyworkout.app` domain
- [ ] Add `resend>=2.0.0` to `requirements.txt`
- [ ] New migration — `users.email_notifications` boolean (default `True`)
- [ ] Create `api/services/email.py` — `send_weekly_plan_email(user, plan)`
- [ ] Create `api/templates/weekly_plan_email.html` — Jinja2 table-based layout
- [ ] Wire into `api/scheduler.py` (step 5 of `_weekly_pipeline_for_user`)
- [ ] Expose `email_notifications` in `GET /auth/me`
- [ ] Add email preference toggle to `frontend/src/app/settings/page.tsx`
- [ ] Set `RESEND_API_KEY`, `FROM_EMAIL`, `APP_URL` env vars on Railway
- [ ] Unit: mock `resend.Emails.send`, call `send_weekly_plan_email` — assert called once, subject contains "week of", HTML contains each non-rest day's video title and URL
- [ ] Unit: rest day entries render as "Recovery" in HTML, not blank
- [ ] Unit: `user.email_notifications=False` → `resend.Emails.send` never called
- [ ] Unit: `RESEND_API_KEY` missing → logs warning and skips cleanly (no crash)
- [ ] Unit: email send failure in scheduler → pipeline continues, error logged, plan still saved
- [ ] Integration: migration adds `email_notifications` column with default `True` for existing rows
- [ ] Manual: trigger pipeline → verify email received in Gmail
- [ ] Manual: rest days render as "Recovery" (not blank)
- [ ] Manual: "Manage notification preferences" link → `/settings#notifications`
- [ ] Manual: toggle email off in Settings → re-trigger pipeline → no email sent
- [ ] Manual: email renders correctly in Gmail web, Apple Mail, and mobile Gmail

- [ ] **Revoked YouTube access email** — add `send_revoked_access_email()` to `api/services/email.py`; trigger when OAuth refresh fails
  - [ ] Unit: mock `resend.Emails.send`, simulate OAuth refresh failure — assert email called with correct user address
  - [ ] Unit: assert email NOT sent when refresh succeeds
  - [ ] Unit: send failure does not suppress the original OAuth error

---

## Phase D — AI Cost Reduction (features 5–8)
> Spec: [ai-cost-reduction.md](ai-cost-reduction.md)

### Done (2026-03-11)

- [x] **F5** — Adaptive payload trimming (`_title_is_descriptive()` helper in `api/services/classifier.py`)
  - [x] Unit: `_title_is_descriptive("30 Min Full Body HIIT")` → `True`
  - [x] Unit: `_title_is_descriptive("My Channel Update")` → `False`
  - [x] Unit: descriptive title → `_fetch_transcript_intro` not called, description capped to 300 chars
  - [x] Unit: ambiguous title → `_fetch_transcript_intro` called, full description used

- [x] **F6** — Rule-based title pre-classifier (`title_classify()` in `api/services/classifier.py`)
  - [x] Unit: `title_classify("30 Min HIIT Cardio Blast", 1800)` → `workout_type="HIIT"`
  - [x] Unit: `title_classify("Morning Yoga Flow for Beginners", 2400)` → `workout_type="Mobility"`, `difficulty="beginner"`
  - [x] Unit: `title_classify("Upper Body Strength Workout", 1800)` → `body_focus="upper"`
  - [x] Unit: `title_classify("My Vlog", 300)` → `None`
  - [x] Unit: 2 obvious + 1 ambiguous → 2 rule-classified without API call, 1 submitted to batch
  - [x] Unit: all obvious → AI batch never submitted, `create()` not called
  - [x] Unit: body focus (full/upper/lower/core), difficulty (beginner/advanced/intermediate), warmup/cooldown flags

### Deferred (until real users / traffic justifies)

- [ ] **F7** — Per-user monthly classification budget cap
  > Protects against runaway costs from heavy manual scanners. Low priority with 1 user.
  - [ ] New migration — `users.monthly_classify_budget` int (default 500, 0=unlimited)
  - [ ] `classify_for_user` raises `BudgetExceededError` when cap hit; pipeline sets stage `budget_exceeded`
  - [ ] Admin `PATCH /admin/users/{id}/budget` endpoint
  - [ ] Dashboard shows dismissible warning banner when `stage=budget_exceeded`
  - [ ] Unit: budget=10, used=10 → raises `BudgetExceededError`
  - [ ] Unit: budget=0 → no error
  - [ ] Unit: budget=100, used=90 → only 10 videos submitted
  - [ ] Unit: admin endpoint sets budget; non-admin gets 403

- [ ] **F8** — Global classification cache (cross-user sharing)
  > Near-zero benefit with 1 user; massive benefit at 50+ users sharing popular channels.
  > Also fixes latent cross-user video dedup bug (User B gets no videos from shared channels).
  - [ ] New migration — `global_classification_cache` table (youtube_video_id PK, full classification fields)
  - [ ] `classify_for_user` checks cache before batch; cache hits written to `Classification` directly
  - [ ] After AI classifies, writes to global cache
  - [ ] Rule-based results (F6) also written to cache
  - [ ] Unit: cache hit → `Classification` row created, Anthropic not called
  - [ ] Unit: cache miss → added to batch
  - [ ] Unit: AI result → cache row written
  - [ ] Integration: user A scans → cache populated; user B same channel → cache hits, no batch

- [ ] *(follow-up to F8)* `UserChannelVideo` join table — proper fix for cross-user channel dedup bug

---

## Phase O1 — Freeform Profile Enrichment
> Spec: [ai-profile-enrichment-and-coach-chat.md](ai-profile-enrichment-and-coach-chat.md)
> Add freeform "Anything else?" step to onboarding. Claude Haiku extracts constraints/preferences silently.

### Migration + models
- [ ] Migration 009 — add `life_stage`, `goal`, `profile_notes`, `profile_enrichment` to `users` table
- [ ] Update `api/models.py` — 4 new columns on `User`

### Backend
- [ ] Create `api/services/enrichment.py` — `enrich_profile(notes: str) -> dict` (Haiku extraction)
- [ ] Add `POST /auth/me/enrich` to `api/routers/auth.py`
- [ ] Extend `PATCH /auth/me` (`PatchMeRequest`) to accept `life_stage` + `goal`
- [ ] Update `api/schemas.py` — `EnrichRequest`, `EnrichResponse`, extend `PatchMeRequest`
- [ ] Update `api/services/planner.py` — read `profile_enrichment.avoid_types` to filter plan generation

### Tests
- [ ] Unit: `test_enrich_profile_extracts_constraint` — "bad knees" → `constraints: ["knee_injury"]`
- [ ] Unit: `test_enrich_profile_extracts_preference` — "love dancing" → `preferred_types: ["dance"]`
- [ ] Unit: `test_enrich_profile_empty_input` — empty string → all empty arrays, no crash
- [ ] Unit: `test_enrich_profile_irrelevant_input` — "I like pizza" → all empty arrays
- [ ] Unit: `test_enrich_endpoint_saves_to_db` — POST → `profile_notes` + `profile_enrichment` written
- [ ] Unit: `test_enrich_endpoint_unauthenticated` → 401
- [ ] Unit: `test_enrich_endpoint_too_long` — 501-char input → 400
- [ ] Unit: `test_enrich_endpoint_anthropic_failure` — mock Anthropic error → 503
- [ ] Unit: `test_planner_respects_avoid_types` — `avoid_types: ["high_impact"]` → no HIIT in plan
- [ ] Unit: `test_planner_no_enrichment` — `profile_enrichment=null` → plan generates normally
- [ ] Integration: `test_full_enrich_and_plan_flow` — POST enrich → plan generated → avoided types absent

### Frontend
- [ ] `app/onboarding/page.tsx` — insert step 6 "Anything else?" between schedule and channels
- [ ] `app/onboarding/page.tsx` — update step numbering (6→7, 7→8); update `StepIndicator`
- [ ] `app/onboarding/page.tsx` — after schedule save (step 5), call `patchMe({ life_stage, goal })`
- [ ] `app/settings/page.tsx` — add "About you" section with `profile_notes` textarea
- [ ] `lib/api.ts` — add `enrichProfile()`, `ProfileEnrichment` type

### Manual
- [ ] Onboarding: type "bad knees" in step 6 → plan has no jumping/HIIT videos
- [ ] Onboarding: click Skip → advances to channels with no API call
- [ ] Onboarding: Anthropic API unavailable → step skips silently, onboarding completes normally
- [ ] Settings: update "About you" → re-run enrichment → plan changes on next regeneration

---

## Phase O2 — AI Coach Chat
> Spec: [ai-profile-enrichment-and-coach-chat.md](ai-profile-enrichment-and-coach-chat.md)
> Floating chat panel on dashboard. Claude Sonnet with tool use (search_library + update_plan_day).

### Migration + models
- [ ] Migration 009 already covers this phase (no additional schema changes needed for v1)

### Backend
- [ ] Create `api/services/coach.py` — `build_coach_system_prompt()`, `build_library_summary()`, `run_coach_turn()`, tool executors
- [ ] Create `api/routers/coach.py` — `POST /coach/chat`, `GET /coach/weekly-review`
- [ ] Register coach router in `api/main.py`
- [ ] Update `api/schemas.py` — `CoachChatRequest`, `CoachChatResponse`, `WeeklyReviewResponse`

### Tests
- [ ] Unit: `test_coach_chat_simple_response` — message with no tool use → text reply returned
- [ ] Unit: `test_coach_chat_search_library_called` — "give me 15 mins" → `search_library` tool executed
- [ ] Unit: `test_coach_chat_search_respects_duration` — `max_duration_min` filter applied in DB query
- [ ] Unit: `test_coach_chat_update_plan_day` — "update Thursday" → `update_plan_day` → history row updated
- [ ] Unit: `test_coach_chat_update_plan_day_returns_flag` — `plan_updated: true`, `updated_day: "thursday"`
- [ ] Unit: `test_coach_chat_excludes_this_week_videos` — `exclude_this_week=true` skips plan videos
- [ ] Unit: `test_coach_chat_constraint_in_system_prompt` — enrichment `knee_injury` → appears in prompt
- [ ] Unit: `test_coach_chat_unauthenticated` → 401
- [ ] Unit: `test_coach_chat_rate_limit` — 21 messages in one hour → 429 on 21st
- [ ] Unit: `test_coach_chat_empty_library` — 0 videos → coach replies gracefully
- [ ] Unit: `test_weekly_review_no_history` — < 2 weeks → `review: null`
- [ ] Unit: `test_weekly_review_returns_cached` — second call same week → no new Claude call
- [ ] Integration: `test_coach_update_persists_to_db` — coach updates Thursday → `program_history` row updated

### Frontend
- [ ] Create `components/CoachPanel.tsx` — slide-over chat panel (message list, input, typing indicator)
- [ ] Create `components/VideoRecommendationCard.tsx` — compact horizontal video card for chat
- [ ] `app/dashboard/page.tsx` — add "Coach" nav button, render `<CoachPanel>`, implement `refetchPlan()`
- [ ] `lib/api.ts` — add `sendCoachMessage()`, `getWeeklyReview()`, `CoachMessage`, `CoachResponse` types

### Manual
- [ ] Dashboard: "Coach" button opens slide-over panel
- [ ] Chat: "give me something shorter" → video card returned with correct duration filter applied
- [ ] Chat: "my shoulder is sore" → no overhead exercises in suggestions
- [ ] Chat: "update Thursday" → plan grid refreshes automatically after coach confirms
- [ ] Chat: 20 messages → 21st returns rate limit error message
- [ ] Panel: close + reopen → conversation history preserved within session
- [ ] Panel: page refresh → conversation history cleared (expected)
- [ ] Mobile: panel opens full-screen

---

## Phase O3 — Weekly AI Review Card
> Spec: [ai-profile-enrichment-and-coach-chat.md](ai-profile-enrichment-and-coach-chat.md)
> Dismissible review card on dashboard Monday mornings. Claude Haiku, cached per week.

### Migration + models
- [ ] Migration 010 — add `weekly_review_cache` (Text), `weekly_review_generated_at` (DateTime) to `users`
- [ ] Update `api/models.py` — 2 new columns on `User`

### Backend
- [ ] Add `GET /coach/weekly-review` logic to `api/routers/coach.py` — Haiku call, cache check, return `{ review }`

### Tests
- [ ] Unit: `test_weekly_review_generates_on_monday` — Monday + no cache → Haiku called
- [ ] Unit: `test_weekly_review_cached_within_week` — cache hit → Haiku not called
- [ ] Unit: `test_weekly_review_null_insufficient_history` — < 2 weeks data → `review: null`

### Frontend
- [ ] `app/dashboard/page.tsx` — fetch weekly review on load; render dismissible card on Mondays
- [ ] Card includes "Open Coach →" button that opens `CoachPanel`

### Manual
- [ ] Monday: review card visible at top of dashboard
- [ ] Dismiss card: does not reappear until next Monday
- [ ] "Open Coach →" opens the coach panel
- [ ] Non-Monday: card not shown
