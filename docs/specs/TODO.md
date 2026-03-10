# Implementation TODO

Ordered by priority. Each item links to its spec.

---

## Phase A — AI Cost Reduction (features 1–4)
> Spec: [ai-cost-reduction.md](ai-cost-reduction.md)
> Do before first users arrive. All trivial–small effort.

- [ ] **F1** — Reduce `max_tokens` 150 → 80 in `classifier.py`
- [ ] **F2** — 18-month video cutoff (`CLASSIFY_MAX_AGE_MONTHS` env var)
- [ ] **F3** — First-scan channel cap (migration 006, `first_scan_done` column, 75-video limit)
- [ ] **F4** — Skip inactive channels (migration 007, `last_video_published_at` column)

---

## Phase B — Onboarding Redesign
> Spec: [onboarding-redesign.md](onboarding-redesign.md)
> Full rewrite of the onboarding wizard. No backend changes needed.

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
- [ ] Manual test: senior profile defaults to beginner/short schedule
- [ ] Manual test: athlete profile defaults to advanced/long schedule
- [ ] Manual test: step 7 auto-navigates after all stages complete

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
- [ ] Unit test: mock `resend.Emails.send`, assert subject + HTML content
- [ ] Manual test: trigger pipeline → verify email received in Gmail
- [ ] Manual test: toggle off in settings → re-trigger → no email sent

---

## Phase D — AI Cost Reduction (features 5–8)
> Spec: [ai-cost-reduction.md](ai-cost-reduction.md)
> Defer until traffic warrants. Feature 8 requires schema decision.

- [ ] **F5** — Adaptive payload trimming (`title_is_descriptive()` helper)
- [ ] **F6** — Rule-based title pre-classifier (`title_classify()`, saves 30–40% AI calls)
- [ ] **F7** — Per-user monthly classification budget cap (migration 008, admin UI)
- [ ] **F8** — Global classification cache (migration 009, `GlobalClassificationCache` table)
- [ ] *(follow-up)* `UserChannelVideo` join table — fix cross-user channel dedup bug
