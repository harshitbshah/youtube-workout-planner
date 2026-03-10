# Implementation TODO

Ordered by priority. Each item links to its spec.

---

## Phase A — AI Cost Reduction (features 1–4)
> Spec: [ai-cost-reduction.md](ai-cost-reduction.md)
> Do before first users arrive. All trivial–small effort.

- [ ] **F1** — Reduce `max_tokens` 150 → 80 in `classifier.py`
  - [ ] Unit: assert `max_tokens` in built batch payload equals 80

- [ ] **F2** — 18-month video cutoff (`CLASSIFY_MAX_AGE_MONTHS` env var)
  - [ ] Unit: insert a 6-month-old video and a 24-month-old video — assert only the recent one is fetched
  - [ ] Unit: set `CLASSIFY_MAX_AGE_MONTHS=1` — assert only videos within 1 month are fetched

- [ ] **F3** — First-scan channel cap (migration 006, `first_scan_done` column, 75-video limit)
  - [ ] Unit: mock YouTube returning 200 videos, `first_scan_done=False` — assert only 75 rows saved
  - [ ] Unit: assert `channel.first_scan_done=True` after first scan completes
  - [ ] Unit: mock YouTube returning 200 videos, `first_scan_done=True` — assert all 200 fetched (no cap)
  - [ ] Integration: create channel, run scan, assert `first_scan_done=True` in DB

- [ ] **F4** — Skip inactive channels (migration 007, `last_video_published_at` column)
  - [ ] Unit: `last_video_published_at=90d ago`, `added_at=60d ago`, `skip_if_inactive=True` → returns 0, no YouTube API call
  - [ ] Unit: same channel but `skip_if_inactive=False` → YouTube API is called
  - [ ] Unit: `last_video_published_at=30d ago` → NOT skipped (still active)
  - [ ] Unit: `last_video_published_at=None` → NOT skipped (newly added, unknown history)
  - [ ] Unit: after scan saves videos, assert `last_video_published_at` updated to most recent video date

- [ ] **Graceful scanner failure** — add `last_scan_error` to user record; show error banner on dashboard if pipeline fails
  - [ ] Unit: pipeline exception sets `last_scan_error` on user record
  - [ ] Unit: `GET /jobs/status` includes error message when `last_scan_error` is set
  - [ ] Unit: successful pipeline run clears `last_scan_error` to `None`
  - [ ] Integration: trigger pipeline that raises, assert `last_scan_error` persisted in DB

---

## Phase B — Onboarding Redesign
> Spec: [onboarding-redesign.md](onboarding-redesign.md)
> Frontend-only rewrite — no backend changes, no unit/integration tests needed.

- [ ] Create `frontend/src/lib/scheduleTemplates.ts` — `buildSchedule()` function + templates
- [ ] Add `suggestions` prop to `ChannelManager.tsx`
- [ ] Rewrite `frontend/src/app/onboarding/page.tsx` — 7-step wizard
  - [ ] Step 1 — Life stage cards
  - [ ] Step 2 — Goal cards (varies by life stage)
  - [ ] Step 3 — Training days toggle
  - [ ] Step 4 — Session length cards
  - [ ] Step 5 — Schedule preview + inline customise
  - [ ] Step 6 — Add channels with curated suggestions
  - [ ] Step 7 — Live scan progress (polls `/jobs/status`, auto-navigate)
- [ ] Update `StepIndicator` labels → `Profile · Channels · Your Plan`
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
> Defer until traffic warrants. Feature 8 requires schema decision.

- [ ] **F5** — Adaptive payload trimming (`title_is_descriptive()` helper)
  - [ ] Unit: `title_is_descriptive("30 Min Full Body HIIT")` → `True`
  - [ ] Unit: `title_is_descriptive("My Channel Update")` → `False`
  - [ ] Unit: descriptive title → built request uses short description, no transcript
  - [ ] Unit: ambiguous title → built request uses full description + transcript

- [ ] **F6** — Rule-based title pre-classifier (`title_classify()`, saves 30–40% AI calls)
  - [ ] Unit: `title_classify("30 Min Full Body HIIT", 1800)` → `workout_type="HIIT"`
  - [ ] Unit: `title_classify("Beginner Yoga Flow", 2400)` → `workout_type="Mobility"`, `difficulty="beginner"`
  - [ ] Unit: `title_classify("Upper Body Strength", 1800)` → `body_focus="upper body"`
  - [ ] Unit: `title_classify("My Vlog", 300)` → `None`
  - [ ] Unit: end-to-end — 2 obvious + 1 ambiguous video → 2 classifications created without API call, 1 submitted to batch

- [ ] **F7** — Per-user monthly classification budget cap (migration 008, admin UI)
  - [ ] Unit: budget=10, already classified 10 this month → raises `BudgetExceededError`
  - [ ] Unit: budget=0 (unlimited) → no error regardless of usage
  - [ ] Unit: budget=100, used=90 → only 10 videos submitted in next batch
  - [ ] Unit: admin `PATCH /admin/users/{id}/budget` sets budget; non-admin gets 403
  - [ ] Integration: budget cap persists across requests; usage count resets at month boundary

- [ ] **F8** — Global classification cache (migration 009, `GlobalClassificationCache` table)
  - [ ] Unit: video ID in cache → `Classification` row created, no Anthropic batch call
  - [ ] Unit: video ID not in cache → added to Anthropic batch
  - [ ] Unit: after Anthropic classifies, `GlobalClassificationCache` row is written
  - [ ] Integration: scan user A → cache populated; scan user B with same channel → cache hits, no Anthropic batch submitted

- [ ] *(follow-up)* `UserChannelVideo` join table — fix cross-user channel dedup bug
