# Backlog

Running list of ideas and deferred features. Append during sessions; review before starting a new phase.

---

## Deferred - Auth

- **Rolling token refresh**: when backend sees a token with < 7 days remaining, issue a fresh 30-day token in an `X-Refresh-Token` response header; frontend stores it via `setToken`. Prevents silent hard-logout for active users. Not urgent at 30-day expiry.

---

## Deferred - AI cost optimizations

- **F7 - Per-user monthly budget cap**: activate when heavy manual scanners become a cost risk. Reject `POST /jobs/scan` with 429 once user exceeds N Anthropic calls/month.
- **F8 - Global classification cache**: when 10+ users share popular channels, the same video should not be classified twice. Share `classifications` rows across users (already partially true with shared channels architecture). Activate at scale.

---

## Deferred - Homepage

- **M2 (A/B variants)**: if traffic warrants it, test alternative headlines or hero layouts. Use Vercel's built-in split testing or a feature flag.

---

## Deferred - AI features

- **O1 - Freeform profile enrichment**: allow users to type free text ("I have bad knees", "training for a marathon") which gets summarised and stored. Used as extra context in channel fitness validation and future plan generation.
- **O2 - Coach chat**: in-app chat that answers questions about the weekly plan using the user's stored profile + schedule as context.
- **O3 - Exercise breakdown with GIFs**: for each video in the plan, show a segment breakdown with animated GIFs and muscle diagrams (requires a separate exercise DB or AI-generated content).

---

## Deferred - Channel recommendations

- **R1 - AI-powered recommendations**: given user profile + goal, recommend channels not yet in their library using Claude.
- **R2 - Collaborative filtering**: "users like you also follow..." based on shared subscription patterns.
- **R3 - Channel health score**: surface channels that are inactive or posting mostly non-workout content.

---

## Active ideas (not yet scheduled)

- **S2 - Completed workout tracking**: let users mark a day's video as "done" - track streaks and completion rates.
- **S3 - BYOK (Bring Your Own Key)**: let power users supply their own Anthropic API key to bypass the platform cost.
- **Admin runbook panel**: collapsible symptom/cause/fix table at `/admin` for common operational issues (e.g. blank plans, stale scans, OAuth revocations). Spec captured in session 2026-03-13.
- **Schedule → workout_type coupling in onboarding**: currently ScheduleEditor enforces valid body_focus per workout_type, but the initial `buildSchedule()` templates could also be validated against the channel library to surface gaps earlier (before the user hits an empty plan day).
