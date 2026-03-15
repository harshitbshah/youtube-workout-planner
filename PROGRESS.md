# Progress

## Status
Phases 1–5 complete + admin console + charts + guide page + mobile UX complete. Phase A complete. Phase B complete. Phase C complete. Phase D F5+F6 complete. Backlog items T1+T2+S1+M2 complete. Channel suggestions + onboarding UX complete. Channel fitness validation (migration 019) complete. Email notifications opt-in step in onboarding complete. Dark mode on all pages complete. Light mode button visibility fixed. Google sign-in color_scheme forwarding complete.
**376 backend + 164 frontend = 540 tests passing**.
Both Railway (backend) and Vercel (frontend) live and functional on `main`.
**Ready for first users** — Google OAuth fully verified ✅. YouTube scope approved by Google Trust & Safety (2026-03-15). No more "unverified app" warning for any user.

**Done this session (2026-03-15, checkpoint 2):**
- Notifications toggle in settings: ON-state thumb was `bg-zinc-900` on `bg-zinc-900` track — invisible in light mode. Fixed to `bg-white` ✅
- Google OAuth YouTube scope verification approved by Trust & Safety (2026-03-15) ✅ — app is fully verified, red warning gone for all users

**Done this session (2026-03-15, checkpoint):**
- Light mode button visibility fixed: all `bg-white text-zinc-900 hover:bg-zinc-100` action buttons changed to `bg-zinc-900 dark:bg-white text-white dark:text-zinc-900 hover:bg-zinc-700 dark:hover:bg-zinc-100` across dashboard, settings, onboarding, admin, guide, FeedbackWidget ✅
- Selected/active states (training days, category tabs) and progress bar fills updated to match ✅
- Investigated Google sign-in page theming — confirmed Google's OAuth2 endpoint ignores `color_scheme`; sign-in page follows OS/browser preference only, not controllable by the app ✅
- New test files: `frontend/src/lib/api.test.ts` (loginUrl), `frontend/src/app/page.test.tsx` (landing page sign-in links) ✅
- **540 total (376 backend + 164 frontend)** ✅

**Done this session (2026-03-14, checkpoint 2):**
- Email notifications opt-in/out step (step 6) added to onboarding wizard ✅
- Sublabel copy fixed: "Arrives every Sunday evening" (scheduler runs Sunday 18:00 UTC) ✅
- Channel fitness validation: `POST /channels` calls Claude Haiku (max_tokens=20) before any DB write; "no: label" response raises 422 with user-friendly message; "yes"/"unsure"/error fail open ✅
- Migration 019: `users.profile` + `users.goal` columns; written by `PUT /schedule` ✅
- `ChannelCreate` schema: `description` field added; stored on `Channel` for future cache hits ✅
- `api/services/channel_validator.py`: new service; 9 unit tests in `test_channel_validator.py` ✅
- 4 new unit tests + 4 new integration tests for channel validation ✅
- 404 Not Found page created (`app/not-found.tsx`) with proper dark mode support ✅
- `privacy/page.tsx` + `terms/page.tsx`: fixed from hardcoded `bg-zinc-950` to `bg-white dark:bg-zinc-950` with all text/link dark: variants ✅
- Onboarding: `cursor-pointer` added to all interactive buttons ✅
- Global `button { cursor: pointer }` rule in `globals.css` — covers all pages ✅
- Shared `LegalSection` component extracted from privacy + terms pages ✅
- **519 total (359 backend + 160 frontend)** ✅

**Done this session (2026-03-14, checkpoint):**
- Simplify cleanup: `_GENERAL_SUGGESTIONS` now references `_SUGGESTION_NAMES["adult"]` (was duplicated); `dict[Optional[str], ...]` → `dict[str, ...]`; single `httpx.AsyncClient` reused across suggestion loop (was new client per name); double `db.commit()` in upsert consolidated to one; `handleNextStep4` renamed to `handleBuildSchedule`; unused `buildCount` variable inlined ✅
- Onboarding steps 1–4: select-then-Next UX (OptionCard `selected` prop, `StepNav` component, explicit Next button) ✅
- Progress tracker: negative `done` values (batch-building phase) now display as `"preparing X / total"` instead of `"-X / total"` ✅
- Onboarding step 7: "Go to dashboard" escape hatch for long-running AI classify ✅
- **511 total (359 backend + 152 frontend)** ✅

