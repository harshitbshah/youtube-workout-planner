"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { getMe } from "@/lib/api";

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

function StatCard({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900 p-5">
      <p className="text-xs font-semibold text-zinc-500 uppercase tracking-widest mb-2">{label}</p>
      <p className="text-3xl font-bold text-white">{value}</p>
      {sub && <p className="text-xs text-zinc-500 mt-1">{sub}</p>}
    </div>
  );
}

function StagePill({ stage }: { stage: string | null }) {
  if (!stage) return <span className="text-zinc-600 text-xs">—</span>;
  const colours: Record<string, string> = {
    scanning: "bg-blue-900/40 text-blue-400 border-blue-800",
    classifying: "bg-purple-900/40 text-purple-400 border-purple-800",
    generating: "bg-amber-900/40 text-amber-400 border-amber-800",
    done: "bg-green-900/40 text-green-400 border-green-800",
    failed: "bg-red-900/40 text-red-400 border-red-800",
  };
  return (
    <span className={`rounded-full border px-2 py-0.5 text-xs capitalize ${colours[stage] ?? "bg-zinc-800 text-zinc-400 border-zinc-700"}`}>
      {stage}
    </span>
  );
}

function formatDate(iso: string | null) {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
}

function formatRelative(iso: string | null) {
  if (!iso) return "—";
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60_000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}

function UsageBlock({ label, data }: { label: string; data: UsagePeriod }) {
  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-4 space-y-2">
      <p className="text-xs font-semibold text-zinc-500 uppercase tracking-widest">{label}</p>
      <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
        <span className="text-zinc-500">Batches</span>
        <span className="text-white font-medium">{data.batches}</span>
        <span className="text-zinc-500">Videos classified</span>
        <span className="text-white font-medium">{data.videos_classified.toLocaleString()}</span>
        <span className="text-zinc-500">Input tokens</span>
        <span className="text-white font-medium">{data.input_tokens.toLocaleString()}</span>
        <span className="text-zinc-500">Output tokens</span>
        <span className="text-white font-medium">{data.output_tokens.toLocaleString()}</span>
        <span className="text-zinc-500">Est. cost</span>
        <span className="text-white font-medium">${data.est_cost_usd.toFixed(4)}</span>
      </div>
    </div>
  );
}

// ─── Main page ───────────────────────────────────────────────────────────────

