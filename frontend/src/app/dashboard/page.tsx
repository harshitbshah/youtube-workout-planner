"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  getMe,
  getChannels,
  getUpcomingPlan,
  generatePlan,
  publishPlan,
  triggerScan,
  logout,
  type User,
  type PlanResponse,
  type PlanDay,
  type VideoSummary,
  type PublishResponse,
} from "@/lib/api";

const DAY_LABELS: Record<string, string> = {
  monday: "Mon",
  tuesday: "Tue",
  wednesday: "Wed",
  thursday: "Thu",
  friday: "Fri",
  saturday: "Sat",
  sunday: "Sun",
};

function formatDuration(sec: number | null): string {
  if (!sec) return "";
  const m = Math.round(sec / 60);
  return `${m} min`;
}

function Badge({ label }: { label: string }) {
  return (
    <span className="rounded-full bg-zinc-800 border border-zinc-700 px-2 py-0.5 text-xs text-zinc-400 capitalize">
      {label}
    </span>
  );
}

function VideoCard({ video }: { video: VideoSummary }) {
  return (
    <a
      href={video.url}
      target="_blank"
      rel="noopener noreferrer"
      className="group block rounded-lg overflow-hidden border border-zinc-700 bg-zinc-900 hover:border-zinc-500 transition"
    >
      {/* Thumbnail */}
      <div className="relative aspect-video bg-zinc-800">
        {/* YouTube thumbnail via video ID */}
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={`https://i.ytimg.com/vi/${video.id}/mqdefault.jpg`}
          alt={video.title}
          className="w-full h-full object-cover"
        />
        {video.duration_sec && (
          <span className="absolute bottom-1.5 right-1.5 rounded bg-black/80 px-1.5 py-0.5 text-xs text-white">
            {formatDuration(video.duration_sec)}
          </span>
        )}
      </div>

      {/* Info */}
      <div className="p-3 space-y-2">
        <p className="text-sm font-medium text-white leading-snug line-clamp-2 group-hover:text-zinc-200">
          {video.title}
        </p>
        <p className="text-xs text-zinc-500">{video.channel_name}</p>
        <div className="flex flex-wrap gap-1.5">
          {video.workout_type && <Badge label={video.workout_type} />}
          {video.body_focus && <Badge label={video.body_focus} />}
          {video.difficulty && video.difficulty !== "any" && <Badge label={video.difficulty} />}
        </div>
      </div>
    </a>
  );
}

function RestDayCard() {
  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-900/40 p-4 flex items-center justify-center min-h-[180px]">
      <p className="text-zinc-600 text-sm">Rest day</p>
    </div>
  );
}

function EmptyDayCard() {
  return (
    <div className="rounded-lg border border-dashed border-zinc-800 bg-zinc-900/20 p-4 flex items-center justify-center min-h-[180px]">
      <p className="text-zinc-700 text-sm">No video assigned</p>
    </div>
  );
}

