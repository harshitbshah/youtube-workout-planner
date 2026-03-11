"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { getMe } from "@/lib/api";

// ─── Section / layout primitives ────────────────────────────────────────────

const SECTIONS = [
  { id: "admin-console",   label: "Admin console" },
  { id: "managing-users",  label: "Managing users" },
  { id: "announcements",   label: "Announcements" },
  { id: "monitoring",      label: "Monitoring pipelines" },
  { id: "troubleshooting", label: "Troubleshooting" },
  { id: "railway-ops",     label: "Railway ops" },
  { id: "db-reference",    label: "DB reference" },
  { id: "env-vars",        label: "Env vars" },
  { id: "known-issues",    label: "Known issues" },
  { id: "optimizations",   label: "Optimizations" },
];

function Section({ id, title, children }: { id: string; title: string; children: React.ReactNode }) {
  return (
    <section id={id} className="scroll-mt-8 pt-10 first:pt-0">
      <h2 className="text-xl font-bold text-white mb-4 pb-3 border-b border-zinc-800">{title}</h2>
      <div className="space-y-4 text-zinc-400 text-sm leading-relaxed">{children}</div>
    </section>
  );
}

function H3({ children }: { children: React.ReactNode }) {
  return <h3 className="text-white font-semibold text-base mt-6 mb-2">{children}</h3>;
}

function Note({ children }: { children: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-zinc-700 bg-zinc-900 px-4 py-3 text-zinc-400 text-sm">
      {children}
    </div>
  );
}

function Warn({ children }: { children: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-amber-800 bg-amber-950/40 px-4 py-3 text-amber-300 text-sm">
      {children}
    </div>
  );
}

function Code({ children }: { children: React.ReactNode }) {
  return (
    <pre className="rounded-lg bg-zinc-900 border border-zinc-800 px-4 py-3 text-xs text-zinc-300 overflow-x-auto leading-relaxed">
      {children}
    </pre>
  );
}

