"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Footer } from "@/components/Footer";
import FeedbackWidget from "@/components/FeedbackWidget";
import {
  getMe,
  getChannels,
  getUpcomingPlan,
  generatePlan,
  publishPlan,
  getPublishStatus,
  triggerScan,
  getJobStatus,
  getActiveAnnouncement,
  getLibrary,
  swapPlanDay,
  logout,
  setToken,
  youtubeConnectUrl,
  type User,
  type PlanResponse,
  type PlanDay,
  type VideoSummary,
  type PublishStatus,
} from "@/lib/api";
import { DAY_LABELS, formatDuration } from "@/lib/utils";
import Badge from "@/components/Badge";

function SwapPicker({
  day,
  workoutType,
  currentVideoId,
  onSwap,
  onClose,
}: {
  day: string;
  workoutType: string | null;
  currentVideoId: string;
  onSwap: (video: VideoSummary) => Promise<void>;
  onClose: () => void;
}) {
  const pickerRef = useRef<HTMLDivElement>(null);
  const [videos, setVideos] = useState<VideoSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [filterType, setFilterType] = useState<string | null>(workoutType);
  const [swapping, setSwapping] = useState<string | null>(null);
  const isMobile = typeof window !== "undefined" && window.innerWidth < 640;

  useEffect(() => {
    setLoading(true);
    getLibrary({ workout_type: filterType ?? undefined, limit: 10 })
      .then((r) => setVideos(r.videos.filter((v) => v.id !== currentVideoId)))
      .catch(() => setVideos([]))
      .finally(() => setLoading(false));
  }, [filterType, currentVideoId]);

  async function handleSelect(video: VideoSummary) {
    setSwapping(video.id);
    await onSwap(video);
    setSwapping(null);
  }

  // Shared header + video content
  const header = (
    <div className="flex items-center justify-between px-4 py-3 border-b border-zinc-100 dark:border-zinc-800 shrink-0">
      <div className="flex items-center gap-3">
        <span className="text-sm font-semibold text-zinc-800 dark:text-white">Pick a replacement</span>
        {filterType && (
          <span className="inline-flex items-center rounded-full bg-zinc-100 dark:bg-zinc-800 px-2.5 py-0.5 text-xs text-zinc-600 dark:text-zinc-400 capitalize">
            {filterType}
          </span>
        )}
        {filterType && (
          <button
            onClick={() => setFilterType(null)}
            className="text-xs text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-300 underline transition cursor-pointer"
          >
            Show all types
          </button>
        )}
      </div>
      <button onClick={onClose} className="text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-300 transition text-lg leading-none cursor-pointer">✕</button>
    </div>
  );

  const videoGrid = (cols2: boolean) => (
    loading ? (
      <div className="flex justify-center py-10">
        <div className="h-5 w-5 animate-spin rounded-full border-2 border-zinc-300 border-t-zinc-600" />
      </div>
    ) : videos.length === 0 ? (
      <p className="py-8 text-sm text-zinc-500 text-center">No videos found.</p>
    ) : (
      <div className={`p-4 grid gap-3 ${cols2 ? "grid-cols-2" : "grid-cols-1"}`}>
        {videos.map((v) => (
          <button
            key={v.id}
            onClick={() => handleSelect(v)}
            disabled={swapping !== null}
            className="group text-left rounded-lg overflow-hidden border border-zinc-200 dark:border-zinc-700 hover:border-zinc-400 dark:hover:border-zinc-500 bg-white dark:bg-zinc-900 disabled:opacity-50 transition cursor-pointer"
          >
            <div className="relative aspect-video bg-zinc-100 dark:bg-zinc-800">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={`https://i.ytimg.com/vi/${v.id}/mqdefault.jpg`} alt="" className="w-full h-full object-cover group-hover:opacity-90 transition" />
              {swapping === v.id && (
                <div className="absolute inset-0 flex items-center justify-center bg-black/40">
                  <div className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
                </div>
              )}
            </div>
            <div className="p-2">
              <p className="text-xs font-medium text-zinc-900 dark:text-white line-clamp-2 leading-snug">{v.title}</p>
              <p className="text-xs text-zinc-500 mt-0.5">
                {v.channel_name}
                {v.duration_sec && ` · ${formatDuration(Math.round(v.duration_sec / 60), Math.round(v.duration_sec / 60))}`}
              </p>
            </div>
          </button>
        ))}
      </div>
    )
  );

  // Mobile: bottom sheet
  if (isMobile) {
    return (
      <>
        <div className="fixed inset-0 z-40 bg-black/50" onClick={onClose} />
        <div
          ref={pickerRef}
          data-testid={`swap-picker-${day}`}
          className="fixed bottom-0 left-0 right-0 z-50 flex flex-col rounded-t-2xl bg-white dark:bg-zinc-900 border-t border-zinc-200 dark:border-zinc-700 max-h-[80vh]"
        >
          <div className="flex justify-center pt-3 pb-1 shrink-0">
            <div className="w-10 h-1 rounded-full bg-zinc-300 dark:bg-zinc-600" />
          </div>
          {header}
          <div className="overflow-y-auto">{videoGrid(false)}</div>
        </div>
      </>
    );
  }

  // Desktop: centered modal
  return (
    <>
      <div className="fixed inset-0 z-40 bg-black/50" onClick={onClose} />
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4 pointer-events-none">
        <div
          ref={pickerRef}
          data-testid={`swap-picker-${day}`}
          className="pointer-events-auto w-full max-w-2xl max-h-[80vh] flex flex-col rounded-2xl border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-900 shadow-2xl overflow-hidden"
        >
          {header}
          <div className="overflow-y-auto">{videoGrid(true)}</div>
        </div>
      </div>
    </>
  );
}

