# Feature Backlog

Running list of ideas captured during development. No priority order — just a place
to park things so they don't get lost in conversation history.

Add items here mid-session whenever something worth remembering surfaces.
Review before starting a new phase to see if anything belongs in scope.

---

## Legal / Compliance

- V0 launch: generate Privacy Policy + ToS via Termly/GetTerms, host at `/privacy` and `/terms`
- Add onboarding consent checkboxes: (1) ToS + Privacy Policy at account creation, (2) health disclaimer before first plan (one-time)
- Footer: YouTube API attribution links + "Not affiliated with YouTube, Google, or featured channels"
- Verify `DELETE /auth/me` fully purges YouTube OAuth tokens (Google API ToS requirement)
- Add "Curated by AI" badge on plan dashboard (FTC AI disclosure)
- Long-term: lawyer-reviewed docs before paid tier; GDPR cookie banner when analytics added; CCPA compliance at scale
- See `docs/legal.md` for full details

---

## Frontend / UX

- **Homepage redesign** — make the landing page more attractive/catchy for new visitors.
  Current homepage is functional but minimal. Ideas: better hero copywriting, social proof
  (screenshots or video demo), testimonials section once first users exist, animated
  "how it works" steps. Captured as pending task, not yet started.

- Light theme as default with a one-click toggle to dark mode. Currently the app
  is dark-only (hardcoded `zinc-950` backgrounds). Would need a theme context/provider,
  CSS variable-based colour tokens, and a toggle button (e.g. sun/moon icon in the
  dashboard header). Light theme should be the out-of-the-box experience for new users.

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

- Per-user classification cost cap — bound Anthropic spend per user per month.
  Not urgent while user count is small; revisit before opening to public.

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

- **Admin runbook panel** — add a collapsed `<details>` section at the bottom of `/admin`
  with quick answers to the most likely operational questions. Content to cover:

  | Symptom | Cause | Fix |
  |---|---|---|
  | User's pipeline is stuck on "classifying" forever | Anthropic batch timed out or server restarted mid-batch; stale `classifier_batch_id` in DB | Use Railway shell: `UPDATE user_credentials SET classifier_batch_id = NULL WHERE user_id = '<id>';` then hit ↺ Scan |
  | User has 0 videos after a scan | All videos filtered by pre-classification blocklist (non-workout titles), or YouTube API quota exhausted | Check Railway logs for that user's scan; if quota, wait 24h |
  | User's plan is all Rest days | Planner found no matching videos (library too small or schedule too restrictive) | Try ↺ Scan to get more videos; check user's schedule settings |
  | "Unclassified" count keeps growing | New videos scanned faster than Anthropic batches can process them, or batch cap (300/run) hit | Normal — will clear on next scheduled Sunday scan; or trigger ↺ Scan manually |
  | YouTube "credentials invalid" for a user | User's Google OAuth refresh token was revoked (changed Google password, or revoked app access at myaccount.google.com) | User must re-authenticate: sign out → sign in again to re-grant YouTube access |
  | Admin stats show 0 AI usage despite classifications | Migration 005 not yet applied (UserActivityLog / ScanLog tables missing) | Trigger a Railway redeploy — Dockerfile runs `alembic upgrade head` automatically |

  Implementation: inline `<details><summary>Runbook</summary>…</details>` at the bottom
  of the admin page. No separate route needed — keeps it contextual and zero maintenance.
  Build when first users are onboarded and real incidents arise to validate the content.

## Infrastructure / Ops

- Email notification when YouTube access is revoked — part of Phase 5 revoked access
  handling. User should get an email + in-app banner, not just a silent skip.

- Per-user YouTube API key support — required before scaling past ~14 concurrent weekly
  users (10,000 quota units / ~670 per user per week). See `docs/infra-research.md`.

- Structured error logging / alerting — currently all errors go to Railway stdout. Add
  Sentry (or similar) so runtime exceptions in background jobs (scan/classify/plan) surface
  without needing to manually inspect logs.

- Graceful scanner failure reporting — if scan/classify fails for a user, they currently
  see nothing. Consider storing a `last_scan_status` + `last_scan_error` on the user
  record so the dashboard can show a meaningful error banner.

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