**Done this session (2026-03-14, continued):**
- Channel suggestion card UI: replaced text chips with thumbnail card grid in both onboarding step 6 and settings ✅
- Backend `GET /channels/suggestions?profile=` endpoint with DB caching: YouTube API called at most once per unique suggestion channel across all users; subsequent requests serve from shared `channels` table ✅
- Migration 018: `channels.thumbnail_url` + `channels.description` columns ✅
- 3 channels capped per profile; adult list trimmed (Yoga with Adriene removed) ✅
- `ChannelManager` props updated: `suggestions?: ChannelSearchResult[]`, `suggestionsLoading?: boolean`; card grid with skeleton loading state ✅
- Onboarding: `SUGGESTIONS` constant removed from frontend; fetches from backend on step 6 mount ✅
- Settings: fetches general suggestions on mount; passes to ChannelManager ✅
- 11 new backend tests (6 unit + 1 integration + schema 018) ✅
- 3 new frontend tests (ChannelManager card UI, skeleton, one-click add); existing suggestion tests fully updated ✅
- **507 total (359 backend + 148 frontend)** ✅

**Done this session (2026-03-14):**
- Re-activation banner: dismissible banner on dashboard when plan.week_start is from a previous week; inline "Generate a fresh plan →" link ✅
- M2: Swap video inline from dashboard — "Swap video" button below each day card opens an inline picker with top 10 videos pre-filtered by workout type; "Show all types" clears filter; selecting a video calls PATCH /plan/{day} and updates card in place; Esc/Cancel closes ✅
- Frontend test coverage audit: identified gaps, wrote tests for FeedbackWidget, ScheduleEditor, SettingsPage, LibraryPage, DashboardPage ✅
- CLAUDE.md: frontend test rule now mandatory (alongside backend rule); skip list for static pages and trivial display components ✅
- **Frontend tests: 71 → 145 (+74)**; total: 352 backend + 145 frontend = 497 passing ✅

**Done this session (2026-03-13, part 6 — checkpoint):**
- Bug fix: delete channel silently swallowed errors — now shows error message + loading state ✅
- Bug fix: feedback modal cut off left side on mobile — fixed with `left-4 right-4` on small screens ✅
- Bug fix: feedback button SVG rendered as arrow on some mobile browsers — replaced with thumbs-up icon ✅
- Bug fix: cursor-pointer missing on feedback category buttons and channel remove (✕) button ✅
- Bug fix: channel delete was failing with FK constraint — `program_history.video_id` FK set to `ON DELETE SET NULL` (migration 016) ✅
- **Architecture refactor: shared channels** — channels are now global, `user_channels` join table links users to channels; deleting a channel removes only the user's link — videos stay in library permanently ✅
  - Migration 017: creates `user_channels`, populates from existing data, deduplicates by `youtube_channel_id`, drops `channels.user_id`
  - All queries updated: `channels.py`, `library.py`, `plan.py`, `jobs.py`, `planner.py`, `classifier.py`, `scheduler.py`, `admin.py`
  - All 29 test files updated — 423/423 tests passing
- DB schema note: migrations 016 + 017 will run on next Railway redeploy ✅

**Done this session (2026-03-13, part 5):**
- Replaced default Next.js favicon (white triangle) with 💪 emoji (Twemoji, 16×32×48px ICO) ✅
- Discussed "Get Started Free" vs "Sign In" UX — recommendation: add Google icon + rename to "Create free account", add "Already have an account? Sign in" below CTA (not yet implemented)

**Done this session (2026-03-13, part 4):**
- Bug fix: theme toggle hidden behind feedback pill — moved from `bottom-16` → `bottom-20` so it sits clearly above the feedback button ✅

**Done this session (2026-03-13, checkpoint):**
- Feedback widget: floating button on all post-login pages; modal with 3 categories; emails admin via Resend with reply_to set to user's email ✅
- `POST /feedback` backend endpoint (category validation, message trimming, 503 on email failure) ✅
- 13 unit + 5 integration tests for feedback ✅
- Light/dark theme system: system preference default, localStorage persistence, floating sun/moon toggle ✅
- ThemeProvider + ThemeToggle in layout.tsx (single mount, no per-page duplication) ✅
- Anti-flash inline `<script>` in layout.tsx — no FOUC on dark-system users ✅
- 9 new frontend tests for ThemeProvider + ThemeToggle ✅
- All 13 pages/components updated with dual-mode zinc/neutral Tailwind classes ✅
- Bug fixes: new-user redirect to /onboarding, mobile horizontal scroll, onboarding progress tracker stuck on "scanning" ✅
- Simplify cleanup: ThemeProvider merged effects, stale closure fix, `applyTheme` helper, `mockMatchMedia` test helper, `_FEEDBACK_ENV` constant, shared `make_mock_user` in `tests/api/helpers.py` ✅
- CLAUDE.md: testing workflow note (push before done), removed simplify from checkpoint ✅