// ─── Rest day messages ────────────────────────────────────────────────────────

const REST_MESSAGES: Record<string, string[]> = {
  senior: [
    "Rest well today. Your body does its best work when you slow down.",
    "Active rest counts - gentle movement, hydration, good sleep.",
    "Recovery is where the work settles in.",
    "Ease off today. Back at it tomorrow.",
    "Rest, recover, repeat.",
    "Let the good work from this week settle.",
    "A gentle walk counts as rest day activity.",
    "Recovery day. You've earned it.",
    "Your joints are thanking you right now.",
    "Slow days make the active days better.",
  ],
  athlete: [
    "Supercompensation in progress.",
    "Recovery is training.",
    "Adaptation happens here.",
    "Your CNS thanks you.",
    "Today's load: zero. Tomorrow's output: higher.",
    "The work you did needs time to stick.",
    "Active rest. Light movement, sleep, hydration.",
    "Earned rest is the foundation of performance.",
    "You don't get stronger during the workout. You get stronger after.",
    "Sleep is the best legal performance enhancer.",
  ],
  default: [
    "Rest day. No guilt required.",
    "Muscles grow on rest days, not workout days.",
    "Recovery is part of the program.",
    "The best workout of the week.",
    "Today the plan is: do nothing. You've earned it.",
    "Your muscles are literally growing right now.",
    "Walk, stretch, sleep. Repeat.",
    "Rest is not the absence of training. It's part of it.",
    "Today: rest. Tomorrow: back at it.",
    "Earned rest is the best rest.",
    "This is not a gap in the plan. This is the plan.",
    "Recovery day. The hard part is trusting it.",
  ],
};

function pickRestMessage(pool: string[], day: string, weekStart: string): string {
  const key = `${weekStart}-${day}`;
  let hash = 0;
  for (let i = 0; i < key.length; i++) {
    hash = (hash * 31 + key.charCodeAt(i)) >>> 0;
  }
  return pool[hash % pool.length];
}

function RestDayCard({ day, weekStart, profile }: { day: string; weekStart: string; profile: string | null }) {
  const pool =
    profile === "senior" ? REST_MESSAGES.senior :
    profile === "athlete" ? REST_MESSAGES.athlete :
    REST_MESSAGES.default;
  const message = pickRestMessage(pool, day, weekStart);
  return (
    <div className="flex-1 flex flex-col rounded-lg overflow-hidden border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-900">
      <div className="aspect-video bg-zinc-50 dark:bg-zinc-800/60 flex items-center justify-center px-5">
        <p className="text-sm text-zinc-400 dark:text-zinc-500 leading-snug text-center">{message}</p>
      </div>
      <div className="p-3 flex-1">
        <p className="text-sm font-medium text-zinc-400 dark:text-zinc-500">Rest day</p>
      </div>
    </div>
  );
}