export default function AdminPage() {
  const router = useRouter();
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [announcements, setAnnouncements] = useState<Announcement[]>([]);
  const [newMsg, setNewMsg] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);
  const [deletingUser, setDeletingUser] = useState<string | null>(null);
  const [retryingUser, setRetryingUser] = useState<string | null>(null);

  async function fetchStats() {
    const data = await adminFetch<AdminStats>("/admin/stats");
    setStats(data);
    setLastRefresh(new Date());
  }

  async function fetchAnnouncements() {
    const data = await adminFetch<Announcement[]>("/admin/announcements");
    setAnnouncements(data);
  }

  useEffect(() => {
    getMe()
      .catch(() => { router.replace("/"); return Promise.reject(); })
      .then(() => Promise.all([fetchStats(), fetchAnnouncements()]))
      .catch((e: unknown) => {
        if ((e as { status?: number })?.status === 403) { router.replace("/dashboard"); return; }
        if (e) setError("Could not load admin stats.");
      })
      .finally(() => setLoading(false));
  }, [router]);

  // Auto-refresh every 30s
  useEffect(() => {
    const id = setInterval(() => { fetchStats().catch(() => {}); }, 30_000);
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
      <main className="flex min-h-screen items-center justify-center bg-zinc-950">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-zinc-600 border-t-white" />
      </main>
    );
  }

  if (error) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-zinc-950 text-red-400 text-sm">
        {error}
      </main>
    );
  }

  if (!stats) return null;

  return (
    <main className="min-h-screen bg-zinc-950 px-4 py-8">
      <div className="max-w-6xl mx-auto space-y-10">

        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <h1 className="text-2xl font-bold text-white">Admin</h1>
            {lastRefresh && (
              <p className="text-xs text-zinc-600 mt-0.5">
                Updated {lastRefresh.toLocaleTimeString()} · auto-refreshes every 30s
              </p>
            )}
          </div>
          <Link href="/dashboard" className="text-sm text-zinc-500 hover:text-zinc-300 transition">
            ← Dashboard
          </Link>
        </div>

        {/* Users */}
        <section>
          <h2 className="text-xs font-semibold text-zinc-500 uppercase tracking-widest mb-3">Users</h2>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <StatCard label="Total users" value={stats.users.total} />
            <StatCard label="New (7 days)" value={stats.users.new_7d} sub={`${stats.users.new_30d} in last 30 days`} />
            <StatCard label="YouTube connected" value={stats.users.youtube_connected} sub={`of ${stats.users.total} users`} />
            <StatCard label="Plans this week" value={stats.plans.users_with_plan_this_week} sub={`of ${stats.users.total} users`} />
          </div>
        </section>

        {/* Library */}
        <section>
          <h2 className="text-xs font-semibold text-zinc-500 uppercase tracking-widest mb-3">Library</h2>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <StatCard label="Total videos" value={stats.library.total_videos.toLocaleString()} />
            <StatCard label="Classified" value={`${stats.library.classification_pct}%`} sub={`${stats.library.classified.toLocaleString()} videos`} />
            <StatCard label="Unclassified" value={stats.library.unclassified.toLocaleString()} />
            <StatCard label="Channels" value={stats.channels.total} sub={`avg ${stats.channels.avg_per_user} per user`} />
          </div>
        </section>

        {/* AI usage */}
        <section>
          <h2 className="text-xs font-semibold text-zinc-500 uppercase tracking-widest mb-3">AI Usage (Haiku 4.5 Batch)</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <UsageBlock label="Last 7 days" data={stats.ai_usage.last_7d} />
            <UsageBlock label="All time" data={stats.ai_usage.all_time} />
          </div>
          <p className="text-xs text-zinc-600 mt-2">Cost estimate uses Batch API pricing: $0.40/MTok input · $2.00/MTok output</p>
        </section>

        {/* Active pipelines */}
        <section>
          <h2 className="text-xs font-semibold text-zinc-500 uppercase tracking-widest mb-3">
            Active pipelines ({stats.pipelines.active_count})
          </h2>
          {stats.pipelines.active_count === 0 ? (
            <div className="rounded-lg border border-zinc-800 bg-zinc-900 px-4 py-3 text-sm text-zinc-600">
              No pipelines running
            </div>
          ) : (
            <div className="rounded-lg border border-zinc-800 bg-zinc-900 divide-y divide-zinc-800">
              {stats.pipelines.active.map((p) => (
                <div key={p.user_id} className="flex items-center justify-between px-4 py-3">
                  <span className="text-zinc-400 font-mono text-xs">{p.user_id}</span>
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
              className="flex-1 rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-white placeholder-zinc-600 focus:outline-none focus:border-zinc-500"
            />
            <button
              type="submit"
              className="rounded-lg bg-white px-4 py-2 text-sm font-semibold text-zinc-900 hover:bg-zinc-100 transition"
            >
              Post
            </button>
          </form>
          {announcements.length === 0 ? (
            <div className="rounded-lg border border-zinc-800 bg-zinc-900 px-4 py-3 text-sm text-zinc-600">
              No announcements
            </div>
          ) : (
            <div className="rounded-lg border border-zinc-800 bg-zinc-900 divide-y divide-zinc-800">
              {announcements.map((a) => (
                <div key={a.id} className="flex items-start justify-between gap-4 px-4 py-3">
                  <div className="flex-1 min-w-0">
                    <p className={`text-sm ${a.is_active ? "text-white" : "text-zinc-600 line-through"}`}>{a.message}</p>
                    <p className="text-xs text-zinc-600 mt-0.5">{formatDate(a.created_at)}</p>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    {a.is_active && (
                      <>
                        <span className="rounded-full border border-green-800 bg-green-900/30 px-2 py-0.5 text-xs text-green-400">Active</span>
                        <button
                          onClick={() => handleDeactivateAnnouncement(a.id)}
                          className="text-xs text-zinc-500 hover:text-zinc-300 transition"
                        >
                          Deactivate
                        </button>
                      </>
                    )}
                    <button
                      onClick={() => handleDeleteAnnouncement(a.id)}
                      className="text-xs text-red-600 hover:text-red-400 transition"
                    >
                      Delete
                    </button>
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
          <div className="rounded-lg border border-zinc-800 overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-zinc-800 text-left">
                  <th className="px-4 py-3 text-xs font-semibold text-zinc-500 uppercase tracking-wide">User</th>
                  <th className="px-4 py-3 text-xs font-semibold text-zinc-500 uppercase tracking-wide">Joined</th>
                  <th className="px-4 py-3 text-xs font-semibold text-zinc-500 uppercase tracking-wide">Last active</th>
                  <th className="px-4 py-3 text-xs font-semibold text-zinc-500 uppercase tracking-wide text-right">Ch.</th>
                  <th className="px-4 py-3 text-xs font-semibold text-zinc-500 uppercase tracking-wide text-right">Videos</th>
                  <th className="px-4 py-3 text-xs font-semibold text-zinc-500 uppercase tracking-wide">YouTube</th>
                  <th className="px-4 py-3 text-xs font-semibold text-zinc-500 uppercase tracking-wide">Last plan</th>
                  <th className="px-4 py-3 text-xs font-semibold text-zinc-500 uppercase tracking-wide">Pipeline</th>
                  <th className="px-4 py-3 text-xs font-semibold text-zinc-500 uppercase tracking-wide">Actions</th>
                </tr>
              </thead>
              <tbody>
                {stats.user_rows.map((u) => (
                  <tr key={u.id} className="border-b border-zinc-800 last:border-0 hover:bg-zinc-900/60">
                    <td className="px-4 py-3">
                      <p className="text-white font-medium">{u.display_name ?? "—"}</p>
                      <p className="text-zinc-500 text-xs">{u.email}</p>
                    </td>
                    <td className="px-4 py-3 text-zinc-400 text-xs whitespace-nowrap">{formatDate(u.created_at)}</td>
                    <td className="px-4 py-3 text-zinc-400 text-xs whitespace-nowrap">{formatRelative(u.last_active_at)}</td>
                    <td className="px-4 py-3 text-zinc-300 text-right">{u.channels}</td>
                    <td className="px-4 py-3 text-zinc-300 text-right">{u.videos.toLocaleString()}</td>
                    <td className="px-4 py-3">
                      {u.youtube_connected
                        ? <span className="text-green-400 text-xs">Connected</span>
                        : <span className="text-zinc-600 text-xs">—</span>}
                    </td>
                    <td className="px-4 py-3 text-zinc-400 text-xs whitespace-nowrap">{u.last_plan ?? "—"}</td>
                    <td className="px-4 py-3"><StagePill stage={u.pipeline_stage} /></td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => handleRetryScan(u.id, u.email)}
                          disabled={retryingUser === u.id || !!u.pipeline_stage}
                          title="Trigger a fresh scan + plan for this user"
                          className="text-xs text-zinc-500 hover:text-zinc-200 disabled:opacity-30 transition"
                        >
                          {retryingUser === u.id ? "Starting…" : "↺ Scan"}
                        </button>
                        <button
                          onClick={() => handleDeleteUser(u.id, u.email)}
                          disabled={deletingUser === u.id}
                          className="text-xs text-red-700 hover:text-red-400 disabled:opacity-30 transition"
                        >
                          {deletingUser === u.id ? "Deleting…" : "Delete"}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

      </div>
    </main>
  );
}
