"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Footer } from "@/components/Footer";
import {
  getMe,
  getChannels,
  getLibrary,
  swapPlanDay,
  type VideoSummary,
  type LibraryResponse,
  type ChannelResponse,
} from "@/lib/api";
import { DAY_LABELS, formatDuration } from "@/lib/utils";
import Badge from "@/components/Badge";

const DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday"];

// Values match what the classifier stores (case-insensitive comparison on backend)
const WORKOUT_TYPES = ["strength", "hiit", "cardio", "mobility"];
const WORKOUT_TYPE_LABELS: Record<string, string> = {
  strength: "Strength",
  hiit: "HIIT",
  cardio: "Cardio",
  mobility: "Mobility",
};
const BODY_FOCUSES = ["full", "upper", "lower", "core", "arms", "legs", "back"];
const DIFFICULTIES = ["beginner", "intermediate", "advanced"];

function AssignButton({ videoId }: { videoId: string }) {
  const [selected, setSelected] = useState("");
  const [status, setStatus] = useState<"idle" | "loading" | "ok" | "err">("idle");
  const [assignedDay, setAssignedDay] = useState("");

  async function handleAssign(day: string) {
    if (!day) return;
    setStatus("loading");
    try {
      await swapPlanDay(day, videoId);
      setAssignedDay(DAY_LABELS[day]);
      setStatus("ok");
      setSelected("");
      setTimeout(() => setStatus("idle"), 2000);
    } catch {
      setStatus("err");
      setSelected("");
      setTimeout(() => setStatus("idle"), 2000);
    }
  }

  if (status === "ok") {
    return (
      <span className="text-xs text-green-400">✓ Assigned to {assignedDay}</span>
    );
  }
  if (status === "err") {
    return <span className="text-xs text-red-400">Failed — generate a plan first</span>;
  }

  return (
    <select
      value={selected}
      onChange={(e) => handleAssign(e.target.value)}
      disabled={status === "loading"}
      className="w-full rounded bg-zinc-800 border border-zinc-700 px-2 py-1 text-xs text-zinc-400 disabled:opacity-40 focus:outline-none focus:border-zinc-500"
    >
      <option value="">Assign to day…</option>
      {DAYS.map((d) => (
        <option key={d} value={d}>
          {DAY_LABELS[d]}
        </option>
      ))}
    </select>
  );
}

function VideoCard({ video }: { video: VideoSummary }) {
  return (
    <div className="rounded-lg overflow-hidden border border-zinc-700 bg-zinc-900 flex flex-col">
      <a
        href={video.url}
        target="_blank"
        rel="noopener noreferrer"
        className="group block"
      >
        <div className="relative aspect-video bg-zinc-800">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={`https://i.ytimg.com/vi/${video.id}/mqdefault.jpg`}
            alt={video.title}
            className="w-full h-full object-cover group-hover:opacity-90 transition"
          />
          {video.duration_sec && (
            <span className="absolute bottom-1.5 right-1.5 rounded bg-black/80 px-1.5 py-0.5 text-xs text-white">
              {formatDuration(Math.round(video.duration_sec / 60), Math.round(video.duration_sec / 60))}
            </span>
          )}
        </div>
        <div className="p-3 pb-2">
          <p className="text-sm font-medium text-white leading-snug line-clamp-2 group-hover:text-zinc-200 mb-1">
            {video.title}
          </p>
          <p className="text-xs text-zinc-500 mb-2">{video.channel_name}</p>
          <div className="flex flex-wrap gap-1.5">
            {video.workout_type && <Badge label={video.workout_type} />}
            {video.body_focus && <Badge label={video.body_focus} />}
            {video.difficulty && video.difficulty !== "any" && <Badge label={video.difficulty} />}
          </div>
        </div>
      </a>
      <div className="px-3 pb-3 mt-auto">
        <AssignButton videoId={video.id} />
      </div>
    </div>
  );
}

function FilterSelect({
  label,
  value,
  options,
  labels,
  onChange,
}: {
  label: string;
  value: string;
  options: string[];
  labels?: Record<string, string>;
  onChange: (v: string) => void;
}) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="rounded-lg bg-zinc-900 border border-zinc-700 px-3 py-2 text-sm text-zinc-300 focus:outline-none focus:border-zinc-500"
    >
      <option value="">{label}</option>
      {options.map((o) => (
        <option key={o} value={o}>
          {labels?.[o] ?? o.charAt(0).toUpperCase() + o.slice(1)}
        </option>
      ))}
    </select>
  );
}