function Table({ headers, rows }: { headers: string[]; rows: string[][] }) {
  return (
    <div className="overflow-x-auto rounded-lg border border-zinc-800">
      <table className="w-full text-sm">
        {headers.length > 0 && (
          <thead>
            <tr className="border-b border-zinc-700">
              {headers.map((h) => (
                <th key={h} className="px-4 py-2.5 text-left text-xs font-semibold text-zinc-400 uppercase tracking-wide">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
        )}
        <tbody>
          {rows.map((row, i) => (
            <tr key={i} className="border-b border-zinc-800 last:border-0">
              {row.map((cell, j) => (
                <td key={j} className={`px-4 py-2.5 align-top ${j === 0 ? "font-medium text-white whitespace-nowrap" : "text-zinc-400"}`}>
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ─── Page ────────────────────────────────────────────────────────────────────

export default function AdminGuidePage() {
  const router = useRouter();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    getMe()
      .then((me) => {
        if (!me.is_admin) { router.replace("/dashboard"); return; }
        setReady(true);
      })
      .catch(() => router.replace("/dashboard"));
  }, [router]);

  if (!ready) {
    return (
      <div className="min-h-screen bg-zinc-950 flex items-center justify-center">
        <div className="w-5 h-5 border-2 border-zinc-600 border-t-white rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-zinc-950 text-white">

      {/* Nav */}
      <nav className="flex items-center justify-between px-6 py-5 max-w-5xl mx-auto border-b border-zinc-800">
        <div className="flex items-center gap-4">
          <Link href="/admin" className="font-semibold text-white tracking-tight hover:text-zinc-300 transition">
            Admin
          </Link>
          <span className="text-zinc-700">/</span>
          <span className="text-zinc-400 text-sm">Guide</span>
        </div>
        <Link
          href="/admin"
          className="rounded-lg border border-zinc-700 px-4 py-2 text-sm text-zinc-300 hover:bg-zinc-800 transition"
        >
          ← Back to admin
        </Link>
      </nav>

      <div className="max-w-5xl mx-auto px-6 py-12 flex gap-12">

        {/* Sidebar */}
        <aside className="hidden lg:block w-52 shrink-0">
          <div className="sticky top-8">
            <p className="text-xs font-semibold text-zinc-500 uppercase tracking-widest mb-4">Contents</p>
            <nav className="space-y-1">
              {SECTIONS.map(({ id, label }) => (
                <a key={id} href={`#${id}`} className="block text-sm text-zinc-500 hover:text-zinc-200 py-1 transition">
                  {label}
                </a>
              ))}
            </nav>
          </div>
        </aside>

        {/* Content */}
        <main className="flex-1 min-w-0 space-y-2">

          <div className="mb-10">
            <h1 className="text-3xl font-bold text-white mb-2">Admin Guide</h1>
            <p className="text-zinc-400">
              Everything you need to run Plan My Workout in production — monitoring users,
              managing the pipeline, posting announcements, and fixing issues when they come up.
            </p>
          </div>

          {/* ── Admin console ─────────────────────────────────────────────── */}
          <Section id="admin-console" title="Admin console">
            <p>
              The admin console at <Link href="/admin" className="text-zinc-300 underline">/admin</Link> gives
              you a live view of the entire platform. It auto-refreshes every 30 seconds.
            </p>

            <H3>Stats cards</H3>
            <Table
              headers={["Card", "What it shows"]}
              rows={[
                ["Total users", "All registered accounts"],
                ["New (7 days)", "Accounts created in the last 7 days, with a 30-day sub-count"],
                ["YouTube connected", "Users with a valid YouTube OAuth token who can publish plans to a playlist"],
                ["Plans this week", "Users who have a generated plan for the current Mon–Sun week"],
                ["Total videos", "All videos scanned across every user's channels"],
                ["Classified", "Videos tagged by AI with workout type, body focus, and difficulty — shown as a percentage"],
                ["Unclassified", "Videos scanned but not yet sent to the classifier — clears on the next pipeline run"],
                ["Channels", "Total YouTube channels added across all users, with an average per user"],
                ["AI usage (7 days)", "Anthropic Batch API input + output tokens and estimated cost for the past week"],
                ["AI usage (all-time)", "Cumulative token usage and cost since the platform launched"],
              ]}
            />

            <H3>Trend charts</H3>
            <p>
              The four charts below the stat cards show daily time-series for the last 30 days:
            </p>
            <Table
              headers={["Chart", "What it shows"]}
              rows={[
                ["Signups", "New user registrations per day"],
                ["Active users", "Distinct users who made at least one API request per day"],
                ["AI cost", "Estimated Anthropic classification spend per day (USD)"],
                ["Scans", "Number of pipeline runs completed per day"],
              ]}
            />
            <Note>
              Charts use Haiku 4.5 Batch API pricing: $0.40 / 1M input tokens, $2.00 / 1M output tokens.
              Days with no activity appear as zero bars — not gaps.
            </Note>

            <H3>Active pipelines</H3>
            <p>
              Below the charts, the per-user table shows the current pipeline stage for each user.
              Stages update in real time as the pipeline progresses. A user stuck on{" "}
              <code className="text-zinc-300 bg-zinc-800 px-1 rounded">classifying</code> for more than
              30 minutes likely has a stale batch ID — see <a href="#troubleshooting" className="text-zinc-300 underline">Troubleshooting</a>.
            </p>
          </Section>

          {/* ── Managing users ────────────────────────────────────────────── */}
          <Section id="managing-users" title="Managing users">
            <p>
              The per-user table shows every registered account with key status information.
            </p>

            <H3>User table columns</H3>
            <Table
              headers={["Column", "What it shows"]}
              rows={[
                ["User", "Display name and email"],
                ["Last active", "When the user last made an API request (updates at most every 5 minutes)"],
                ["Channels", "Number of YouTube channels the user has added"],
                ["Videos", "Total videos scanned across their channels"],
                ["YouTube", "Whether they have a connected and valid YouTube OAuth token"],
                ["Last plan", "When their most recent plan was generated"],
                ["Pipeline", "Current pipeline stage — blank means idle"],
              ]}
            />

            <H3>Triggering a scan</H3>
            <p>
              Click the <strong className="text-white">↺ Scan</strong> button next to any user to
              immediately run the full pipeline for them: scan → classify → generate plan.
              This is the same as the user clicking "Regenerate" but works even if their pipeline
              is stuck or they haven't logged in.
            </p>
            <Note>
              If a user has no channels, the scan button returns an error — that's expected. Ask them
              to add channels first via their settings page.
            </Note>

            <H3>Deleting a user</H3>
            <p>
              Click <strong className="text-white">Delete</strong> to permanently remove a user and
              all their data: channels, videos, classifications, schedule, plan history, and credentials.
              This cannot be undone. You cannot delete your own account from the admin console
              (use <Link href="/settings" className="text-zinc-300 underline">/settings</Link> for that).
            </p>
            <Warn>
              Deleting a user does not revoke their YouTube OAuth token with Google. If needed,
              the token is revoked automatically when a user deletes their own account via settings.
            </Warn>
          </Section>

          {/* ── Announcements ─────────────────────────────────────────────── */}
          <Section id="announcements" title="Announcements">
            <p>
              Announcements appear as a dismissible banner at the top of every user's dashboard.
              Use them to communicate maintenance windows, new features, or known issues.
            </p>

            <H3>Creating an announcement</H3>
            <p>
              Type your message in the text area at the bottom of the admin console and click{" "}
              <strong className="text-white">Post announcement</strong>. The banner goes live
              immediately for all users — no deploy needed.
            </p>
            <Note>
              Only one announcement should be active at a time. If a previous one is still active,
              deactivate it before posting a new one — otherwise users see only the most recent one anyway.
            </Note>

            <H3>Deactivating vs deleting</H3>
            <Table
              headers={["Action", "What happens"]}
              rows={[
                ["Deactivate", "Hides the banner from users immediately. The announcement stays in the list for reference."],
                ["Delete", "Permanently removes the announcement from the database."],
              ]}
            />

            <H3>How users see it</H3>
            <p>
              The banner appears at the top of <code className="text-zinc-300 bg-zinc-800 px-1 rounded">/dashboard</code> for
              all logged-in users. Users can dismiss it for their session — it reappears on the next
              page load until the announcement is deactivated or deleted.
            </p>
          </Section>

          {/* ── Monitoring pipelines ─────────────────────────────────────── */}
          <Section id="monitoring" title="Monitoring pipelines">
            <p>
              The weekly pipeline runs automatically every <strong className="text-white">Sunday at 18:00 UTC</strong> for
              all users. Users can also trigger it manually from their dashboard. Here's what each stage means.
            </p>

            <H3>Pipeline stages</H3>
            <Table
              headers={["Stage", "What's happening"]}
              rows={[
                ["scanning", "Fetching new videos from each of the user's YouTube channels"],
                ["classifying", "Sending unclassified videos to Anthropic Batch API (Haiku) — this is the slowest stage"],
                ["generating", "Picking the best video per schedule slot and saving the weekly plan"],
                ["done", "Pipeline finished — plan is visible on the user's dashboard"],
                ["failed", "An unexpected error stopped the pipeline — check last_scan_error in the user table"],
              ]}
            />

            <H3>Pipeline error handling</H3>
            <p>
              When the pipeline fails, the error message is saved to the user record and shown in the
              admin user table. A successful pipeline run (triggered manually or on the next Sunday cron)
              clears the error automatically.
            </p>
            <p>
              To clear a stuck error: find the user in the table, click{" "}
              <strong className="text-white">↺ Scan</strong>. If the scan succeeds, the error clears.
              If it fails again, check Railway logs for that user's ID to diagnose the root cause.
            </p>

            <H3>How inactive channels are handled</H3>
            <p>
              During the automated Sunday cron, channels that haven't published a new video in over
              60 days are skipped to save YouTube API quota. User-triggered scans always scan all
              channels regardless. The date of the most recent video per channel is tracked
              in the database and visible via the{" "}
              <a href="#db-reference" className="text-zinc-300 underline">DB reference</a> queries below.
            </p>

            <H3>First-time channel scans</H3>
            <p>
              When a user adds a new channel, the first scan fetches up to 75 of the most recent videos
              to keep the initial pipeline fast. Subsequent scans are incremental with no cap.
            </p>
          </Section>

          {/* ── Troubleshooting ───────────────────────────────────────────── */}
          <Section id="troubleshooting" title="Troubleshooting">
            <Table
              headers={["Symptom", "Likely cause", "Fix"]}
              rows={[
                [
                  "User's pipeline is stuck on \"classifying\" forever",
                  "Anthropic batch timed out or server restarted mid-batch — stale batch ID in DB",
                  "Railway shell: UPDATE user_credentials SET classifier_batch_id = NULL WHERE user_id = '<id>'; then hit ↺ Scan from admin",
                ],
                [
                  "User has 0 videos after a scan",
                  "All videos filtered by pre-classification blocklist (non-workout titles), or YouTube API quota exhausted",
                  "Check Railway logs for that user's scan. If quota, wait 24h. If blocklist, user needs channels with clearer titles.",
                ],
                [
                  "User's plan is all rest days",
                  "Planner found no matching videos (library too small or schedule too restrictive)",
                  "Trigger ↺ Scan to get more videos. Check user's schedule settings in DB.",
                ],
                [
                  "\"Unclassified\" count keeps growing",
                  "New videos scanned faster than Anthropic batches can process, or batch cap (300/run) hit",
                  "Normal — clears on next Sunday scan. Or trigger ↺ Scan manually from admin.",
                ],
                [
                  "YouTube \"credentials invalid\" for a user",
                  "Google OAuth refresh token revoked (user changed password or revoked app access at myaccount.google.com)",
                  "User must re-authenticate: sign out → sign in again to re-grant YouTube access.",
                ],
                [
                  "Admin stats show 0 AI usage despite classifications",
                  "batch_usage_log table missing — migration not yet applied",
                  "Trigger a Railway redeploy — the Dockerfile runs alembic upgrade head automatically.",
                ],
                [
                  "Channel scan shows 0 new videos but channel is active",
                  "Channel's last video is >60 days old so the Sunday cron skipped it",
                  "Trigger a manual scan from the admin console — user-triggered scans bypass the inactive skip.",
                ],
                [
                  "User's error banner won't clear",
                  "Pipeline is failing on every run for this user",
                  "Check Railway logs for that user's ID. Fix root cause, then trigger ↺ Scan — success clears the error.",
                ],
              ]}
            />
          </Section>

          {/* ── Railway ops ──────────────────────────────────────────────── */}
          <Section id="railway-ops" title="Railway ops">
            <H3>Connecting to the Railway shell</H3>
            <Code>{`railway link          # link to project (one-time)
railway shell         # drop into a shell on the running container`}</Code>

            <H3>Running a migration manually</H3>
            <Code>{`# Migrations run automatically on redeploy via Dockerfile.
# To run manually in the Railway shell:
alembic upgrade head

# Check current migration version:
alembic current`}</Code>

            <H3>Triggering the weekly pipeline manually</H3>
            <Code>{`# In Railway shell:
python -c "
from api.scheduler import run_weekly_pipeline
run_weekly_pipeline()
"`}</Code>

            <H3>Triggering pipeline for a single user</H3>
            <Code>{`# In Railway shell:
python -c "
from api.scheduler import _weekly_pipeline_for_user
_weekly_pipeline_for_user('<user_id>')
"`}</Code>

            <H3>Clearing a stuck batch ID</H3>
            <Code>{`# In Railway psql shell:
UPDATE user_credentials
SET classifier_batch_id = NULL
WHERE user_id = '<user_id>';`}</Code>

            <H3>Updating env vars</H3>
            <p>
              All env vars are set in the Railway project dashboard under Variables. Changes take
              effect on the next deploy or restart. Key pairs that must stay in sync:
            </p>
            <Table
              headers={["Var", "Must match"]}
              rows={[
                ["FRONTEND_ORIGINS", "The Vercel deployment URL (comma-separated if multiple)"],
                ["GOOGLE_REDIRECT_URI", "The Railway callback URL — must also be registered in Google Cloud Console"],
                ["FRONTEND_URL", "Used in OAuth token handoff redirect"],
              ]}
            />
            <Warn>
              When renaming the Railway domain, update BOTH <code>FRONTEND_ORIGINS</code> and{" "}
              <code>GOOGLE_REDIRECT_URI</code>, AND register the new URI in Google Cloud Console.
              Missing either step will break OAuth for all users.
            </Warn>
          </Section>

          {/* ── DB reference ─────────────────────────────────────────────── */}
          <Section id="db-reference" title="DB reference">
            <H3>Migration history</H3>
            <Table
              headers={["Migration", "Adds"]}
              rows={[
                ["001", "Initial schema — users, channels, videos, classifications, schedules, program_history, user_credentials"],
                ["002", "user_credentials.credentials_valid + youtube_playlist_id"],
                ["003", "user_credentials.classifier_batch_id"],
                ["004", "users.last_active_at, batch_usage_log, announcements"],
                ["005", "scan_log, user_activity_log"],
                ["006", "channels.first_scan_done"],
                ["007", "channels.last_video_published_at"],
                ["008", "users.last_scan_error"],
              ]}
            />

            <H3>Useful queries</H3>
            <Code>{`-- All users + channel/video counts
SELECT u.email, COUNT(DISTINCT c.id) channels, COUNT(DISTINCT v.id) videos,
       u.last_active_at, u.last_scan_error
FROM users u
LEFT JOIN channels c ON c.user_id = u.id
LEFT JOIN videos v ON v.channel_id = c.id
GROUP BY u.id ORDER BY u.created_at DESC;

-- AI usage last 7 days
SELECT DATE(created_at) AS day,
       SUM(classified) AS classified,
       SUM(input_tokens) AS input_tok,
       SUM(output_tokens) AS output_tok,
       ROUND(SUM(input_tokens) * 0.00000025 + SUM(output_tokens) * 0.00000125, 4) AS est_cost_usd
FROM batch_usage_log
WHERE created_at > now() - interval '7 days'
GROUP BY day ORDER BY day DESC;

-- Videos not yet classified
SELECT c.name AS channel, COUNT(*) AS unclassified
FROM videos v
JOIN channels c ON c.id = v.channel_id
LEFT JOIN classifications cl ON cl.video_id = v.id
WHERE cl.video_id IS NULL AND v.duration_sec >= 180
GROUP BY c.name ORDER BY unclassified DESC;

-- Channels that would be skipped by the Sunday cron
SELECT name, last_video_published_at, added_at
FROM channels
WHERE last_video_published_at < now() - interval '60 days'
  AND added_at < now() - interval '30 days';

-- Users with a lingering scan error
SELECT id, email, last_scan_error
FROM users
WHERE last_scan_error IS NOT NULL;`}</Code>
          </Section>

          {/* ── Env vars ─────────────────────────────────────────────────── */}
          <Section id="env-vars" title="Env vars">
            <Table
              headers={["Var", "Example", "Notes"]}
              rows={[
                ["ANTHROPIC_API_KEY", "sk-ant-...", "Required — Haiku classifier"],
                ["YOUTUBE_API_KEY", "AIza...", "Required — channel scanning"],
                ["GOOGLE_CLIENT_ID", "xxx.apps.googleusercontent.com", "OAuth"],
                ["GOOGLE_CLIENT_SECRET", "GOCSPX-...", "OAuth"],
                ["GOOGLE_REDIRECT_URI", "https://planmyworkout-api.up.railway.app/auth/google/callback", "Must match Google Cloud Console"],
                ["FRONTEND_URL", "https://planmyworkout.vercel.app", "OAuth token handoff redirect target"],
                ["FRONTEND_ORIGINS", "https://planmyworkout.vercel.app", "CORS — comma-separated"],
                ["ENCRYPTION_KEY", "base64...", "Fernet key for YouTube refresh tokens at rest"],
                ["SECRET_KEY", "random-string", "Starlette session middleware signing"],
                ["ADMIN_EMAIL", "harshitspeaks@gmail.com", "Single admin — read at request time"],
                ["DATABASE_URL", "postgresql://...", "Managed by Railway — set automatically"],
                ["CLASSIFY_MAX_AGE_MONTHS", "18", "Videos older than this are skipped by the classifier (default: 18)"],
                ["FIRST_SCAN_LIMIT", "75", "Max videos fetched on a channel's first scan (default: 75)"],
              ]}
            />
          </Section>

          {/* ── Known issues ─────────────────────────────────────────────── */}
          <Section id="known-issues" title="Known issues">
            <Table
              headers={["Issue", "Impact", "Planned fix"]}
              rows={[
                [
                  "Cross-user channel dedup bug",
                  "If two users add the same YouTube channel, the second user's scan creates a PK conflict on videos.id — their channel effectively gets no videos",
                  "GlobalClassificationCache + UserChannelVideo join table (backlog)",
                ],
                [
                  "Error banner not shown on dashboard",
                  "users.last_scan_error is persisted and returned by GET /jobs/status but the frontend doesn't render it as a banner yet",
                  "Add error banner to dashboard — in backlog",
                ],
                [
                  "WebSockets not implemented",
                  "Dashboard polls GET /jobs/status every 5s — works fine at current scale but adds latency",
                  "Deferred until polling becomes a user complaint",
                ],
                [
                  "Per-user YouTube API quota",
                  "Shared API key supports ~14 concurrent weekly users (10,000 units / ~670 per user). Beyond that, scans fail silently",
                  "Per-user BYOK or YouTube key rotation (backlog)",
                ],
                [
                  "Monthly classification budget cap not implemented",
                  "Power users could trigger many manual scans, running up Anthropic costs",
                  "Monthly budget per user + admin override (backlog)",
                ],
              ]}
            />
          </Section>

          {/* ── Optimizations ────────────────────────────────────────── */}
          <Section id="optimizations" title="Optimizations">
            <p>
              Cost and performance optimizations applied across the codebase, organised by layer.
            </p>

            <H3>Backend optimizations (Phase A — AI cost reduction)</H3>
            <Table
              headers={["Optimization", "Where", "Detail"]}
              rows={[
                [
                  "max_tokens reduced 150 → 80",
                  "api/services/classifier.py",
                  "Each Anthropic Batch API request caps output at 80 tokens. The JSON classification response is ~50–70 tokens; 80 gives headroom without waste. Cuts per-video AI cost ~47%.",
                ],
                [
                  "18-month video cutoff",
                  "CLASSIFY_MAX_AGE_MONTHS env var",
                  "Videos older than 18 months are excluded from classification before the Anthropic batch is built. Configurable — set a lower value to reduce cost further.",
                ],
                [
                  "First-scan channel cap (75 videos)",
                  "channels.first_scan_done (migration 006)",
                  "The first scan of a new channel is capped at 75 of its most recent videos to keep the initial pipeline fast. Subsequent scans are uncapped and incremental. first_scan_done is set True after the first scan completes.",
                ],
                [
                  "Skip inactive channels",
                  "channels.last_video_published_at (migration 007)",
                  "Channels with no video published in 60+ days AND added 60+ days ago are skipped in the automated Sunday pipeline to save YouTube API quota. User-triggered scans (POST /jobs/scan) always scan all channels regardless.",
                ],
                [
                  "Graceful pipeline failures",
                  "users.last_scan_error (migration 008)",
                  "Pipeline exceptions are caught, stored on the user record, and returned by GET /jobs/status. The dashboard shows an error banner when set. The weekly pipeline continues for other users even when one fails. Cleared automatically on the next successful run.",
                ],
              ]}
            />

            <H3>Frontend optimizations (Phase B + cleanup)</H3>
            <Table
              headers={["Optimization", "Where", "Detail"]}
              rows={[
                [
                  "Shared constants",
                  "src/lib/utils.ts",
                  "DAY_LABELS and formatDuration() were previously duplicated across the dashboard, library, and onboarding pages. Extracted to a single shared module.",
                ],
                [
                  "Shared Badge component",
                  "src/components/Badge.tsx",
                  "Styled badge pill previously duplicated in dashboard and library pages. Extracted to a shared component used in both.",
                ],
                [
                  "Polling change detection",
                  "app/onboarding/page.tsx (step 7)",
                  "The scan progress tracker uses functional state updates (prev === next ? prev : next) to avoid unnecessary re-renders when the poll returns the same pipeline stage.",
                ],
                [
                  "Interval ref cleanup",
                  "app/onboarding/page.tsx (step 7)",
                  "A useRef tracks the polling interval, allowing it to be cleared immediately when the pipeline finishes — not waiting for the next effect cleanup cycle.",
                ],
                [
                  "Extracted search helper",
                  "components/ChannelManager.tsx",
                  "performSearch() deduplicates search logic shared between manual search-box submission and suggestion-chip clicks, removing a copy-paste branch.",
                ],
                [
                  "Extracted scan helper",
                  "app/onboarding/page.tsx",
                  "executeScan() deduplicates the triggerScan error-handling logic shared between the initial scan trigger and the retry path.",
                ],
              ]}
            />

            <Note>
              Phase A optimizations are in production on Railway. The frontend optimizations were
              introduced during Phase B and apply to the Next.js app served via Vercel.
            </Note>
          </Section>

        </main>
      </div>
    </div>
  );
}
