# Feature Backlog

Running list of ideas captured during development. No priority order — just a place
to park things so they don't get lost in conversation history.

Add items here mid-session whenever something worth remembering surfaces.
Review before starting a new phase to see if anything belongs in scope.

---

## Frontend / UX

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

## Infrastructure / Ops

- Email notification when YouTube access is revoked — part of Phase 5 revoked access
  handling. User should get an email + in-app banner, not just a silent skip.

- Per-user YouTube API key support — required before scaling past ~14 concurrent weekly
  users (10,000 quota units / ~670 per user per week). See `docs/infra-research.md`.

- Deploy to Railway (API + DB) + Vercel (frontend) — not started. Do after Phase 5.

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