**Done this session (2026-03-13, continued, part 3):**
- Phase C (weekly plan email) complete — code fully implemented, awaiting Resend account + `planmyworkout.app` domain verification to go live ✅
- `api/services/email.py` — `send_weekly_plan_email()`, Jinja2 template rendering, Resend SDK integration ✅
- `api/templates/weekly_plan_email.html` — table-based HTML email, inline CSS, workout type pills, recovery rows ✅
- `alembic/versions/015_add_email_notifications.py` — `users.email_notifications` boolean (default True) ✅
- `api/scheduler.py` — step 4 calls `send_weekly_plan_email` after plan generation; errors never break pipeline ✅
- `PATCH /auth/me/notifications` endpoint — toggle email preference; exposed in `GET /auth/me` ✅
- Settings page `#notifications` section — toggle with immediate save ✅
- 9 new unit tests in `tests/api/test_email.py` — all passing ✅
- Railway env vars needed: `RESEND_API_KEY`, `FROM_EMAIL=plan@planmyworkout.app`, `APP_URL=https://planmyworkout.app`

**Done this session (2026-03-13, continued, part 2):**
- Migrated frontend domain from `planmyworkout.vercel.app` → `planmyworkout.app` (Hostinger) ✅
- Updated Railway env vars: `FRONTEND_URL`, `FRONTEND_ORIGINS` ✅
- Updated Google Cloud Console OAuth authorized origins ✅
- Verified `planmyworkout.app` ownership via Google Search Console (DNS TXT record) ✅
- Re-submitted Google OAuth verification with updated homepage to Trust & Safety ✅
- Updated `docs/google-oauth-setup.md` with migration notes ✅

**Done this session (2026-03-13, continued):**
- Merged `origin/claude/exercise-plan-with-gifs-b1bRg` into `main` — brought in active-user gate, 3 new spec files (exercise-breakdown-with-gifs, channel-recommendations, ai-profile-enrichment-and-coach-chat), docs/specs/TODO.md expansion ✅
- Active-user gate (`api/scheduler.py`) — weekly cron skips users inactive >14 days; saves YouTube API quota + Anthropic credits ✅
- 9 new unit tests for active-user gate in `tests/api/test_scheduler.py` — boundary conditions, mixed users, error isolation, session cleanup ✅
- **3 new specs captured** (exercise breakdown with GIFs, channel recommendations R1/R2/R3, AI profile enrichment + coach chat O1/O2/O3) ✅

**Done this session (2026-03-13):**
- T1: Dashboard scan polling uses functional state updates — no re-renders when polled stage/progress is unchanged ✅
- T2: "Curated by AI" disclosure badge added above plan grid on dashboard (FTC compliance) ✅
- S1: Admin runbook panel — collapsible symptom/cause/fix table at bottom of `/admin` for common operational issues ✅
- All docs updated: PROGRESS.md, backlog.md, MEMORY.md ✅

**Done this session (2026-03-11, continued):**
- Phase D F5 (adaptive payload trimming) — descriptive titles skip transcript fetch + use 300-char description; ambiguous titles keep full 800-char + transcript ✅
- Phase D F6 (rule-based title pre-classifier) — `title_classify()` classifies HIIT/Strength/Cardio/Mobility titles with body focus + difficulty without AI call; estimated 30–40% fewer Anthropic batch submissions ✅
- 32 new unit tests in `tests/api/test_phase_d.py` — 316/316 backend tests passing ✅

**Done this session (2026-03-11):**
- Phase B (onboarding redesign) complete — 7-step wizard: life stage → goal → training days → session length → schedule preview → channels → live scan progress ✅
- `frontend/src/lib/scheduleTemplates.ts` — `buildSchedule()` generates ScheduleSlot[] from profile/goal/days/duration ✅
- `ChannelManager.tsx` updated with optional `suggestions` prop — curated channel suggestions shown per life stage/goal ✅
- Onboarding page fully rewritten as a 7-step wizard with auto-advance on selection, ScheduleEditor inline customise, and live scan progress polling ✅
- Frontend test suite added: Vitest + React Testing Library — 62 tests covering scheduleTemplates logic, ChannelManager, and onboarding page steps ✅
- Code cleanup: `DAY_LABELS` + `formatDuration()` extracted to `src/lib/utils.ts`, shared `Badge.tsx` component, polling change-detection fix, interval ref cleanup, `performSearch()` and `executeScan()` helpers extracted ✅
- Admin guide: "Optimizations" section added documenting all Phase A backend + Phase B frontend optimizations ✅
- Admin guide: 4 new reference sections added — Architecture (stack, auth, pipeline, design decisions), Testing (commands, philosophy, DB setup), Infrastructure (Railway gotchas table, CLI commands, migration triggers), Scaling & decisions (cost model, known limits, future pricing) ✅
- User guide (`/guide` page + `docs/user-guide.md`): Getting started section rewritten for 7-step wizard flow ✅
- CLAUDE.md: "Docs ↔ Admin guide relationship" convention added — docs/ is canonical, admin guide is operational summaries only ✅
- Checkpoint docs updated (PROGRESS.md, architecture.md, testing.md, backlog.md, CLAUDE.md, TODO.md) ✅

