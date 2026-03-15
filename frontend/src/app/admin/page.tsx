"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip as ReTooltip,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";
import { getMe, getAdminCharts, adminResetOnboarding, type ChartsResponse } from "@/lib/api";
import { Tooltip } from "@/components/Tooltip";
import { Footer } from "@/components/Footer";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

function authHeaders() {
  const token = typeof window !== "undefined" ? localStorage.getItem("auth_token") ?? "" : "";
  return { "Content-Type": "application/json", Authorization: `Bearer ${token}` };
}

async function adminFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    credentials: "include",
    ...init,
    headers: { ...authHeaders(), ...(init?.headers as Record<string, string>) },
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw Object.assign(new Error(err.detail ?? "API error"), { status: res.status });
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

// ─── Types ─────────────────────────────────────────────────────────────────

type UsagePeriod = {
  batches: number;
  videos_classified: number;
  input_tokens: number;
  output_tokens: number;
  est_cost_usd: number;
};

type AdminStats = {
  users: { total: number; new_7d: number; new_30d: number; youtube_connected: number };
  library: { total_videos: number; classified: number; unclassified: number; classification_pct: number };
  channels: { total: number; avg_per_user: number };
  plans: { users_with_plan_this_week: number };
  pipelines: { active_count: number; active: { user_id: string; stage: string }[] };
  ai_usage: { last_7d: UsagePeriod; all_time: UsagePeriod };
  user_rows: UserRow[];
};

type UserRow = {
  id: string;
  email: string;
  display_name: string | null;
  created_at: string | null;
  last_active_at: string | null;
  channels: number;
  videos: number;
  youtube_connected: boolean;
  last_plan: string | null;
  pipeline_stage: string | null;
};

type Announcement = { id: number; message: string; is_active: boolean; created_at: string };

// ─── Sub-components ─────────────────────────────────────────────────────────

function StatCard({ label, value, sub, tooltip }: { label: string; value: string | number; sub?: string; tooltip?: string }) {
  return (
    <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900 p-5">
      <div className="flex items-center gap-1.5 mb-2">
        <p className="text-xs font-semibold text-zinc-500 uppercase tracking-widest">{label}</p>
        {tooltip && (
          <Tooltip text={tooltip} position="top">
            <span className="text-zinc-500 dark:text-zinc-600 hover:text-zinc-600 dark:hover:text-zinc-400 cursor-default text-xs leading-none">ⓘ</span>
          </Tooltip>
        )}
      </div>
      <p className="text-3xl font-bold text-zinc-900 dark:text-white">{value}</p>
      {sub && <p className="text-xs text-zinc-500 mt-1">{sub}</p>}
    </div>
  );
}

function StagePill({ stage }: { stage: string | null }) {
  if (!stage) return <span className="text-zinc-500 dark:text-zinc-600 text-xs">-</span>;
  const colours: Record<string, string> = {
    scanning: "bg-blue-900/40 text-blue-400 border-blue-800",
    classifying: "bg-purple-900/40 text-purple-400 border-purple-800",
    generating: "bg-amber-900/40 text-amber-400 border-amber-800",
    done: "bg-green-900/40 text-green-400 border-green-800",
    failed: "bg-red-900/40 text-red-400 border-red-800",
  };
  return (
    <span className={`rounded-full border px-2 py-0.5 text-xs capitalize ${colours[stage] ?? "bg-zinc-100 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-400 border-zinc-200 dark:border-zinc-700"}`}>
      {stage}
    </span>
  );
}

function formatDate(iso: string | null) {
  if (!iso) return "-";
  return new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
}

function formatRelative(iso: string | null) {
  if (!iso) return "-";
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60_000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}

