# Feature Backlog

Running list of ideas captured during development. No priority order — just a place
to park things so they don't get lost in conversation history.

Add items here mid-session whenever something worth remembering surfaces.
Review before starting a new phase to see if anything belongs in scope.

---

## Legal / Compliance

- V0 launch: Privacy Policy + ToS written manually, live at `/privacy` and `/terms` ✅
- Health disclaimer onboarding checkbox — defer to pre-paid-tier (covered in ToS for now)
- Footer: YouTube API attribution links + "Not affiliated with YouTube, Google, or featured channels"
- Verify `DELETE /auth/me` fully purges YouTube OAuth tokens (Google API ToS requirement)
- ~~Add "Curated by AI" badge on plan dashboard (FTC AI disclosure)~~ ✅ Done (2026-03-13) — subtle `✦ Curated by AI` label right-aligned above the plan grid.
- Long-term: lawyer-reviewed docs before paid tier; GDPR cookie banner when analytics added; CCPA compliance at scale
- See `docs/legal.md` for full details

---

## Frontend / UX

- **Homepage redesign** — make the landing page more attractive/catchy for new visitors.
  Current homepage is functional but minimal. Ideas: better hero copywriting, social proof
  (screenshots or video demo), testimonials section once first users exist, animated
  "how it works" steps. Captured as pending task, not yet started.

- ~~Light/dark theme system~~ ✅ Done (2026-03-13) — system preference default, localStorage persistence, floating sun/moon ThemeToggle button on all pages (in layout.tsx). Anti-FOUC inline script. All pages updated with dual-mode zinc/neutral Tailwind classes.

- `PATCH /plan/{day}` with null `video_id` to skip a day for that week only (mark as
  rest without swapping). Needs an explicit "Skip this day" button on the dashboard
  day card — not worth building without the UI.

- Completed workout tracking — tap a day card to mark it done. `program_history.completed`
  column already exists in the DB schema, just needs UI + API support.

- Welcome back screen for returning users showing last week's completion rate before
  showing the new plan.

- Swap video from dashboard directly — click a day card to open a mini library picker
  (filtered to that day's workout type) without navigating to the full library page.

---

## Backend / API

- Cross-user channel dedup — shared `channels` table + `user_channels` join table so
  the same YouTube channel isn't scanned N times for N users. Pre-scale work.
  Documented in `docs/scaling.md`.
  → **Covered by** `docs/specs/ai-cost-reduction.md` Feature 8 (global cache + UserChannelVideo join table).

- Per-user classification cost cap — bound Anthropic spend per user per month.
  Not urgent while user count is small; revisit before opening to public.
  → **Covered by** `docs/specs/ai-cost-reduction.md` Feature 7.

- BYOK (bring your own Anthropic key) — `user_credentials.anthropic_key` field already
  exists in the schema. Add a settings UI field + validation + fallback to platform key.

- `GET /plan/history` — return past weeks' plans so users can look back. Useful once
  the completed tracking UI exists.

---

## Real-time / Performance

- Replace 5s polling for scan job status with WebSockets — FastAPI supports WebSockets
  natively. Currently the dashboard polls `GET /jobs/status` every 5s; a WebSocket
  connection would push status updates instantly. Low priority while user count is small
  and polling works fine; revisit if users complain about scan UX latency.
  Decision: defer until after E2E testing + first users, since polling is not broken
  and WebSockets add meaningful complexity (backend endpoint, connection manager,
  frontend reconnect logic, new test surface).

---

## Launch Prep

- ~~Rename Vercel project~~ — renamed to `planmyworkout` → `planmyworkout.vercel.app`.
  Update `FRONTEND_URL` on Railway to `https://planmyworkout.vercel.app`.
- Publish Google OAuth app (Google Cloud Console → OAuth consent screen → Publish App)
  — removes "unverified" warning for basic scopes, no review needed.
- Full Google verification for `youtube.force-ssl` scope — required before opening
  to public. Needs: Privacy Policy, ToS, homepage, Search Console verification, demo video.
  Submit early (4–6 week review). See `docs/google-oauth-setup.md`.
- Custom domain (~$10–20/yr via Cloudflare Registrar) — defer until name decided and
  going public.

## Admin / Ops

- ~~**Admin runbook panel**~~ ✅ Done (2026-03-13) — collapsible `<details>` section at the bottom of `/admin` with 6-row symptom/cause/fix table (stuck pipeline, 0 videos, all-Rest plan, growing unclassified, revoked credentials, missing migration).

## Infrastructure / Ops

- Email notification when YouTube access is revoked — part of Phase 5 revoked access
  handling. User should get an email + in-app banner, not just a silent skip.
  → **Fits into Phase C** (Resend already wired up for weekly plan email). Add as a
  second `send_*` function in `api/services/email.py`.

- Per-user YouTube API key support — required before scaling past ~14 concurrent weekly
  users (10,000 quota units / ~670 per user per week). See `docs/infra-research.md`.

- Structured error logging / alerting — currently all errors go to Railway stdout. Add
  Sentry (or similar) so runtime exceptions in background jobs (scan/classify/plan) surface
  without needing to manually inspect logs.

- Graceful scanner failure reporting — if scan/classify fails for a user, they currently
  see nothing. Consider storing a `last_scan_status` + `last_scan_error` on the user
  record so the dashboard can show a meaningful error banner.
  → **Fits into Phase A** (scan pipeline work). Small addition alongside F3/F4.

---

## Testing

- **Playwright E2E tests for full onboarding flow** — deferred. The 7-step wizard involves
  multi-step interactions, schedule preview, and live polling that would benefit from a
  browser-level test. Vitest unit tests are sufficient for now; add Playwright when the
  onboarding flow stabilises and E2E coverage becomes a priority.

- ~~**Dashboard polling change-detection**~~ ✅ Done (2026-03-13) — `setPipelineStage` and `setClassifyProgress` now use functional updates; no re-render when polled value is unchanged.

---

## Ideas / Someday

- Adaptive periodization — auto-manage build / peak / deload blocks based on recent
  workout history. Requires completed tracking data over several weeks.

- Preference learning — rate workouts after completing them; scoring adapts over time
  to surface videos you tend to finish vs skip.

- Natural language rescheduling — "swap Thursday to a rest day this week" via a
  simple text input.

- Telegram / WhatsApp bot interface — weekly plan delivered as a message, reply to
  swap or skip a day.

---

## Re-activation flow (surfaced 2026-03-11)

When an inactive user (skipped by the cron for 2+ weeks) comes back, they land on the
dashboard with a stale plan — potentially weeks old — and no new plan. Nothing currently
handles this gracefully.

**The problem:** the scheduler only runs for users active within 14 days. A returning
user gets no fresh plan automatically; they'd need to manually hit "Regenerate" with no
prompting to do so.

**Proposed fix (deferred — implement when re-activation becomes a real pattern):**

On dashboard load, check if `plan.week_start < current_week_start`. If so, show a
dismissible banner:

> "Welcome back! Your last plan was from [date]. Want us to generate a fresh one?"
> [Generate now]

The "Generate now" button calls `POST /plan/generate` and refreshes the dashboard. No
new backend logic needed — just a frontend check on the `week_start` field already
returned by `GET /plan/upcoming`.

**Stale plan detection:** `plan.week_start < get_upcoming_monday()` (or current ISO week
comparison). Already available in frontend state.