export default function LibraryPage() {
  const router = useRouter();
  const [channels, setChannels] = useState<ChannelResponse[]>([]);
  const [data, setData] = useState<LibraryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // Filters
  const [workoutType, setWorkoutType] = useState("");
  const [bodyFocus, setBodyFocus] = useState("");
  const [difficulty, setDifficulty] = useState("");
  const [channelId, setChannelId] = useState("");
  const [page, setPage] = useState(1);

  const fetchLibrary = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const result = await getLibrary({
        workout_type: workoutType || undefined,
        body_focus: bodyFocus || undefined,
        difficulty: difficulty || undefined,
        channel_id: channelId || undefined,
        page,
      });
      setData(result);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load library");
    } finally {
      setLoading(false);
    }
  }, [workoutType, bodyFocus, difficulty, channelId, page]);

  useEffect(() => {
    getMe().catch(() => router.replace("/"));
    getChannels().then(setChannels).catch(() => {});
  }, [router]);

  useEffect(() => {
    fetchLibrary();
  }, [fetchLibrary]);

  function applyFilter(setter: (v: string) => void, value: string) {
    setter(value);
    setPage(1);
  }

  function clearFilters() {
    setWorkoutType("");
    setBodyFocus("");
    setDifficulty("");
    setChannelId("");
    setPage(1);
  }

  const hasFilters = workoutType || bodyFocus || difficulty || channelId;

  return (
    <main className="min-h-screen bg-zinc-950 px-4 py-8">
      <div className="max-w-6xl mx-auto">

        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div className="flex items-center gap-4">
            <Link
              href="/dashboard"
              className="text-zinc-500 hover:text-zinc-300 text-sm transition"
            >
              ← Back
            </Link>
            <h1 className="text-2xl font-bold text-white">Video Library</h1>
          </div>
          {data && (
            <p className="text-sm text-zinc-500">{data.total.toLocaleString()} videos</p>
          )}
        </div>

        {/* Filters */}
        <div className="flex flex-wrap items-center gap-3 mb-6">
          <FilterSelect
            label="Workout type"
            value={workoutType}
            options={WORKOUT_TYPES}
            labels={WORKOUT_TYPE_LABELS}
            onChange={(v) => applyFilter(setWorkoutType, v)}
          />
          <FilterSelect
            label="Body focus"
            value={bodyFocus}
            options={BODY_FOCUSES}
            onChange={(v) => applyFilter(setBodyFocus, v)}
          />
          <FilterSelect
            label="Difficulty"
            value={difficulty}
            options={DIFFICULTIES}
            onChange={(v) => applyFilter(setDifficulty, v)}
          />
          {channels.length > 1 && (
            <select
              value={channelId}
              onChange={(e) => applyFilter(setChannelId, e.target.value)}
              className="rounded-lg bg-zinc-900 border border-zinc-700 px-3 py-2 text-sm text-zinc-300 focus:outline-none focus:border-zinc-500"
            >
              <option value="">All channels</option>
              {channels.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          )}
          {hasFilters && (
            <button
              onClick={clearFilters}
              className="text-sm text-zinc-500 hover:text-zinc-300 transition"
            >
              Clear filters
            </button>
          )}
        </div>

        {error && (
          <div className="mb-6 rounded-lg border border-red-800 bg-red-900/30 px-4 py-3 text-sm text-red-400">
            {error}
          </div>
        )}

        {/* Grid */}
        {loading ? (
          <div className="flex justify-center py-24">
            <div className="h-8 w-8 animate-spin rounded-full border-4 border-zinc-600 border-t-white" />
          </div>
        ) : data && data.videos.length > 0 ? (
          <>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              {data.videos.map((video) => (
                <VideoCard key={video.id} video={video} />
              ))}
            </div>

            {/* Pagination */}
            {data.pages > 1 && (
              <div className="flex items-center justify-center gap-4 mt-8">
                <button
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page === 1}
                  className="rounded-lg border border-zinc-700 px-4 py-2 text-sm text-zinc-400 hover:bg-zinc-800 disabled:opacity-30 transition"
                >
                  Previous
                </button>
                <span className="text-sm text-zinc-500">
                  Page {data.page} of {data.pages}
                </span>
                <button
                  onClick={() => setPage((p) => Math.min(data.pages, p + 1))}
                  disabled={page === data.pages}
                  className="rounded-lg border border-zinc-700 px-4 py-2 text-sm text-zinc-400 hover:bg-zinc-800 disabled:opacity-30 transition"
                >
                  Next
                </button>
              </div>
            )}
          </>
        ) : (
          <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-12 text-center">
            <p className="text-zinc-400 text-sm">
              {hasFilters
                ? "No videos match these filters."
                : "No videos in your library yet. Generate a plan to scan your channels."}
            </p>
            {hasFilters && (
              <button
                onClick={clearFilters}
                className="mt-4 text-sm text-zinc-500 hover:text-zinc-300 transition"
              >
                Clear filters
              </button>
            )}
          </div>
        )}

      </div>
      <Footer />
    </main>
  );
}