function fmtAxisDate(iso: string) {
  const d = new Date(iso + "T12:00:00Z");
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

type MiniChartProps = {
  data: Record<string, number | string>[];
  dataKey: string;
  color: string;
  label: string;
  valueFormatter?: (v: number) => string;
};

function MiniChart({ data, dataKey, color, label, valueFormatter }: MiniChartProps) {
  const fmt = valueFormatter ?? ((v: number) => String(v));
  // Show a tick every ~7 days to keep x-axis readable
  const tickInterval = Math.max(1, Math.floor(data.length / 5));
  return (
    <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900 p-4">
      <p className="text-xs font-semibold text-zinc-500 uppercase tracking-widest mb-4">{label}</p>
      <ResponsiveContainer width="100%" height={160}>
        <BarChart data={data} barCategoryGap="30%">
          <CartesianGrid vertical={false} stroke="#27272a" />
          <XAxis
            dataKey="date"
            tickFormatter={fmtAxisDate}
            interval={tickInterval}
            tick={{ fill: "#71717a", fontSize: 10 }}
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            tick={{ fill: "#71717a", fontSize: 10 }}
            axisLine={false}
            tickLine={false}
            width={36}
            tickFormatter={fmt}
          />
          <ReTooltip
            formatter={(v) => [fmt(Number(v)), label]}
            labelFormatter={(l) => fmtAxisDate(String(l))}
            contentStyle={{ background: "#18181b", border: "1px solid #3f3f46", borderRadius: 8, fontSize: 12, color: "#e4e4e7" }}
            cursor={{ fill: "#ffffff08" }}
          />
          <Bar dataKey={dataKey} fill={color} radius={[3, 3, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function MetricRow({ label, value, tooltip }: { label: string; value: React.ReactNode; tooltip: string }) {
  return (
    <>
      <span className="text-zinc-500 flex items-center gap-1">
        {label}
        <Tooltip text={tooltip}>
          <span className="text-zinc-500 dark:text-zinc-600 hover:text-zinc-600 dark:hover:text-zinc-400 cursor-default text-xs">ⓘ</span>
        </Tooltip>
      </span>
      <span className="text-zinc-900 dark:text-white font-medium">{value}</span>
    </>
  );
}

function UsageBlock({ label, data }: { label: string; data: UsagePeriod }) {
  return (
    <div className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900 p-4 space-y-2">
      <p className="text-xs font-semibold text-zinc-500 uppercase tracking-widest">{label}</p>
      <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
        <MetricRow label="Batches" value={data.batches} tooltip="Number of Anthropic Batch API calls made in this period" />
        <MetricRow label="Videos classified" value={data.videos_classified.toLocaleString()} tooltip="Total videos successfully tagged with workout type, body focus, and difficulty" />
        <MetricRow label="Input tokens" value={data.input_tokens.toLocaleString()} tooltip="Tokens sent to Claude - includes video title, description, tags, and transcript" />
        <MetricRow label="Output tokens" value={data.output_tokens.toLocaleString()} tooltip="Tokens returned by Claude - short JSON classification responses" />
        <MetricRow label="Est. cost" value={`$${data.est_cost_usd.toFixed(4)}`} tooltip="Estimated cost using Batch API pricing: $0.40/MTok input, $2.00/MTok output (50% off standard rates)" />
      </div>
    </div>
  );
}

// ─── Main page ───────────────────────────────────────────────────────────────

export default function AdminPage() {
  const router = useRouter();
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [charts, setCharts] = useState<ChartsResponse | null>(null);
  const [announcements, setAnnouncements] = useState<Announcement[]>([]);
  const [newMsg, setNewMsg] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);
  const [deletingUser, setDeletingUser] = useState<string | null>(null);
  const [retryingUser, setRetryingUser] = useState<string | null>(null);
  const [resettingUser, setResettingUser] = useState<string | null>(null);

  async function fetchStats() {
    const data = await adminFetch<AdminStats>("/admin/stats");
    setStats(data);
    setLastRefresh(new Date());
  }

  async function fetchCharts() {
    const data = await getAdminCharts(30);
    setCharts(data);
  }

  async function fetchAnnouncements() {
    const data = await adminFetch<Announcement[]>("/admin/announcements");
    setAnnouncements(data);
  }

  useEffect(() => {
    getMe()
      .catch(() => { router.replace("/"); return Promise.reject(); })
      .then(() => Promise.all([fetchStats(), fetchAnnouncements(), fetchCharts()]))
      .catch((e: unknown) => {
        if ((e as { status?: number })?.status === 403) { router.replace("/dashboard"); return; }
        if (e) setError("Could not load admin stats.");
      })
      .finally(() => setLoading(false));
  }, [router]);

  // Auto-refresh every 30s
  useEffect(() => {
    const id = setInterval(() => { fetchStats().catch(() => {}); fetchCharts().catch(() => {}); }, 30_000);
    return () => clearInterval(id);
  }, []);

  async function handleDeleteUser(userId: string, email: string) {
    if (!confirm(`Delete user ${email}? This is permanent.`)) return;
    setDeletingUser(userId);
    try {
      await adminFetch(`/admin/users/${userId}`, { method: "DELETE" });
      await fetchStats();
    } catch {
      alert("Failed to delete user.");
    } finally {
      setDeletingUser(null);
    }
  }

  async function handleRetryScan(userId: string, email: string) {
    if (!confirm(`Trigger a fresh scan for ${email}?`)) return;
    setRetryingUser(userId);
    try {
      await adminFetch(`/admin/users/${userId}/scan`, { method: "POST" });
      await fetchStats();
    } catch {
      alert("Failed to trigger scan.");
    } finally {
      setRetryingUser(null);
    }
  }

  async function handleResetOnboarding(userId: string, email: string) {
    if (!confirm(`Reset onboarding for ${email}? This removes all their channel subscriptions and schedule. They will go through onboarding again on next login.`)) return;
    setResettingUser(userId);
    try {
      await adminResetOnboarding(userId);
      await fetchStats();
    } catch {
      alert("Failed to reset onboarding.");
    } finally {
      setResettingUser(null);
    }
  }

  async function handleCreateAnnouncement(e: React.FormEvent) {
    e.preventDefault();
    if (!newMsg.trim()) return;
    try {
      await adminFetch("/admin/announcements", { method: "POST", body: JSON.stringify({ message: newMsg.trim() }) });
      setNewMsg("");
      await fetchAnnouncements();
    } catch {
      alert("Failed to create announcement.");
    }
  }

  async function handleDeleteAnnouncement(id: number) {
    try {
      await adminFetch(`/admin/announcements/${id}`, { method: "DELETE" });
      await fetchAnnouncements();
    } catch {
      alert("Failed to delete announcement.");
    }
  }

  async function handleDeactivateAnnouncement(id: number) {
    try {
      await adminFetch(`/admin/announcements/${id}/deactivate`, { method: "PATCH" });
      await fetchAnnouncements();
    } catch {
      alert("Failed to deactivate announcement.");
    }
  }

  if (loading) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-white dark:bg-zinc-950">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-zinc-300 border-t-zinc-900 dark:border-zinc-600 dark:border-t-white" />
      </main>
    );
  }

  if (error) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-white dark:bg-zinc-950 text-red-400 text-sm">
        {error}
      </main>
    );
  }

  if (!stats) return null;

  return (
    <main className="min-h-screen bg-white dark:bg-zinc-950 px-4 py-8">
      <div className="max-w-6xl mx-auto space-y-10 overflow-x-hidden">

        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <h1 className="text-2xl font-bold text-zinc-900 dark:text-white">Admin</h1>
            {lastRefresh && (
              <p className="text-xs text-zinc-500 dark:text-zinc-600">
                Updated {lastRefresh.toLocaleTimeString()} · auto-refreshes every 30s
              </p>
            )}
          </div>
          <Link href="/dashboard" className="text-sm text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300 transition">
            ← Dashboard
          </Link>
        </div>

        {/* Users */}
        <section>
          <h2 className="text-xs font-semibold text-zinc-500 uppercase tracking-widest mb-3">Users</h2>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <StatCard label="Total users" value={stats.users.total} tooltip="All registered accounts" />
            <StatCard label="New (7 days)" value={stats.users.new_7d} sub={`${stats.users.new_30d} in last 30 days`} tooltip="Accounts created in the last 7 days" />
            <StatCard label="YouTube connected" value={stats.users.youtube_connected} sub={`of ${stats.users.total} users`} tooltip="Users with a valid YouTube OAuth token - they can publish plans to a YouTube playlist" />
            <StatCard label="Plans this week" value={stats.plans.users_with_plan_this_week} sub={`of ${stats.users.total} users`} tooltip="Distinct users who have a plan generated for the current week (Mon–Sun)" />
          </div>
        </section>

        {/* Library */}
        <section>
          <h2 className="text-xs font-semibold text-zinc-500 uppercase tracking-widest mb-3">Library</h2>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <StatCard label="Total videos" value={stats.library.total_videos.toLocaleString()} tooltip="All videos scanned across every user's channels" />
            <StatCard label="Classified" value={`${stats.library.classification_pct}%`} sub={`${stats.library.classified.toLocaleString()} videos`} tooltip="Videos analysed by AI and tagged with workout type, body focus, and difficulty" />
            <StatCard label="Unclassified" value={stats.library.unclassified.toLocaleString()} tooltip="Videos scanned but not yet classified - will be processed on the next pipeline run" />
            <StatCard label="Channels" value={stats.channels.total} sub={`avg ${stats.channels.avg_per_user} per user`} tooltip="Total YouTube channels added across all users" />
          </div>
        </section>

        {/* AI usage */}
        <section>
          <h2 className="text-xs font-semibold text-zinc-500 uppercase tracking-widest mb-3">AI Usage (Haiku 4.5 Batch)</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <UsageBlock label="Last 7 days" data={stats.ai_usage.last_7d} />
            <UsageBlock label="All time" data={stats.ai_usage.all_time} />
          </div>
          <p className="text-xs text-zinc-500 dark:text-zinc-600 mt-2">Cost estimate uses Batch API pricing: $0.40/MTok input · $2.00/MTok output</p>
        </section>

        {/* Charts */}
        {charts && (
          <section>
            <h2 className="text-xs font-semibold text-zinc-500 uppercase tracking-widest mb-3">
              Trends - last 30 days
            </h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <MiniChart
                data={charts.signups}
                dataKey="count"
                color="#6366f1"
                label="New signups"
              />
              <MiniChart
                data={charts.active_users}
                dataKey="count"
                color="#22d3ee"
                label="Active users / day"
              />
              <MiniChart
                data={charts.ai_usage}
                dataKey="est_cost_usd"
                color="#a78bfa"
                label="AI cost (USD)"
                valueFormatter={(v) => `$${v.toFixed(3)}`}
              />
              <MiniChart
                data={charts.scans}
                dataKey="count"
                color="#34d399"
                label="Pipeline scans"
              />
            </div>
          </section>
        )}

        {/* Active pipelines */}
        <section>
          <h2 className="text-xs font-semibold text-zinc-500 uppercase tracking-widest mb-3">
            Active pipelines ({stats.pipelines.active_count})
          </h2>
          {stats.pipelines.active_count === 0 ? (
            <div className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900 px-4 py-3 text-sm text-zinc-500 dark:text-zinc-600">
              No pipelines running
            </div>
          ) : (
            <div className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900 divide-y divide-zinc-200 dark:divide-zinc-800">
              {stats.pipelines.active.map((p) => (
                <div key={p.user_id} className="flex items-center justify-between px-4 py-3">
                  <span className="text-zinc-600 dark:text-zinc-400 font-mono text-xs">{p.user_id}</span>
                  <StagePill stage={p.stage} />
                </div>
              ))}
            </div>
          )}
        </section>

        {/* Announcements */}
        <section>
          <h2 className="text-xs font-semibold text-zinc-500 uppercase tracking-widest mb-3">Announcements</h2>
          <form onSubmit={handleCreateAnnouncement} className="flex gap-2 mb-4">
            <input
              type="text"
              value={newMsg}
              onChange={(e) => setNewMsg(e.target.value)}
              placeholder="New announcement message…"
              className="flex-1 rounded-lg border border-zinc-200 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-900 px-3 py-2 text-sm text-zinc-900 dark:text-white placeholder-zinc-500 dark:placeholder-zinc-600 focus:outline-none focus:border-zinc-500"
            />
            <Tooltip text="Post this announcement - it will appear as a banner on all users' dashboards immediately">
              <button
                type="submit"
                className="rounded-lg bg-zinc-900 dark:bg-white px-4 py-2 text-sm font-semibold text-white dark:text-zinc-900 hover:bg-zinc-700 dark:hover:bg-zinc-100 transition"
              >
                Post
              </button>
            </Tooltip>
          </form>
          {announcements.length === 0 ? (
            <div className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900 px-4 py-3 text-sm text-zinc-500 dark:text-zinc-600">
              No announcements
            </div>
          ) : (
            <div className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900 divide-y divide-zinc-200 dark:divide-zinc-800">
              {announcements.map((a) => (
                <div key={a.id} className="flex items-start justify-between gap-4 px-4 py-3">
                  <div className="flex-1 min-w-0">
                    <p className={`text-sm ${a.is_active ? "text-zinc-900 dark:text-white" : "text-zinc-500 dark:text-zinc-600 line-through"}`}>{a.message}</p>
                    <p className="text-xs text-zinc-500 dark:text-zinc-600 mt-0.5">{formatDate(a.created_at)}</p>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    {a.is_active && (
                      <>
                        <Tooltip text="This announcement is currently visible to all users on their dashboard">
                          <span className="rounded-full border border-green-800 bg-green-900/30 px-2 py-0.5 text-xs text-green-400 cursor-default">Active</span>
                        </Tooltip>
                        <Tooltip text="Hide this announcement from users without deleting it">
                          <button
                            onClick={() => handleDeactivateAnnouncement(a.id)}
                            className="text-xs text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300 transition"
                          >
                            Deactivate
                          </button>
                        </Tooltip>
                      </>
                    )}
                    <Tooltip text="Permanently remove this announcement">
                      <button
                        onClick={() => handleDeleteAnnouncement(a.id)}
                        className="text-xs text-red-600 hover:text-red-400 transition"
                      >
                        Delete
                      </button>
                    </Tooltip>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>

        {/* User table */}
        <section>
          <h2 className="text-xs font-semibold text-zinc-500 uppercase tracking-widest mb-3">
            Users ({stats.users.total})
          </h2>
          <div className="rounded-lg border border-zinc-200 dark:border-zinc-800 overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-zinc-200 dark:border-zinc-800 text-left">
                  <th className="px-4 py-3 text-xs font-semibold text-zinc-500 uppercase tracking-wide">User</th>
                  <th className="px-4 py-3 text-xs font-semibold text-zinc-500 uppercase tracking-wide">Joined</th>
                  <th className="px-4 py-3 text-xs font-semibold text-zinc-500 uppercase tracking-wide">
                    <Tooltip text="Last time this user made an API request - updated at most once every 5 minutes" position="bottom">
                      <span className="cursor-default">Last active</span>
                    </Tooltip>
                  </th>
                  <th className="px-4 py-3 text-xs font-semibold text-zinc-500 uppercase tracking-wide text-right">
                    <Tooltip text="Number of YouTube channels this user has added" position="bottom">
                      <span className="cursor-default">Ch.</span>
                    </Tooltip>
                  </th>
                  <th className="px-4 py-3 text-xs font-semibold text-zinc-500 uppercase tracking-wide text-right">
                    <Tooltip text="Total videos scanned from this user's channels" position="bottom">
                      <span className="cursor-default">Videos</span>
                    </Tooltip>
                  </th>
                  <th className="px-4 py-3 text-xs font-semibold text-zinc-500 uppercase tracking-wide">
                    <Tooltip text="Whether this user has a valid YouTube OAuth token for publishing playlists" position="bottom">
                      <span className="cursor-default">YouTube</span>
                    </Tooltip>
                  </th>
                  <th className="px-4 py-3 text-xs font-semibold text-zinc-500 uppercase tracking-wide">
                    <Tooltip text="Week start date of the most recent plan generated for this user" position="bottom">
                      <span className="cursor-default">Last plan</span>
                    </Tooltip>
                  </th>
                  <th className="px-4 py-3 text-xs font-semibold text-zinc-500 uppercase tracking-wide">
                    <Tooltip text="Current pipeline stage if a scan is running for this user" position="bottom">
                      <span className="cursor-default">Pipeline</span>
                    </Tooltip>
                  </th>
                  <th className="px-4 py-3 text-xs font-semibold text-zinc-500 uppercase tracking-wide">Actions</th>
                </tr>
              </thead>
              <tbody>
                {stats.user_rows.map((u) => (
                  <tr key={u.id} className="border-b border-zinc-200 dark:border-zinc-800 last:border-0 hover:bg-zinc-50/60 dark:hover:bg-zinc-900/60">
                    <td className="px-4 py-3">
                      <p className="text-zinc-900 dark:text-white font-medium">{u.display_name ?? "-"}</p>
                      <p className="text-zinc-500 text-xs">{u.email}</p>
                    </td>
                    <td className="px-4 py-3 text-zinc-600 dark:text-zinc-400 text-xs whitespace-nowrap">{formatDate(u.created_at)}</td>
                    <td className="px-4 py-3 text-zinc-600 dark:text-zinc-400 text-xs whitespace-nowrap">{formatRelative(u.last_active_at)}</td>
                    <td className="px-4 py-3 text-zinc-700 dark:text-zinc-300 text-right">{u.channels}</td>
                    <td className="px-4 py-3 text-zinc-700 dark:text-zinc-300 text-right">{u.videos.toLocaleString()}</td>
                    <td className="px-4 py-3">
                      {u.youtube_connected
                        ? <span className="text-green-400 text-xs">Connected</span>
                        : <span className="text-zinc-500 dark:text-zinc-600 text-xs">-</span>}
                    </td>
                    <td className="px-4 py-3 text-zinc-600 dark:text-zinc-400 text-xs whitespace-nowrap">{u.last_plan ?? "-"}</td>
                    <td className="px-4 py-3"><StagePill stage={u.pipeline_stage} /></td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <Tooltip text="Trigger a fresh channel scan, AI classification, and plan generation for this user">
                          <button
                            onClick={() => handleRetryScan(u.id, u.email)}
                            disabled={retryingUser === u.id || !!u.pipeline_stage}
                            className="text-xs text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-200 disabled:opacity-30 transition"
                          >
                            {retryingUser === u.id ? "Starting…" : "↺ Scan"}
                          </button>
                        </Tooltip>
                        <Tooltip text="Remove all channel subscriptions and schedule - user goes through onboarding again on next login">
                          <button
                            onClick={() => handleResetOnboarding(u.id, u.email)}
                            disabled={resettingUser === u.id}
                            className="text-xs text-amber-700 hover:text-amber-400 disabled:opacity-30 transition"
                          >
                            {resettingUser === u.id ? "Resetting…" : "Reset"}
                          </button>
                        </Tooltip>
                        <Tooltip text="Permanently delete this user and all their data - channels, videos, plan history, and credentials">
                          <button
                            onClick={() => handleDeleteUser(u.id, u.email)}
                            disabled={deletingUser === u.id}
                            className="text-xs text-red-700 hover:text-red-400 disabled:opacity-30 transition"
                          >
                            {deletingUser === u.id ? "Deleting…" : "Delete"}
                          </button>
                        </Tooltip>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        {/* Runbook */}
        <details className="mt-8 rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-50/40 dark:bg-zinc-900/40 group">
          <summary className="flex items-center justify-between px-5 py-4 cursor-pointer list-none select-none">
            <span className="text-sm font-semibold text-zinc-600 dark:text-zinc-400 group-open:text-zinc-900 dark:group-open:text-white transition">
              Runbook - common operational issues
            </span>
            <span className="text-zinc-500 dark:text-zinc-600 text-xs group-open:rotate-180 transition-transform">▼</span>
          </summary>
          <div className="px-5 pb-5 overflow-x-auto">
            <table className="w-full text-xs border-collapse">
              <thead>
                <tr className="border-b border-zinc-200 dark:border-zinc-800">
                  <th className="text-left py-2 pr-4 font-semibold text-zinc-500 uppercase tracking-wide w-1/4">Symptom</th>
                  <th className="text-left py-2 pr-4 font-semibold text-zinc-500 uppercase tracking-wide w-1/3">Cause</th>
                  <th className="text-left py-2 font-semibold text-zinc-500 uppercase tracking-wide">Fix</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-200 dark:divide-zinc-800">
                {([
                  [
                    'Pipeline stuck on "classifying" forever',
                    "Anthropic batch timed out or server restarted mid-batch - stale classifier_batch_id in DB",
                    "Railway shell: UPDATE user_credentials SET classifier_batch_id = NULL WHERE user_id = '<id>'; then hit Scan",
                  ],
                  [
                    "User has 0 videos after a scan",
                    "All videos filtered by pre-classification blocklist (non-workout titles), or YouTube API quota exhausted",
                    "Check Railway logs for that user's scan. If quota, wait 24 h and retry.",
                  ],
                  [
                    "User's plan is all Rest days",
                    "Planner found no matching videos - library too small or schedule too restrictive",
                    "Try Scan to classify more videos; check user's schedule settings in DB.",
                  ],
                  [
                    '"Unclassified" count keeps growing',
                    "New videos scanned faster than Anthropic batches process them, or 300/run batch cap hit",
                    "Normal - clears on next Sunday scan. Trigger Scan manually to accelerate.",
                  ],
                  [
                    'YouTube "credentials invalid" for a user',
                    "User's Google OAuth refresh token was revoked (changed password, or revoked app access)",
                    "User must re-authenticate: sign out then sign in again to re-grant YouTube access.",
                  ],
                  [
                    "Admin stats show 0 AI usage despite classifications",
                    "Migration 005 not yet applied (batch_usage_log table missing)",
                    "Trigger a Railway redeploy - Dockerfile runs alembic upgrade head automatically.",
                  ],
                ] as [string, string, string][]).map(([symptom, cause, fix]) => (
                  <tr key={symptom} className="align-top">
                    <td className="py-2.5 pr-4 text-zinc-700 dark:text-zinc-300 font-medium">{symptom}</td>
                    <td className="py-2.5 pr-4 text-zinc-500">{cause}</td>
                    <td className="py-2.5 text-zinc-600 dark:text-zinc-400 font-mono">{fix}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>

      </div>
      <Footer isAdmin />
    </main>
  );
}