**Done this session (2026-03-10):**
- `feat/web-app` merged → `main`, Railway + Vercel switched to `main`, branch deleted ✅
- Admin page mobile horizontal scroll fixed ✅
- Privacy Policy + Terms of Service pages live at `/privacy` + `/terms` ✅
- Shared Footer with YouTube API attribution added to all pages ✅
- YouTube OAuth token revocation on account deletion (`DELETE /auth/me`) ✅
- App renamed "Plan My Workout" everywhere ✅
- Google Search Console domain verified ✅
- Google OAuth branding verified + published ✅
- Google sensitive scope (`youtube`) submitted for review ✅ (4–6 week wait)
- Phase A checkpoint docs updated (PROGRESS.md, architecture.md, MEMORY.md) ✅
- Admin guide page (`/admin/guide`) committed and deployed ✅
- Admin guide rewritten as operational reference (9 sections: admin console, managing users, announcements, monitoring, troubleshooting, railway ops, DB reference, env vars, known issues) ✅
- Footer updated with `isAdmin` prop — shows "Admin Guide" link beside "User Guide" on admin pages only ✅
- Admin page Guide link: styled as button, repositioned to bottom footer ✅

**Next:** Phase D F7+F8 (per-user budget cap + global classification cache) — deferred until real users.

## What's built

### Phase 1–3 (Backend)
FastAPI + PostgreSQL (Alembic), Google OAuth, Fernet encryption, channels/schedule/plan
routers, scanner/classifier/planner services, APScheduler weekly cron, scan endpoint.

### Phase 4 (Frontend) — complete
- Landing/marketing page (`/`) — hero, how it works, features, sign-up CTA
- Onboarding (`/onboarding`) — 7-step wizard: life stage → goal → training days → session length → schedule preview → channels → live scan progress
- Dashboard (`/dashboard`) — 7-day plan grid, regenerate, nav to library/settings
- Library browser (`/library`) — filter by workout type/body focus/difficulty/channel,
  assign video to plan day, pagination
- Settings (`/settings`) — edit display name, manage channels, edit schedule, delete account
- Shared components: `ChannelManager`, `ScheduleEditor` (reused in onboarding + settings)
- Backend: `PATCH /auth/me` (display name), `DELETE /auth/me` (account deletion)
- Bug fix: `GET /library` filters are case-insensitive (`func.lower`) — classifier stores
  mixed-case values ("HIIT", "Strength") but frontend sends lowercase

### Phase 5 (Playlist Publishing) — complete
- `POST /plan/publish` — publishes current plan to user's YouTube playlist
- Server-side OAuth: decrypts stored refresh token → exchanges for access token
- First publish creates a private playlist and stores its ID; subsequent runs reuse it
- Auto-publish in APScheduler cron (Sundays) if credentials are valid
- Revoked access: `google.auth.exceptions.RefreshError` or YouTube 401/403 sets
  `credentials_valid=False` in DB and returns HTTP 403 to client
- `GET /auth/me` now returns `youtube_connected` + `credentials_valid`
- Dashboard: Publish button enabled when connected + valid credentials + plan exists
- Dashboard: amber banner when YouTube access revoked
- Dashboard: green success banner with playlist link after publish
- DB migration 002: `credentials_valid` (bool, default true) + `youtube_playlist_id` columns

### Post-deploy fixes (2026-03-09) — complete
See "Deployment Bug Log" below for full diagnosis.

**Infrastructure:**
- `api/database.py` + `alembic/env.py`: rewrite `postgres://` → `postgresql://` at runtime
- `requirements.txt`: pinned all unpinned deps
- `Dockerfile`: added `exec` before `uvicorn` so it runs as PID 1
- Railway dashboard: proxy port corrected from 8000 → 8080

