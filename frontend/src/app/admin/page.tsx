"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { getMe } from "@/lib/api";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type AdminStats = {
  users: { total: number; new_7d: number; new_30d: number; youtube_connected: number };
  library: { total_videos: number; classified: number; unclassified: number; classification_pct: number };
  channels: { total: number; avg_per_user: number };
  plans: { users_with_plan_this_week: number };
  pipelines: { active_count: number; active: { user_id: string; stage: string }[] };
  user_rows: {
    id: string;
    email: string;
    display_name: string | null;
    created_at: string | null;
    channels: number;
    videos: number;
    youtube_connected: boolean;
    last_plan: string | null;
    pipeline_stage: string | null;
  }[];
};

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

export default function AdminPage() {
  const router = useRouter();
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);

  async function fetchStats() {
    const res = await fetch(`${API_BASE}/admin/stats`, { credentials: "include", headers: { Authorization: `Bearer ${localStorage.getItem("token") ?? ""}` } });
    if (res.status === 403) throw new Error("forbidden");
    if (!res.ok) throw new Error("Failed to load stats");
    return res.json() as Promise<AdminStats>;
  }

  useEffect(() => {
    getMe()
      .catch(() => { router.replace("/"); return Promise.reject(); })
      .then(() => fetchStats())
      .then((data) => { setStats(data); setLastRefresh(new Date()); })
      .catch((e) => {
        if (e?.message === "forbidden") { router.replace("/dashboard"); return; }
        if (e) setError("Could not load admin stats.");
      })
      .finally(() => setLoading(false));
  }, [router]);

  // Auto-refresh every 30s
  useEffect(() => {
    const id = setInterval(() => {
      fetchStats()
        .then((data) => { setStats(data); setLastRefresh(new Date()); })
        .catch(() => {});
    }, 30_000);
    return () => clearInterval(id);
  }, []);

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
      <div className="max-w-6xl mx-auto">

        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between mb-8 gap-3">
          <div>
            <h1 className="text-2xl font-bold text-white">Admin</h1>
            {lastRefresh && (
              <p className="text-xs text-zinc-600 mt-0.5">
                Last updated {lastRefresh.toLocaleTimeString()} · auto-refreshes every 30s
              </p>
            )}
          </div>
          <Link
            href="/dashboard"
            className="text-sm text-zinc-500 hover:text-zinc-300 transition"
          >
            ← Dashboard
          </Link>
        </div>

        {/* Stat cards */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-8">
          <StatCard label="Total users" value={stats.users.total} />
          <StatCard label="New (7 days)" value={stats.users.new_7d} sub={`${stats.users.new_30d} in last 30 days`} />
          <StatCard label="YouTube connected" value={stats.users.youtube_connected} sub={`of ${stats.users.total} users`} />
          <StatCard label="Plans this week" value={stats.plans.users_with_plan_this_week} sub={`of ${stats.users.total} users`} />
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-8">
          <StatCard label="Total videos" value={stats.library.total_videos.toLocaleString()} />
          <StatCard label="Classified" value={`${stats.library.classification_pct}%`} sub={`${stats.library.classified.toLocaleString()} videos`} />
          <StatCard label="Unclassified" value={stats.library.unclassified.toLocaleString()} />
          <StatCard label="Channels" value={stats.channels.total} sub={`avg ${stats.channels.avg_per_user} per user`} />
        </div>

        {/* Active pipelines */}
        <div className="mb-8">
          <h2 className="text-sm font-semibold text-zinc-400 uppercase tracking-widest mb-3">
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
                  <span className="text-sm text-zinc-400 font-mono text-xs">{p.user_id}</span>
                  <StagePill stage={p.stage} />
                </div>
              ))}
            </div>
          )}
        </div>

        {/* User table */}
        <div>
          <h2 className="text-sm font-semibold text-zinc-400 uppercase tracking-widest mb-3">
            Users ({stats.users.total})
          </h2>
          <div className="rounded-lg border border-zinc-800 overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-zinc-800 text-left">
                  <th className="px-4 py-3 text-xs font-semibold text-zinc-500 uppercase tracking-wide">User</th>
                  <th className="px-4 py-3 text-xs font-semibold text-zinc-500 uppercase tracking-wide">Joined</th>
                  <th className="px-4 py-3 text-xs font-semibold text-zinc-500 uppercase tracking-wide text-right">Channels</th>
                  <th className="px-4 py-3 text-xs font-semibold text-zinc-500 uppercase tracking-wide text-right">Videos</th>
                  <th className="px-4 py-3 text-xs font-semibold text-zinc-500 uppercase tracking-wide">YouTube</th>
                  <th className="px-4 py-3 text-xs font-semibold text-zinc-500 uppercase tracking-wide">Last plan</th>
                  <th className="px-4 py-3 text-xs font-semibold text-zinc-500 uppercase tracking-wide">Pipeline</th>
                </tr>
              </thead>
              <tbody>
                {stats.user_rows.map((u) => (
                  <tr key={u.id} className="border-b border-zinc-800 last:border-0 hover:bg-zinc-900/60">
                    <td className="px-4 py-3">
                      <p className="text-white font-medium">{u.display_name ?? "—"}</p>
                      <p className="text-zinc-500 text-xs">{u.email}</p>
                    </td>
                    <td className="px-4 py-3 text-zinc-400 text-xs whitespace-nowrap">
                      {u.created_at ? new Date(u.created_at).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" }) : "—"}
                    </td>
                    <td className="px-4 py-3 text-zinc-300 text-right">{u.channels}</td>
                    <td className="px-4 py-3 text-zinc-300 text-right">{u.videos.toLocaleString()}</td>
                    <td className="px-4 py-3">
                      {u.youtube_connected
                        ? <span className="text-green-400 text-xs">Connected</span>
                        : <span className="text-zinc-600 text-xs">—</span>}
                    </td>
                    <td className="px-4 py-3 text-zinc-400 text-xs whitespace-nowrap">
                      {u.last_plan ?? "—"}
                    </td>
                    <td className="px-4 py-3">
                      <StagePill stage={u.pipeline_stage} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

      </div>
    </main>
  );
}