function MissingVideoCard({ workoutType }: { workoutType: string }) {
  const label = workoutType.charAt(0).toUpperCase() + workoutType.slice(1);
  return (
    <div className="flex-1 flex flex-col rounded-lg overflow-hidden border border-amber-200 dark:border-amber-800/50 bg-white dark:bg-zinc-900">
      <div className="aspect-video bg-amber-50/60 dark:bg-amber-900/10 flex items-center justify-center px-5">
        <p className="text-sm text-amber-600 dark:text-amber-400 leading-snug text-center">No {label} video found in your library.</p>
      </div>
      <div className="p-3 flex-1">
        <Link href="/settings" className="text-sm font-medium text-amber-600 dark:text-amber-500 hover:text-amber-800 dark:hover:text-amber-300 transition">
          Add channels in Settings →
        </Link>
      </div>
    </div>
  );
}

function VideoCard({ video }: { video: VideoSummary }) {
  return (
    <a
      href={video.url}
      target="_blank"
      rel="noopener noreferrer"
      className="group flex-1 flex flex-col rounded-lg overflow-hidden border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-900 hover:border-zinc-400 dark:hover:border-zinc-500 transition"
    >
      {/* Thumbnail */}
      <div className="relative aspect-video bg-zinc-100 dark:bg-zinc-800">
        {/* YouTube thumbnail via video ID */}
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={`https://i.ytimg.com/vi/${video.id}/mqdefault.jpg`}
          alt={video.title}
          className="w-full h-full object-cover"
        />
        {video.duration_sec && (
          <span className="absolute bottom-1.5 right-1.5 rounded bg-black/70 px-1.5 py-0.5 text-xs text-white">
            {formatDuration(Math.round(video.duration_sec / 60), Math.round(video.duration_sec / 60))}
          </span>
        )}
      </div>

      {/* Info */}
      <div className="p-3 space-y-2 flex-1">
        <p className="text-sm font-medium text-zinc-900 dark:text-white leading-snug line-clamp-2 group-hover:text-zinc-700 dark:group-hover:text-zinc-200">
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


export default function DashboardPage() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [plan, setPlan] = useState<PlanResponse | null>(null);
  const [hasChannels, setHasChannels] = useState(true);
  const [scanning, setScanning] = useState(false);
  const [pipelineStage, setPipelineStage] = useState<string | null>(null);
  const [classifyProgress, setClassifyProgress] = useState<{ total: number; done: number } | null>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [publishStatus, setPublishStatus] = useState<PublishStatus | null>(null);
  const publishPollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const [announcement, setAnnouncement] = useState<{ id: number; message: string } | null>(null);
  const [stalePlanDismissed, setStalePlanDismissed] = useState(false);
  const [alreadySetUpDismissed, setAlreadySetUpDismissed] = useState(false);
  const [showAlreadySetUp, setShowAlreadySetUp] = useState(false);
  const [openSwapDay, setOpenSwapDay] = useState<string | null>(null);
  const [screenshotMode, setScreenshotMode] = useState(false);
  const [error, setError] = useState("");
  const [missingTypesDismissed, setMissingTypesDismissed] = useState(false);
  const [youtubeJustConnected, setYoutubeJustConnected] = useState(false);
  const [profileNudgeDismissed, setProfileNudgeDismissed] = useState(false);

  useEffect(() => {
    // Check if we just came from onboarding with a scan in progress
    const params = new URLSearchParams(window.location.search);
    // Extract token if we arrived directly from OAuth callback
    const token = params.get("token");
    if (token) setToken(token);
    const scanJustTriggered = params.get("scanning") === "1";
    const fromOnboarding = params.get("from") === "onboarding";
    if (params.get("screenshot") === "1") setScreenshotMode(true);
    if (params.get("youtube") === "connected") setYoutubeJustConnected(true);
    if (scanJustTriggered) {
      setScanning(true);
    }
    if (fromOnboarding) {
      setShowAlreadySetUp(true);
    }
    if (token || scanJustTriggered || fromOnboarding || params.get("youtube") === "connected") {
      window.history.replaceState({}, "", window.location.pathname);
    }

    Promise.all([
      getMe(),
      getUpcomingPlan().catch(() => null),
      getChannels().catch(() => []),
      getJobStatus().catch(() => ({ stage: null, total: null, done: null })),
      getActiveAnnouncement().catch(() => null),
    ])
      .then(([u, p, channels, status, ann]) => {
        setUser(u);
        setPlan(p);
        setHasChannels(channels.length > 0);
        setAnnouncement(ann);
        const activeStages = ["scanning", "classifying", "generating"];
        if (status.stage && activeStages.includes(status.stage)) {
          // Pipeline is actively running - show scanning state regardless of
          // whether a stale plan already exists in the DB
          setScanning(true);
          setPipelineStage(status.stage);
        } else if (p) {
          setScanning(false);
        }
      })
      .catch(() => router.replace("/"))
      .finally(() => setLoading(false));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Poll for status every 5s while scanning; stop when pipeline reports done/failed/null
  useEffect(() => {
    if (!scanning) return;
    const interval = setInterval(async () => {
      try {
        const { stage, total, done } = await getJobStatus();
        setPipelineStage((prev) => prev === stage ? prev : stage);
        if (stage === "classifying" && total !== null && done !== null) {
          setClassifyProgress((prev) =>
            prev?.total === total && prev?.done === done ? prev : { total, done }
          );
        } else {
          setClassifyProgress(null);
        }
        // Pipeline finished - fetch fresh plan and stop polling
        if (!stage || stage === "done" || stage === "failed") {
          setScanning(false);
          setPipelineStage(null);
          setClassifyProgress(null);
          const p = await getUpcomingPlan().catch(() => null);
          if (p) setPlan(p);
        }
      } catch {
        // network blip - keep polling
      }
    }, 5_000);
    return () => clearInterval(interval);
  }, [scanning]);

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

  // Close swap picker on Esc
  useEffect(() => {
    if (!openSwapDay) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpenSwapDay(null);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [openSwapDay]);

  // Cleanup publish poll on unmount
  useEffect(() => {
    return () => {
      if (publishPollRef.current) clearInterval(publishPollRef.current);
    };
  }, []);

  async function handleSwap(day: string, video: VideoSummary) {
    await swapPlanDay(day, video.id);
    setPlan((p) =>
      p ? { ...p, days: p.days.map((d) => (d.day === day ? { ...d, video } : d)) } : p
    );
    setOpenSwapDay(null);
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
    setPublishStatus({ status: "publishing" });
    setError("");
    try {
      await publishPlan();
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Failed to start publish";
      setPublishStatus({ status: "failed", error: msg });
      return;
    }

    // Poll for completion
    publishPollRef.current = setInterval(async () => {
      try {
        const s = await getPublishStatus();
        setPublishStatus(s);
        if (s.status === "done" || s.status === "failed") {
          if (publishPollRef.current) {
            clearInterval(publishPollRef.current);
            publishPollRef.current = null;
          }
          if (s.status === "done") {
            setUser((u) => u ? { ...u, credentials_valid: true } : u);
          }
          if (s.status === "failed" && s.error === "revoked") {
            setUser((u) => u ? { ...u, credentials_valid: false } : u);
          }
        }
      } catch {
        // ignore poll errors
      }
    }, 2000);
  }

  async function handleLogout() {
    await logout();
    router.replace("/");
  }

  if (loading) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-white dark:bg-zinc-950">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-zinc-300 border-t-zinc-900 dark:border-zinc-600 dark:border-t-white" />
      </main>
    );
  }

  const allDaysEmpty = plan && plan.days.every((d: PlanDay) => !d.video);

  const EIGHT_WEEKS_MS = 56 * 24 * 60 * 60 * 1000;
  const showProfileNudge = (() => {
    if (!user?.profile || !user?.created_at) return false;
    if (profileNudgeDismissed) return false;
    const signedUpMs = new Date(user.created_at).getTime();
    if (Date.now() - signedUpMs < EIGHT_WEEKS_MS) return false;
    const dismissedAt = typeof window !== "undefined"
      ? localStorage.getItem("profile_nudge_dismissed_at")
      : null;
    if (dismissedAt && Date.now() - parseInt(dismissedAt) < EIGHT_WEEKS_MS) return false;
    return true;
  })();

  const LIFE_STAGE_LABELS: Record<string, string> = {
    beginner: "Just starting out",
    adult: "Active adult",
    senior: "55 and thriving",
    athlete: "Training seriously",
  };

  // True when plan.week_start is from a previous week
  const isPlanStale = (() => {
    if (!plan) return false;
    const today = new Date();
    const dayOfWeek = today.getDay(); // 0=Sun, 1=Mon…
    const daysToMonday = dayOfWeek === 0 ? -6 : 1 - dayOfWeek;
    const monday = new Date(today);
    monday.setDate(today.getDate() + daysToMonday);
    const currentWeekISO = monday.toISOString().slice(0, 10);
    return plan.week_start < currentWeekISO;
  })();

  const weekLabel = plan
    ? new Date(plan.week_start + "T00:00:00").toLocaleDateString("en-GB", {
        day: "numeric",
        month: "short",
        year: "numeric",
      })
    : null;

  return (
    <main className="min-h-screen bg-white dark:bg-zinc-950 px-4 py-8">
      <div className="max-w-5xl mx-auto">

        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between mb-8 gap-4">
          <div>
            <h1 className="text-2xl font-bold text-zinc-900 dark:text-white">
              {screenshotMode ? "Your plan" : (user?.display_name ? `${user.display_name.split(" ")[0]}'s plan` : "Your plan")}
            </h1>
            {!screenshotMode && weekLabel && (
              <p className="text-zinc-500 text-sm mt-0.5">Week of {weekLabel}</p>
            )}
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Link
              href="/library"
              className="rounded-lg border border-zinc-200 dark:border-zinc-700 px-3 py-2 text-sm text-zinc-600 dark:text-zinc-400 hover:bg-zinc-100 dark:hover:bg-zinc-800 transition"
            >
              Library
            </Link>
            <Link
              href="/settings"
              className="rounded-lg border border-zinc-200 dark:border-zinc-700 px-3 py-2 text-sm text-zinc-600 dark:text-zinc-400 hover:bg-zinc-100 dark:hover:bg-zinc-800 transition"
            >
              Settings
            </Link>
            {user?.is_admin && (
              <Link
                href="/admin"
                className="rounded-lg border border-zinc-200 dark:border-zinc-700 px-3 py-2 text-sm text-zinc-600 dark:text-zinc-400 hover:bg-zinc-100 dark:hover:bg-zinc-800 transition"
              >
                Admin
              </Link>
            )}
            {plan && !allDaysEmpty ? (
              <button
                onClick={handleGenerate}
                disabled={generating}
                className="rounded-lg bg-zinc-900 dark:bg-white px-3 py-2 text-sm font-semibold text-white dark:text-zinc-900 hover:bg-zinc-700 dark:hover:bg-zinc-100 disabled:opacity-40 cursor-pointer transition"
              >
                {generating ? "Generating…" : "Regenerate"}
              </button>
            ) : (
              <button
                onClick={handleScan}
                disabled={generating || scanning}
                className="rounded-lg bg-zinc-900 dark:bg-white px-3 py-2 text-sm font-semibold text-white dark:text-zinc-900 hover:bg-zinc-700 dark:hover:bg-zinc-100 disabled:opacity-40 cursor-pointer transition"
              >
                {generating ? "Starting…" : allDaysEmpty ? "Rescan channels" : "Generate plan"}
              </button>
            )}
            {!user?.youtube_connected ? (
              <a
                href={youtubeConnectUrl()}
                className="rounded-lg border border-red-600 bg-red-600/10 px-3 py-2 text-sm font-medium text-red-400 hover:bg-red-600/20 transition"
              >
                Connect YouTube
              </a>
            ) : user?.youtube_connected && !user?.credentials_valid ? (
              <a
                href={youtubeConnectUrl()}
                title="Your YouTube access was revoked - click to reconnect"
                className="rounded-lg border border-amber-500 bg-amber-500/10 px-3 py-2 text-sm font-medium text-amber-400 hover:bg-amber-500/20 transition"
              >
                Reconnect YouTube
              </a>
            ) : plan ? (
              <button
                onClick={handlePublish}
                disabled={publishStatus?.status === "publishing"}
                className="rounded-lg border border-red-600 bg-red-600/10 px-3 py-2 text-sm font-medium text-red-400 hover:bg-red-600/20 disabled:opacity-40 cursor-pointer transition"
              >
                {publishStatus?.status === "publishing" ? "Publishing…" : "Publish to YouTube"}
              </button>
            ) : (
              <button
                disabled
                title="Generate a plan first"
                className="rounded-lg border border-zinc-200 dark:border-zinc-700 px-3 py-2 text-sm text-zinc-500 dark:text-zinc-600 opacity-50 cursor-not-allowed transition"
              >
                Publish to YouTube
              </button>
            )}
            <button
              onClick={() => { throw new Error("Sentry frontend test - delete me") }}
              className="rounded-lg border border-red-300 px-3 py-2 text-sm text-red-500 cursor-pointer"
            >
              Sentry test
            </button>
            <button
              onClick={handleLogout}
              className="rounded-lg border border-zinc-200 dark:border-zinc-700 px-3 py-2 text-sm text-zinc-600 dark:text-zinc-400 hover:bg-zinc-100 dark:hover:bg-zinc-800 cursor-pointer transition"
            >
              Sign out
            </button>
          </div>
        </div>

        {/* YouTube connected banner */}
        {youtubeJustConnected && (
          <div className="mb-6 flex items-center justify-between gap-3 rounded-lg border border-green-700 bg-green-900/20 px-4 py-3 text-sm text-green-300">
            <span>YouTube connected. You can now publish your plan directly to your YouTube playlist.</span>
            <button onClick={() => setYoutubeJustConnected(false)} aria-label="Dismiss" className="shrink-0 text-green-500 hover:text-green-300 transition">✕</button>
          </div>
        )}

        {/* Already set up banner - shown when user tried to access /onboarding */}
        {showAlreadySetUp && !alreadySetUpDismissed && (
          <div className="mb-6 flex items-center justify-between gap-3 rounded-lg border border-zinc-300 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-800/60 px-4 py-3 text-sm text-zinc-700 dark:text-zinc-300">
            <span>You&apos;re already all set. Head to <Link href="/settings" className="underline hover:text-zinc-900 dark:hover:text-white transition">Settings</Link> to update your channels or schedule.</span>
            <button onClick={() => setAlreadySetUpDismissed(true)} aria-label="Dismiss" className="shrink-0 text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-200 transition">✕</button>
          </div>
        )}

        {/* Missing workout types banner - shown when active schedule days have no matching videos */}
        {(() => {
          if (!plan || missingTypesDismissed) return null;
          const missing = [...new Set(
            plan.days
              .filter(d => !d.video && d.scheduled_workout_type)
              .map(d => d.scheduled_workout_type!)
          )];
          if (missing.length === 0) return null;
          const typeList = missing.map(t => t.charAt(0).toUpperCase() + t.slice(1)).join(", ");
          return (
            <div className="mb-6 flex items-center justify-between gap-3 rounded-lg border border-amber-200 dark:border-amber-800/60 bg-amber-50 dark:bg-amber-900/20 px-4 py-3 text-sm text-amber-800 dark:text-amber-300">
              <span>Some days couldn&apos;t be filled - your library has no <strong>{typeList}</strong> videos. Try adding channels that cover these workout types, or update your schedule in <Link href="/settings" className="underline hover:text-amber-900 dark:hover:text-amber-100 transition">Settings</Link>.</span>
              <button onClick={() => setMissingTypesDismissed(true)} aria-label="Dismiss" className="shrink-0 text-amber-400 hover:text-amber-600 dark:hover:text-amber-200 transition">✕</button>
            </div>
          );
        })()}

        {/* Announcement banner */}
        {announcement && (
          <div className="mb-6 flex items-start justify-between gap-3 rounded-lg border border-blue-800 bg-blue-900/20 px-4 py-3 text-sm text-blue-300">
            <span>{announcement.message}</span>
            <button onClick={() => setAnnouncement(null)} className="shrink-0 text-blue-500 hover:text-blue-300 transition">✕</button>
          </div>
        )}

        {/* Profile nudge banner - shown after 8 weeks to prompt profile review */}
        {showProfileNudge && (
          <div className="mb-6 flex items-center justify-between gap-3 rounded-lg border border-zinc-300 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-800/60 px-4 py-3 text-sm text-zinc-700 dark:text-zinc-300">
            <span>
              Your fitness profile is set to <strong>{LIFE_STAGE_LABELS[user!.profile!] ?? user!.profile}</strong> - <strong>{user!.goal!.join(", ")}</strong>. Still accurate?{" "}
              <Link href="/settings" className="underline hover:text-zinc-900 dark:hover:text-white transition">
                Update in Settings →
              </Link>
            </span>
            <button
              onClick={() => {
                localStorage.setItem("profile_nudge_dismissed_at", Date.now().toString());
                setProfileNudgeDismissed(true);
              }}
              aria-label="Dismiss"
              className="shrink-0 text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-200 transition"
            >
              ✕
            </button>
          </div>
        )}

        {/* Stale plan banner */}
        {isPlanStale && !stalePlanDismissed && !scanning && (
          <div className="mb-6 flex items-center justify-between gap-3 rounded-lg border border-zinc-300 dark:border-zinc-600 bg-zinc-50 dark:bg-zinc-800/60 px-4 py-3 text-sm text-zinc-700 dark:text-zinc-300">
            <span>
              Welcome back! Your plan is from a previous week.{" "}
              <button
                onClick={async () => {
                  setStalePlanDismissed(true);
                  await handleGenerate();
                }}
                disabled={generating}
                className="font-semibold underline hover:text-zinc-900 dark:hover:text-white disabled:opacity-40 transition"
              >
                Generate a fresh plan →
              </button>
            </span>
            <button
              onClick={() => setStalePlanDismissed(true)}
              className="shrink-0 text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-200 transition"
            >
              ✕
            </button>
          </div>
        )}

        {/* Generate in progress banner */}
        {generating && !scanning && (
          <div className="mb-6 flex items-center gap-3 rounded-lg border border-zinc-200 dark:border-zinc-700 bg-zinc-100/60 dark:bg-zinc-800/60 px-4 py-3 text-sm text-zinc-700 dark:text-zinc-300">
            <svg className="h-4 w-4 animate-spin shrink-0 text-zinc-600 dark:text-zinc-400" viewBox="0 0 24 24" fill="none">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"/>
            </svg>
            <span>Generating your plan - picking the best videos for each day…</span>
          </div>
        )}

        {/* Scan in progress banner */}
        {scanning && (
          <div className="mb-6 rounded-lg border border-zinc-200 dark:border-zinc-700 bg-zinc-100/60 dark:bg-zinc-800/60 px-4 py-3 text-sm text-zinc-700 dark:text-zinc-300 space-y-2">
            <div className="flex items-center gap-3">
              <svg className="h-4 w-4 animate-spin shrink-0 text-zinc-600 dark:text-zinc-400" viewBox="0 0 24 24" fill="none">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"/>
              </svg>
              <span>
                {pipelineStage === "scanning" && "Scanning your channels for new videos…"}
                {pipelineStage === "classifying" && (
                  classifyProgress
                    ? classifyProgress.done < 0
                      ? `Preparing batch - fetching transcripts (${Math.abs(classifyProgress.done).toLocaleString()} / ${classifyProgress.total.toLocaleString()})`
                      : `Classifying videos with AI - ${classifyProgress.done.toLocaleString()} / ${classifyProgress.total.toLocaleString()} done`
                    : "Classifying videos with AI - preparing batch…"
                )}
                {pipelineStage === "generating" && "Almost done - generating your weekly plan…"}
                {pipelineStage === "failed" && "Something went wrong. Try rescanning from the button above."}
                {(!pipelineStage || pipelineStage === "done") && "Starting pipeline - your plan will appear automatically when ready."}
              </span>
            </div>
            {pipelineStage === "classifying" && classifyProgress && (
              <div className="w-full bg-zinc-200 dark:bg-zinc-700 rounded-full h-1.5">
                <div
                  className="bg-zinc-900 dark:bg-white h-1.5 rounded-full transition-all duration-500"
                  style={{ width: `${Math.round((Math.abs(classifyProgress.done) / classifyProgress.total) * 100)}%` }}
                />
              </div>
            )}
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

        {/* Publishing in progress banner */}
        {publishStatus?.status === "publishing" && (
          <div className="mb-6 rounded-lg border border-zinc-700 bg-zinc-800/50 px-4 py-3 text-sm text-zinc-300">
            Publishing your plan to YouTube...
          </div>
        )}

        {/* Publish failed banner */}
        {publishStatus?.status === "failed" && publishStatus.error !== "revoked" && (
          <div className="mb-6 rounded-lg border border-red-800 bg-red-900/30 px-4 py-3 text-sm text-red-400">
            {publishStatus.error ?? "Failed to publish plan"}
          </div>
        )}

        {/* Publish success banner */}
        {publishStatus?.status === "done" && (
          <div className="mb-6 rounded-lg border border-green-800 bg-green-900/20 px-4 py-3 text-sm text-green-400 flex items-center justify-between">
            <span>
              Plan published - {publishStatus.video_count!} video{publishStatus.video_count !== 1 ? "s" : ""} added to your playlist.
            </span>
            <a
              href={publishStatus.playlist_url!}
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
          <div className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900 p-12 text-center">
            {!hasChannels ? (
              <>
                <p className="text-zinc-600 dark:text-zinc-400 text-sm mb-4">
                  Add your favourite YouTube fitness channels to get started.
                </p>
                <Link
                  href="/onboarding"
                  className="inline-block rounded-lg bg-zinc-900 dark:bg-white px-5 py-2.5 text-sm font-semibold text-white dark:text-zinc-900 hover:bg-zinc-700 dark:hover:bg-zinc-100 transition"
                >
                  Set up my plan →
                </Link>
              </>
            ) : scanning ? (
              <p className="text-zinc-500 text-sm">Hang tight - building your plan in the background…</p>
            ) : (
              <>
                <p className="text-zinc-600 dark:text-zinc-400 text-sm mb-4">No plan generated yet.</p>
                <button
                  onClick={handleScan}
                  disabled={generating}
                  className="rounded-lg bg-zinc-900 dark:bg-white px-5 py-2.5 text-sm font-semibold text-white dark:text-zinc-900 hover:bg-zinc-700 dark:hover:bg-zinc-100 disabled:opacity-40 cursor-pointer transition"
                >
                  {generating ? "Starting scan…" : "Scan channels & generate plan"}
                </button>
              </>
            )}
          </div>
        )}

        {/* Plan grid */}
        {plan && (
          <>
          <p className="text-xs text-zinc-500 dark:text-zinc-600 mb-3 text-right">✦ Curated by AI</p>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {plan.days.map((day: PlanDay) => (
              <div key={day.day} className="flex flex-col">
                <p className="text-xs font-semibold text-zinc-500 uppercase tracking-wide mb-2">
                  {DAY_LABELS[day.day] ?? day.day}
                </p>
                {day.video ? (
                  <>
                    <VideoCard video={day.video} />
                    <button
                      onClick={() => setOpenSwapDay(openSwapDay === day.day ? null : day.day)}
                      className="mt-1.5 w-full text-xs text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-300 transition py-1 cursor-pointer"
                    >
                      {openSwapDay === day.day ? "Cancel" : "Swap video"}
                    </button>
                    {openSwapDay === day.day && (
                      <SwapPicker
                        day={day.day}
                        workoutType={day.video.workout_type}
                        currentVideoId={day.video.id}
                        onSwap={(video) => handleSwap(day.day, video)}
                        onClose={() => setOpenSwapDay(null)}
                      />
                    )}
                  </>
                ) : day.scheduled_workout_type ? (
                  <>
                    <MissingVideoCard workoutType={day.scheduled_workout_type} />
                    <div className="mt-1.5 h-6" />
                  </>
                ) : (
                  <>
                    <RestDayCard day={day.day} weekStart={plan.week_start} profile={user?.profile ?? null} />
                    <div className="mt-1.5 h-6" />
                  </>
                )}
              </div>
            ))}
          </div>
          </>
        )}

      </div>
      <Footer />
      <FeedbackWidget />
    </main>
  );
}