**Auth — cross-domain cookie replacement:**
- Replaced `SameSite=lax` session cookies with URL token handoff
- OAuth callback now redirects to `{FRONTEND_URL}?token=<signed_token>` (itsdangerous)
- Frontend extracts token from URL, stores in `localStorage`, sends as `Authorization: Bearer`
- `api/dependencies.py` checks Bearer token first, falls back to session cookie
- Tokens expire after 30 days; signed with `SESSION_SECRET_KEY`

**UX — scan progress:**
- `POST /jobs/scan` router prefix was missing (`/scan` → `/jobs/scan`) — endpoint was
  silently 404-ing on every "Generate plan" click since it was added
- `api/routers/jobs.py` fixed: `router = APIRouter(prefix="/jobs", ...)`
- Dashboard "Generate plan" (no plan yet) now calls `POST /jobs/scan` (full background
  pipeline) showing a scanning banner + polls `GET /plan/upcoming` every 15s
- Dashboard "Regenerate" (plan exists) calls `POST /plan/generate` (fast, synchronous)
  showing an inline "Generating…" banner while in flight
- Onboarding → redirects to `/dashboard?scanning=1` after triggering scan; dashboard
  reads this flag on mount to start scanning state without an extra API call

**Tests:**
- 5 new unit tests for `POST /jobs/scan` in `tests/api/test_jobs.py`
- 5 new integration tests in `tests/integration/test_jobs_api.py` (new file)
- Updated all tests using old per-channel route (`/channels/{id}/scan` → `/jobs/channels/{id}/scan`)
- `CLAUDE.md`: mandatory unit + integration test rule added; must pass before every commit

### Pipeline reliability + UX (2026-03-09) — complete