export default function DashboardPage() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [plan, setPlan] = useState<PlanResponse | null>(null);
  const [hasChannels, setHasChannels] = useState(true);
  const [scanning, setScanning] = useState(false);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [publishResult, setPublishResult] = useState<PublishResponse | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    // Check if we just came from onboarding with a scan in progress
    const params = new URLSearchParams(window.location.search);
    const scanJustTriggered = params.get("scanning") === "1";
    if (scanJustTriggered) {
      setScanning(true);
      window.history.replaceState({}, "", window.location.pathname);
    }

    Promise.all([getMe(), getUpcomingPlan().catch(() => null), getChannels().catch(() => [])])
      .then(([u, p, channels]) => {
        setUser(u);
        setPlan(p);
        setHasChannels(channels.length > 0);
        if (p) setScanning(false); // plan already exists, no need to poll
      })
      .catch(() => router.replace("/"))
      .finally(() => setLoading(false));
  }, [router]);

  // Poll for the plan every 15s while scanning
  useEffect(() => {
    if (!scanning || plan) return;
    const interval = setInterval(() => {
      getUpcomingPlan()
        .then((p) => {
          setPlan(p);
          setScanning(false);
        })
        .catch(() => {}); // still scanning, keep polling
    }, 15_000);
    return () => clearInterval(interval);
  }, [scanning, plan]);

  async function handleScan() {
    setGenerating(true);
    setError("");
    try {
      await triggerScan();
      setScanning(true);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to start scan");
    } finally {
      setGenerating(false);
    }
  }

  async function handleGenerate() {
    setGenerating(true);
    setError("");
    try {
      const p = await generatePlan();
      setPlan(p);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to generate plan");
    } finally {
      setGenerating(false);
    }
  }

  async function handlePublish() {
    setPublishing(true);
    setError("");
    setPublishResult(null);
    try {
      const result = await publishPlan();
      setPublishResult(result);
      // If we get here, credentials are valid — ensure user state reflects that
      setUser((u) => u ? { ...u, credentials_valid: true } : u);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Failed to publish plan";
      setError(msg);
      // If revoked, mark locally so banner appears without a full reload
      if (msg.includes("revoked")) {
        setUser((u) => u ? { ...u, credentials_valid: false } : u);
      }
    } finally {
      setPublishing(false);
    }
  }

  async function handleLogout() {
    await logout();
    router.replace("/");
  }

  if (loading) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-zinc-950">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-zinc-600 border-t-white" />
      </main>
    );
  }

  const weekLabel = plan
    ? new Date(plan.week_start + "T00:00:00").toLocaleDateString("en-GB", {
        day: "numeric",
        month: "short",
        year: "numeric",
      })
    : null;

  return (
    <main className="min-h-screen bg-zinc-950 px-4 py-8">
      <div className="max-w-5xl mx-auto">

        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-2xl font-bold text-white">
              {user?.display_name ? `${user.display_name.split(" ")[0]}'s plan` : "Your plan"}
            </h1>
            {weekLabel && (
              <p className="text-zinc-500 text-sm mt-0.5">Week of {weekLabel}</p>
            )}
          </div>
          <div className="flex items-center gap-3">
            <Link
              href="/library"
              className="rounded-lg border border-zinc-700 px-4 py-2 text-sm text-zinc-400 hover:bg-zinc-800 transition"
            >
              Library
            </Link>
            <Link
              href="/settings"
              className="rounded-lg border border-zinc-700 px-4 py-2 text-sm text-zinc-400 hover:bg-zinc-800 transition"
            >
              Settings
            </Link>
            {plan ? (
              <button
                onClick={handleGenerate}
                disabled={generating}
                className="rounded-lg bg-white px-4 py-2 text-sm font-semibold text-zinc-900 hover:bg-zinc-100 disabled:opacity-40 cursor-pointer transition"
              >
                {generating ? "Generating…" : "Regenerate"}
              </button>
            ) : (
              <button
                onClick={handleScan}
                disabled={generating || scanning}
                className="rounded-lg bg-white px-4 py-2 text-sm font-semibold text-zinc-900 hover:bg-zinc-100 disabled:opacity-40 cursor-pointer transition"
              >
                {generating ? "Starting…" : "Generate plan"}
              </button>
            )}
            {user?.youtube_connected && user?.credentials_valid && plan ? (
              <button
                onClick={handlePublish}
                disabled={publishing}
                className="rounded-lg border border-red-600 bg-red-600/10 px-4 py-2 text-sm font-medium text-red-400 hover:bg-red-600/20 disabled:opacity-40 cursor-pointer transition"
              >
                {publishing ? "Publishing…" : "Publish to YouTube"}
              </button>
            ) : (
              <button
                disabled
                title={
                  !user?.youtube_connected
                    ? "Sign in with Google to connect YouTube"
                    : !user?.credentials_valid
                    ? "YouTube access revoked — sign in again to reconnect"
                    : "Generate a plan first"
                }
                className="rounded-lg border border-zinc-700 px-4 py-2 text-sm text-zinc-600 opacity-50 cursor-not-allowed transition"
              >
                Publish to YouTube
              </button>
            )}
            <button
              onClick={handleLogout}
              className="rounded-lg border border-zinc-700 px-4 py-2 text-sm text-zinc-400 hover:bg-zinc-800 cursor-pointer transition"
            >
              Sign out
            </button>
          </div>
        </div>

        {/* Generate in progress banner */}
        {generating && !scanning && (
          <div className="mb-6 flex items-center gap-3 rounded-lg border border-zinc-700 bg-zinc-800/60 px-4 py-3 text-sm text-zinc-300">
            <svg className="h-4 w-4 animate-spin shrink-0 text-zinc-400" viewBox="0 0 24 24" fill="none">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"/>
            </svg>
            <span>Generating your plan — picking the best videos for each day…</span>
          </div>
        )}

        {/* Scan in progress banner */}
        {scanning && (
          <div className="mb-6 flex items-center gap-3 rounded-lg border border-zinc-700 bg-zinc-800/60 px-4 py-3 text-sm text-zinc-300">
            <svg className="h-4 w-4 animate-spin shrink-0 text-zinc-400" viewBox="0 0 24 24" fill="none">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"/>
            </svg>
            <span>
              Scanning your channels and classifying videos — this usually takes 2–5 minutes.
              Your plan will appear automatically when ready.
            </span>
          </div>
        )}

        {/* YouTube access revoked banner */}
        {user?.youtube_connected && !user?.credentials_valid && (
          <div className="mb-6 rounded-lg border border-amber-700 bg-amber-900/20 px-4 py-3 text-sm text-amber-400">
            Your YouTube access has been revoked. Sign out and sign in again with Google to reconnect.
          </div>
        )}

        {error && (
          <div className="mb-6 rounded-lg border border-red-800 bg-red-900/30 px-4 py-3 text-sm text-red-400">
            {error}
          </div>
        )}

        {/* Publish success banner */}
        {publishResult && (
          <div className="mb-6 rounded-lg border border-green-800 bg-green-900/20 px-4 py-3 text-sm text-green-400 flex items-center justify-between">
            <span>
              Plan published — {publishResult.video_count} video{publishResult.video_count !== 1 ? "s" : ""} added to your playlist.
            </span>
            <a
              href={publishResult.playlist_url}
              target="_blank"
              rel="noopener noreferrer"
              className="ml-4 underline hover:text-green-300 whitespace-nowrap"
            >
              Open playlist →
            </a>
          </div>
        )}

        {/* No plan yet */}
        {!plan && (
          <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-12 text-center">
            {!hasChannels ? (
              <>
                <p className="text-zinc-400 text-sm mb-4">
                  Add your favourite YouTube fitness channels to get started.
                </p>
                <Link
                  href="/onboarding"
                  className="inline-block rounded-lg bg-white px-5 py-2.5 text-sm font-semibold text-zinc-900 hover:bg-zinc-100 transition"
                >
                  Set up my plan →
                </Link>
              </>
            ) : scanning ? (
              <p className="text-zinc-500 text-sm">Hang tight — building your plan in the background…</p>
            ) : (
              <>
                <p className="text-zinc-400 text-sm mb-4">No plan generated yet.</p>
                <button
                  onClick={handleScan}
                  disabled={generating}
                  className="rounded-lg bg-white px-5 py-2.5 text-sm font-semibold text-zinc-900 hover:bg-zinc-100 disabled:opacity-40 cursor-pointer transition"
                >
                  {generating ? "Starting scan…" : "Scan channels & generate plan"}
                </button>
              </>
            )}
          </div>
        )}

        {/* Plan grid */}
        {plan && (
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
            {plan.days.map((day: PlanDay) => (
              <div key={day.day}>
                <p className="text-xs font-semibold text-zinc-500 uppercase tracking-wide mb-2">
                  {DAY_LABELS[day.day] ?? day.day}
                </p>
                {day.video ? (
                  <VideoCard video={day.video} />
                ) : day.day === "sunday" ? (
                  <RestDayCard />
                ) : (
                  <EmptyDayCard />
                )}
              </div>
            ))}
          </div>
        )}

      </div>
    </main>
  );
}
