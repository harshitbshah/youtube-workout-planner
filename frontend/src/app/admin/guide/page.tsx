"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { getMe } from "@/lib/api";

// ─── Section / layout primitives ────────────────────────────────────────────

const SECTIONS = [
  { id: "architecture",   label: "Architecture overview" },
  { id: "phase-a",        label: "Phase A — AI cost" },
  { id: "troubleshooting",label: "Troubleshooting runbook" },
  { id: "railway-ops",    label: "Railway ops" },
  { id: "db-reference",   label: "DB quick reference" },
  { id: "env-vars",       label: "Env vars reference" },
  { id: "known-issues",   label: "Known issues / debt" },
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

function Checklist({ items }: { items: string[] }) {
  return (
    <ul className="space-y-1.5">
      {items.map((item, i) => (
        <li key={i} className="flex gap-2 text-sm text-zinc-400">
          <span className="mt-0.5 shrink-0 w-4 h-4 rounded border border-zinc-600 flex items-center justify-center text-zinc-600">
            <svg className="w-2.5 h-2.5" fill="none" viewBox="0 0 10 10">
              <path d="M2 5l2.5 2.5L8 3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </span>
          <span>{item}</span>
        </li>
      ))}
    </ul>
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
              Operational reference for running Plan My Workout in production. Everything here requires
              Railway or DB access — this page is not visible to regular users.
            </p>
          </div>

          {/* ── Architecture overview ─────────────────────────────────────── */}
          <Section id="architecture" title="Architecture overview">
            <p>
              Plan My Workout is a FastAPI backend + Next.js frontend. The backend runs on Railway,
              the frontend on Vercel. They communicate over HTTPS via a Bearer token stored in
              the user's localStorage.
            </p>

            <H3>Pipeline stages (per user, per week)</H3>
            <Table
              headers={["Stage", "What happens", "Triggered by"]}
              rows={[
                ["scanning", "YouTube playlistItems API fetched for each channel", "POST /jobs/scan · Sunday cron"],
                ["classifying", "Unclassified videos sent to Anthropic Batch API (Haiku)", "After scan, or POST /jobs/classify"],
                ["generating", "Planner picks best video per schedule slot", "After classify, or POST /plan/generate"],
                ["done", "Plan visible on dashboard", "—"],
                ["failed", "Outer exception in pipeline — last_scan_error set on user", "Unexpected error"],
              ]}
            />

            <H3>Cron schedule</H3>
            <p>
              APScheduler runs <code className="text-zinc-300 bg-zinc-800 px-1 rounded">run_weekly_pipeline()</code> every{" "}
              <strong className="text-white">Sunday at 18:00 UTC</strong> for all users. Defined in{" "}
              <code className="text-zinc-300 bg-zinc-800 px-1 rounded">api/scheduler.py</code>.
            </p>

            <H3>Auth flow</H3>
            <p>
              Google OAuth → callback redirects to{" "}
              <code className="text-zinc-300 bg-zinc-800 px-1 rounded">{"{FRONTEND_URL}"}?token={"<signed>"}</code> →
              stored in localStorage → sent as <code className="text-zinc-300 bg-zinc-800 px-1 rounded">Authorization: Bearer</code> on every API call.
              Sessions are stateless — no server-side session storage.
            </p>

            <H3>Key env vars (Railway)</H3>
            <p>See <a href="#env-vars" className="text-zinc-300 underline">Env vars reference</a> for the full list.</p>
          </Section>

          {/* ── Phase A ───────────────────────────────────────────────────── */}
          <Section id="phase-a" title="Phase A — AI cost reduction">
            <p>
              Phase A ships four cost-saving features to the classifier and scanner. All are live
              after migrations 006–008 run on Railway. Below is what each feature does and how to
              verify it in production.
            </p>

            <H3>F1 — max_tokens 150 → 80</H3>
            <p>
              Each Anthropic batch request now uses <code className="text-zinc-300 bg-zinc-800 px-1 rounded">max_tokens=80</code>.
              The actual JSON response is ~50–70 tokens so this wastes nothing.
            </p>
            <p className="font-medium text-zinc-300">Verify:</p>
            <Code>{`SELECT ROUND(AVG(output_tokens::float / NULLIF(classified, 0)), 1) AS avg_tokens_per_video
FROM batch_usage_log
WHERE created_at > now() - interval '7 days';
-- Expect: ≤ 80`}</Code>

            <H3>F2 — 18-month video cutoff</H3>
            <p>
              Videos with <code className="text-zinc-300 bg-zinc-800 px-1 rounded">published_at</code> older than 18 months
              are excluded from classification batches. Videos with NULL published_at are always included.
              Controlled by <code className="text-zinc-300 bg-zinc-800 px-1 rounded">CLASSIFY_MAX_AGE_MONTHS</code> env var (default: 18).
            </p>
            <p className="font-medium text-zinc-300">Verify:</p>
            <Code>{`-- No old videos should be unclassified (they're intentionally skipped)
SELECT COUNT(*) FROM videos
WHERE published_at < now() - interval '18 months'
  AND id NOT IN (SELECT video_id FROM classifications);
-- Expect: 0 (or a small number if they were already unclassified before Phase A)`}</Code>

            <H3>F3 — First-scan channel cap (75 videos)</H3>
            <p>
              When a channel is added for the first time (<code className="text-zinc-300 bg-zinc-800 px-1 rounded">first_scan_done=false</code>),
              only the 75 most recent videos are fetched. After the first scan, the flag is set to{" "}
              <code className="text-zinc-300 bg-zinc-800 px-1 rounded">true</code> and subsequent incremental scans have no cap.
            </p>
            <p className="font-medium text-zinc-300">Verify:</p>
            <Code>{`-- All existing channels should have first_scan_done=true
SELECT name, first_scan_done, COUNT(v.id) AS video_count
FROM channels c
LEFT JOIN videos v ON v.channel_id = c.id
GROUP BY c.id, c.name, c.first_scan_done
ORDER BY c.added_at DESC;`}</Code>
            <p className="font-medium text-zinc-300">Manual E2E:</p>
            <Checklist items={[
              "Add a brand-new channel, trigger scan → confirm first_scan_done=true in DB and video_count ≤ 75",
              "Trigger a second scan on the same channel → confirm video_count grows beyond 75 (incremental, no cap)",
            ]} />

            <H3>F4 — Skip inactive channels in cron</H3>
            <p>
              Channels with no new videos in the last 60 days are skipped during the automated
              Sunday cron to save YouTube API quota. User-triggered scans (<code className="text-zinc-300 bg-zinc-800 px-1 rounded">POST /jobs/scan</code>)
              always scan everything. The most recent video date is tracked in{" "}
              <code className="text-zinc-300 bg-zinc-800 px-1 rounded">channels.last_video_published_at</code>.
            </p>
            <p className="font-medium text-zinc-300">Verify:</p>
            <Code>{`-- See each channel's last video date and whether it would be skipped
SELECT name,
       last_video_published_at,
       added_at,
       CASE
         WHEN last_video_published_at IS NULL THEN 'never set (not skipped)'
         WHEN last_video_published_at < now() - interval '60 days'
          AND added_at < now() - interval '30 days' THEN 'would be skipped'
         ELSE 'active'
       END AS cron_status
FROM channels
ORDER BY last_video_published_at ASC NULLS FIRST;`}</Code>
            <p className="font-medium text-zinc-300">Manual E2E:</p>
            <Checklist items={[
              "Set last_video_published_at = now() - interval '90 days' on a channel, then trigger the cron (Railway shell: python -c \"from api.scheduler import run_weekly_pipeline; run_weekly_pipeline()\") — confirm that channel's scan is skipped in logs",
              "Confirm a user-triggered POST /jobs/scan still scans the same channel",
              "Confirm last_video_published_at is populated after a normal scan",
            ]} />

            <H3>Graceful pipeline failure</H3>
            <p>
              When the pipeline crashes unexpectedly, the error message is now persisted to{" "}
              <code className="text-zinc-300 bg-zinc-800 px-1 rounded">users.last_scan_error</code> and
              surfaced in <code className="text-zinc-300 bg-zinc-800 px-1 rounded">GET /jobs/status</code> as an{" "}
              <code className="text-zinc-300 bg-zinc-800 px-1 rounded">error</code> field. The dashboard should show
              this as an error banner (frontend work pending — Phase B scope).
              Cleared automatically on the next successful run.
            </p>
            <p className="font-medium text-zinc-300">Verify:</p>
            <Code>{`-- Check for any users with a lingering scan error
SELECT id, email, last_scan_error
FROM users
WHERE last_scan_error IS NOT NULL;`}</Code>
            <Warn>
              If a user is stuck with a non-null <code>last_scan_error</code>, trigger a manual scan
              from the admin console — a successful run will clear it automatically.
            </Warn>
          </Section>

          {/* ── Troubleshooting runbook ───────────────────────────────────── */}
          <Section id="troubleshooting" title="Troubleshooting runbook">
            <Table
              headers={["Symptom", "Likely cause", "Fix"]}
              rows={[
                [
                  "User's pipeline is stuck on \"classifying\" forever",
                  "Anthropic batch timed out or server restarted mid-batch — stale classifier_batch_id in DB",
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
                  "Migration 005 not yet applied (batch_usage_log / scan_log tables missing)",
                  "Trigger a Railway redeploy — Dockerfile runs alembic upgrade head automatically.",
                ],
                [
                  "Channel scan shows 0 new videos but channel is active",
                  "Channel's last_video_published_at is > 60 days ago and cron skipped it (F4)",
                  "Trigger a manual scan from the admin console — user-triggered scans bypass the inactive skip.",
                ],
                [
                  "User's last_scan_error is set and not clearing",
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

          {/* ── DB quick reference ────────────────────────────────────────── */}
          <Section id="db-reference" title="DB quick reference">
            <H3>Migration history</H3>
            <Table
              headers={["Migration", "Adds"]}
              rows={[
                ["001", "Initial schema — users, channels, videos, classifications, schedules, program_history, user_credentials"],
                ["002", "user_credentials.credentials_valid"],
                ["003", "user_credentials.classifier_batch_id"],
                ["004", "users.last_active_at, batch_usage_log, announcements"],
                ["005", "scan_log, user_activity_log"],
                ["006", "channels.first_scan_done (Phase A — F3)"],
                ["007", "channels.last_video_published_at (Phase A — F4)"],
                ["008", "users.last_scan_error (Phase A — graceful failure)"],
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

-- Videos not classified (potential backlog)
SELECT c.name AS channel, COUNT(*) AS unclassified
FROM videos v
JOIN channels c ON c.id = v.channel_id
LEFT JOIN classifications cl ON cl.video_id = v.id
WHERE cl.video_id IS NULL AND v.duration_sec >= 180
GROUP BY c.name ORDER BY unclassified DESC;

-- Channels that would be skipped by F4 cron
SELECT name, last_video_published_at, added_at
FROM channels
WHERE last_video_published_at < now() - interval '60 days'
  AND added_at < now() - interval '30 days';`}</Code>
          </Section>

          {/* ── Env vars ─────────────────────────────────────────────────── */}
          <Section id="env-vars" title="Env vars reference">
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
                ["CLASSIFY_MAX_AGE_MONTHS", "18", "Phase A F2 — videos older than this are skipped (default: 18)"],
                ["FIRST_SCAN_LIMIT", "75", "Phase A F3 — max videos on a channel's first scan (default: 75)"],
              ]}
            />
          </Section>

          {/* ── Known issues ─────────────────────────────────────────────── */}
          <Section id="known-issues" title="Known issues / debt">
            <Table
              headers={["Issue", "Impact", "Planned fix"]}
              rows={[
                [
                  "Cross-user channel dedup bug",
                  "If two users add the same YouTube channel, the second user's scan creates a PK conflict on videos.id — their channel effectively gets no videos",
                  "Phase D — F8: GlobalClassificationCache + UserChannelVideo join table",
                ],
                [
                  "Graceful failure error banner not shown on dashboard",
                  "users.last_scan_error is persisted and returned by GET /jobs/status but the frontend doesn't render it yet",
                  "Phase B scope — add error banner to dashboard alongside the scanning banner",
                ],
                [
                  "WebSockets not implemented",
                  "Dashboard polls GET /jobs/status every 5s — works fine at current scale but adds latency",
                  "Deferred until polling becomes a user complaint",
                ],
                [
                  "Per-user YouTube API quota",
                  "Shared API key supports ~14 concurrent weekly users (10,000 units / ~670 per user). Beyond that, scans fail silently",
                  "Per-user BYOK (user_credentials.anthropic_key field exists) or YouTube key rotation",
                ],
                [
                  "Monthly classification budget cap not implemented",
                  "Power users could trigger many manual scans, running up Anthropic costs",
                  "Phase D — F7: monthly_classify_budget on User + admin override",
                ],
              ]}
            />
          </Section>

        </main>
      </div>
    </div>
  );
}