**Bug fixes:**
- `_run_full_pipeline` skipped classification when `total_new == 0` (incremental scan) —
  previously failed classifications never retried. Fix: always run `classify_for_user`
  (it's a no-op if nothing to classify)
- Plan with all null days caused UX loop: "Regenerate" button called `POST /plan/generate`
  (no scan) → still empty. Fix: detect all-null plan → show "Rescan channels" button instead

**Pipeline improvements:**
- `GET /jobs/status` endpoint — returns current stage + classify progress (total/done)
- In-memory `_pipeline_status` dict updated at each stage (scanning/classifying/generating/done/failed)
- `classify_for_user` accepts `on_progress` callback — called during transcript fetch phase
  (every 10 videos, negative done = still building) and during Anthropic batch polling
- Batch size capped at 300 videos per run — defers remainder to next scan, keeps first-run
  time manageable (~5 min transcript fetch vs 20+ min for 1000+ videos)
- Resumable batches: `classifier_batch_id` persisted in `user_credentials` (migration 003).
  On restart, resumes polling or retrieves results directly — no resubmission, no double billing

**Scanner pre-classification filters** (reduce Anthropic API cost):
- Title keyword blocklist: skips meal/recipe/vlog/q&a/podcast/unboxing/giveaway/transformation
  etc before fetching video details (no extra API calls)
- Livestream/premiere filter: skips `liveBroadcastContent=live/upcoming` (free, in playlist API)
- Upper duration cap: skips videos > 2 hours (livestreams/podcasts)
- Existing: < 3 min (Shorts) + `#shorts` hashtag filters preserved

**Dashboard UX:**
- Live scanning banner with stage-specific messages (scanning/classifying/generating/failed)
- Progress bar + `X / N done` count during classification batch polling
- Building phase shows `Preparing batch — fetching transcripts (X / N)` with progress bar
- Dashboard auto-detects running pipeline on mount (handles externally triggered scans)
- Polling interval reduced from 15s → 5s during scanning

**Tests:** 227/227 (was 216). New tests for: GET /jobs/status, duration cap, classify cap,
on_progress callback, batch resume logic, batch ID cleared on completion.

## Next
- Complete E2E testing (Groups 1–7 in `docs/testing.md`)
- Publish Google OAuth app (removes "unverified" warning for basic scopes)
- Once E2E passes: share with first users

### Phase A — AI cost reduction (2026-03-10) — complete

**F1 — Reduce max_tokens:**
- `classifier.py` `max_tokens` reduced 150 → 80 (JSON response is ~50–70 tokens; 80 gives headroom without waste)

**F2 — 18-month video cutoff:**
- `CLASSIFY_MAX_AGE_MONTHS` env var (default 18); classifier skips videos older than this threshold before building the Anthropic batch

**F3 — First-scan channel cap (migration 006):**
- `channels.first_scan_done` boolean column added
- Scanner limits new channels to 75 videos on first scan; subsequent scans are uncapped (incremental)
- `first_scan_done` set to `True` after first scan completes

**F4 — Skip inactive channels (migration 007):**
- `channels.last_video_published_at` datetime column added
- Weekly cron skips channels where `last_video_published_at` > 60 days after `added_at` and last publish > 60 days ago
- User-triggered scans (`POST /jobs/scan`) always scan all channels regardless
- `last_video_published_at` updated to the most recent video date after each scan

**Graceful scanner failure (migration 008):**
- `users.last_scan_error` text column added
- Pipeline exception sets `last_scan_error` on the user record; successful run clears it to `None`
- `GET /jobs/status` includes `error` field; dashboard shows error banner when set

**Tests:** 284/284 (+36 new tests covering all F1–F4 cases + graceful failure paths)

### Phase D — AI Cost Reduction F5+F6 (2026-03-11) — complete

**F5 — Adaptive payload trimming:**
- `_title_is_descriptive(title)` — regex detects fitness keywords (duration numbers, body parts, workout type words)
- Descriptive titles: skip `_fetch_transcript_intro` + cap description to 300 chars before building Anthropic request
- Ambiguous titles: unchanged — full 800-char description + transcript
- Estimated savings: ~20–30% input tokens on obvious-title videos

**F6 — Rule-based title pre-classifier:**
- `title_classify(title, duration_sec)` — regex rules for type (HIIT/Strength/Cardio/Mobility), body focus (upper/lower/full/core), difficulty (beginner/intermediate/advanced), warmup/cooldown flags
- Returns classification dict if type is matched with confidence; `None` for ambiguous titles
- Applied to all unclassified videos before capping and batching — classified by rules skip AI entirely
- Estimated savings: ~30–40% fewer Anthropic batch submissions
- F6 runs before F5: a video classified by rules never reaches the payload trimming step

**Tests:** 316/316 backend (+32 in `tests/api/test_phase_d.py`)

**Deferred (F7+F8):**
- F7 (per-user monthly budget cap) — activate when heavy manual scanners become a cost risk
- F8 (global classification cache) — activate at 10+ users sharing popular channels

### Phase B — Onboarding redesign (2026-03-11) — complete

**7-step onboarding wizard:**
- Step 1 — Life stage cards (4 options: student, working adult, senior, athlete); auto-advance on click
- Step 2 — Goal cards (varies by life stage, 3–4 options); auto-advance on click
- Step 3 — Training days toggle (2–6 days); auto-advance on selection
- Step 4 — Session length cards (4 options); auto-advance on click
- Step 5 — Schedule preview: `buildSchedule()` generates a ScheduleSlot[] from profile/goal/days/duration; inline "Customise" expands ScheduleEditor without leaving the step; changes persist
- Step 6 — Add channels: ChannelManager with curated channel suggestions filtered by life stage/goal; minimum-1-channel gate on Continue
- Step 7 — Live scan progress: polls `GET /jobs/status` every 2s, progress bar advances through scanning/classifying/generating stages, auto-navigates to `/dashboard` on `done`

**New files:**
- `frontend/src/lib/scheduleTemplates.ts` — `buildSchedule()` + per-profile/goal templates
- `frontend/src/test/setup.ts` — Vitest + jest-dom test setup

**Updated files:**
- `frontend/src/app/onboarding/page.tsx` — fully rewritten
- `frontend/src/components/ChannelManager.tsx` — optional `suggestions` prop added
- `frontend/src/lib/utils.ts` — `DAY_LABELS` + `formatDuration()` extracted (was duplicated)
- `frontend/src/components/Badge.tsx` — shared badge pill extracted (was duplicated)

**Frontend test suite (Vitest + React Testing Library):**
- 62 tests covering `scheduleTemplates.ts` logic, `ChannelManager` component, and onboarding page steps
- Run: `cd frontend && npm run test:run`

**Code quality cleanup:**
- `DAY_LABELS` and `formatDuration()` extracted to `src/lib/utils.ts`; removed duplication from dashboard, library, onboarding
- Shared `Badge.tsx` component; removed duplication from dashboard and library
- Onboarding polling uses functional state updates to avoid re-renders on identical stage
- Interval ref cleanup: polling cleared immediately on pipeline finish
- `performSearch()` helper deduplicates search logic in ChannelManager
- `executeScan()` helper deduplicates triggerScan error handling in onboarding

### Admin charts + scan/activity tracking (2026-03-10) — complete

**New DB tables (migration 005):**
- `scan_log` — one row per pipeline run: `started_at`, `completed_at`, `status` (running/done/failed), `videos_scanned`
- `user_activity_log` — one row per 5-min active window per user (powers "active users/day" chart)

**Backend:**
- `_run_full_pipeline` creates a `ScanLog` on start and marks it done/failed on finish
- `get_current_user` now also inserts a `UserActivityLog` row when updating `last_active_at`
- `GET /admin/charts?days=30` — 4 daily time series, zero-filled: signups, active users, AI cost (USD), scans

**Frontend:**
- Recharts installed; `MiniChart` component (responsive BarChart, dark theme, auto tick spacing)
- Admin console: "Trends — last 30 days" 2×2 grid (signups/indigo, active users/cyan, AI cost/purple, scans/green)

**Tests:** 248/248 (+8 chart tests: shape, custom days, per-series data, non-admin 403)

**Docs:**
- `backlog.md`: admin runbook panel idea captured with full symptom/cause/fix table
- `backlog.md`: branch merge next steps documented (6-step checklist)

**Pending ops:**
- Trigger Railway redeploy → migration 005 runs automatically
- Set `ADMIN_EMAIL=harshitspeaks@gmail.com` on Railway

### Admin console + guide page + mobile UX (2026-03-10) — complete

**Mobile responsive:**
- Dashboard header now `flex-col sm:flex-row` with `flex-wrap gap-2` on button group
- Dashboard plan grid: `grid-cols-1 sm:grid-cols-2 lg:grid-cols-4`
- Library grid: `grid-cols-1 sm:grid-cols-2 lg:grid-cols-4`

**Railway domain rename:**
- Backend renamed to `planmyworkout-api.up.railway.app` (was `youtube-workout-planner-production`)
- Updated `NEXT_PUBLIC_API_URL` on Vercel and all docs
- **Important:** `GOOGLE_REDIRECT_URI` env var on Railway must also be updated on any domain rename
  (was `https://planmyworkout-api.up.railway.app/auth/google/callback`)

**User guide page:**
- New `/guide` frontend page with 7 sections: Getting started, Weekly plan, Library,
  Settings, How the plan is built, Publish to YouTube, FAQ
- Sticky sidebar nav on desktop; mobile-friendly single column
- Linked from homepage nav ("Guide") and footer ("User Guide")

**Admin console:**
- New `GET /admin/stats` — aggregate stats (users, library, AI usage) + per-user table
  (last_active_at, channels, videos, YouTube status, last plan, pipeline stage)
- New `DELETE /admin/users/{user_id}` — delete any user; blocks self-deletion
- New `POST /admin/users/{user_id}/scan` — trigger scan for any user
- New `GET/POST/DELETE /admin/announcements`, `PATCH /admin/announcements/{id}/deactivate`
- New `GET /announcements/active` (public, any auth'd user) — active announcement or null
- Admin gating: `ADMIN_EMAIL` env var checked at request time (not import time)
- Dashboard shows admin nav link when `user.is_admin` is true
- Dashboard shows announcement banner (dismissible) when active announcement exists

**DB migrations (004):**
- `users.last_active_at` (datetime, nullable) — updated on every authenticated request (5-min throttle)
- `batch_usage_log` table — records token usage per Anthropic batch (input, output, per-user)
- `announcements` table — admin-created site-wide messages (id, message, is_active, created_at)

**Token usage tracking:**
- `api/services/classifier.py` now extracts input/output tokens from Anthropic batch results
- Records `BatchUsageLog` rows after each classify run
- Admin `/admin/stats` aggregates 7d + all-time token usage with cost estimate ($0.40/$2.00 per 1M)

**Tooltip component:**
- New `frontend/src/components/Tooltip.tsx` — CSS-only tooltip using Tailwind `group/tip`
- Subtle styling: `text-[11px]`, `max-w-[220px]`, `delay-300`, `bg-zinc-900 border-zinc-700/60`
- Used on admin console stat cards, column headers, action buttons
- Removed from dashboard (self-explanatory controls; native `title` on disabled Publish button)

**Tests:** 248/248 (+21 new admin tests in `tests/api/test_admin.py`)
- Stats shape, user counts, AI usage aggregation, 403 for non-admin, delete user,
  cannot delete self, retry scan (no channels → 400, with channels → 202),
  CRUD for announcements, active announcement visibility, timezone-aware 7d filter

### Vercel rename + URL cleanup (2026-03-09) — complete
- Renamed Vercel project to `planmyworkout` → live at `https://planmyworkout.vercel.app`
- Updated `FRONTEND_URL` on Railway to match
- Updated `FRONTEND_ORIGINS` on Railway to `https://planmyworkout.vercel.app` (CORS fix — old domain was blocking all API calls post-rename)
- Updated all docs and memory with new URL
- Kept UI title as "Workout Planner" (doesn't need to match URL)

### E2E bug fixes (2026-03-09) — complete

**Bug fixes:**
- Dashboard polling stopped when stale plan existed (`if (!scanning || plan) return` short-circuit).
  Fix: poll based on pipeline stage only — stop when stage is `done`/`failed`/`null`.
- Planner returned all Rest days — `NOT IN` subquery included NULL `video_id` rows from Rest days,
  making condition always false in SQL. Fix: added `video_id.is_not(None)` filter.
- Publisher crashed with 404 on newly created playlist — YouTube API has propagation delay.
  Fix: skip `clear_playlist` for new playlists (they're empty anyway).
- Classifier crashed saving results for videos deleted after batch submission.
  Fix: check video exists in DB before inserting classification.
- Page title still showed "Create Next App" — layout.tsx change was never committed.
  Fix: committed and pushed.

**Cleanup:**
- `scripts/cleanup_false_positives.py` — one-off script to remove pre-filter false positives from DB.
  Deleted 93 HASfit videos (recipes, vlogs, reviews, giveaways) from production. 1,076 remain.
- Cleared stale `program_history` entries (14 all-null rows from broken planner runs).
- Cleared stale `youtube_playlist_id` from user_credentials (pointing to deleted playlist).

**Docs:**
- Updated all docs: `testing.md` (227 tests), `architecture.md` (schema, scanner filters,
  batch cap, resumable batches, dashboard UX), `CLAUDE.md` (GET /jobs/status route),
  `backlog.md` (5s polling), `user-guide.md` (scan stages, non-workout filters).

## Deployment Status
- **Railway (backend):** ✅ Live at `https://planmyworkout-api.up.railway.app`
  - Health check: `{"status":"ok"}`
  - OAuth redirect working (`/auth/google` → Google consent screen)
  - All env vars set and verified via `railway variables`
  - Railway CLI installed (`npm install -g @railway/cli`) and linked to project `endearing-abundance`
- **Vercel (frontend):** ✅ Live at `https://planmyworkout.app` (custom domain, Hostinger DNS)
  - Branch: `main`, root directory: `frontend`
  - `NEXT_PUBLIC_API_URL` set to `https://planmyworkout-api.up.railway.app`

## Deployment Bug Log

### Bug 1 — Railway 502 on all endpoints (root cause: wrong proxy port)
**Symptom:** `/health` returned 502 from external internet; internal health checks returned 200.
**Root cause:** Railway proxy routing to port 8000; app bound to `PORT=8080` (Railway-injected).
Internal probes (`100.64.x.x`) bypass the public proxy — misleading green health check.
**Fix:** Railway dashboard → Settings → Networking → changed proxy port 8000 → 8080.

### Bug 2 — Post-OAuth redirect lands on homepage (SameSite=lax)
**Root cause:** `SameSite=lax` blocks cross-origin fetch. Session cookie set on Railway domain
never reached `GET /auth/me` from Vercel fetch calls.
**Attempted fix:** `SameSite=none; Secure` — worked briefly, then broke in Chrome (third-party
cookie deprecation, 2024).
**Final fix:** Dropped cookies entirely for cross-domain auth. OAuth callback redirects to
`{FRONTEND_URL}?token=<signed_token>`. Frontend stores in `localStorage` and sends as
`Authorization: Bearer`. No cookies needed across domains.

### Bug 3 — POST /jobs/scan was 404 (missing router prefix)
**Symptom:** "Generate plan" and "Scan channels" clicks silently failed; error state showed
nothing because the scan ran in a background context where errors weren't surfaced.
**Root cause:** `router = APIRouter(tags=["jobs"])` had no prefix. Endpoint was registered
at `/scan`, not `/jobs/scan`. The frontend always called `/jobs/scan`.
**Fix:** `router = APIRouter(prefix="/jobs", tags=["jobs"])`.

## Future API Ideas
- `PATCH /plan/{day}` with null `video_id` to mark a day as rest for that week only
  (currently only supports swapping to another video — only worth adding with explicit UI)
- Cross-user channel dedup: shared `channels` table + `user_channels` join to avoid
  scanning the same YouTube channel N times. Documented in `docs/scaling.md`.
