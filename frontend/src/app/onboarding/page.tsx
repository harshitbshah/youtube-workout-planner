"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import {
  updateSchedule,
  triggerScan,
  type ChannelResponse,
  type ScheduleSlot,
} from "@/lib/api";
import ChannelManager from "@/components/ChannelManager";
import ScheduleEditor from "@/components/ScheduleEditor";

const DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"];

const DEFAULT_SCHEDULE: ScheduleSlot[] = [
  { day: "monday",    workout_type: "strength", body_focus: "upper", duration_min: 30, duration_max: 45, difficulty: "any" },
  { day: "tuesday",   workout_type: "hiit",     body_focus: "full",  duration_min: 30, duration_max: 45, difficulty: "any" },
  { day: "wednesday", workout_type: "strength", body_focus: "lower", duration_min: 30, duration_max: 45, difficulty: "any" },
  { day: "thursday",  workout_type: "hiit",     body_focus: "core",  duration_min: 15, duration_max: 45, difficulty: "any" },
  { day: "friday",    workout_type: "strength", body_focus: "full",  duration_min: 30, duration_max: 45, difficulty: "any" },
  { day: "saturday",  workout_type: "cardio",   body_focus: "full",  duration_min: 30, duration_max: 45, difficulty: "any" },
  { day: "sunday",    workout_type: null,        body_focus: null,    duration_min: null, duration_max: null, difficulty: "any" },
];

function StepIndicator({ current }: { current: number }) {
  const steps = ["Channels", "Schedule", "Done"];
  return (
    <div className="flex items-center gap-3 mb-8">
      {steps.map((label, i) => {
        const step = i + 1;
        const active = step === current;
        const done = step < current;
        return (
          <div key={label} className="flex items-center gap-3">
            <div className="flex items-center gap-2">
              <div
                className={`h-7 w-7 rounded-full flex items-center justify-center text-xs font-bold transition-colors
                  ${active ? "bg-white text-zinc-900" : done ? "bg-zinc-600 text-white" : "bg-zinc-800 text-zinc-500"}`}
              >
                {done ? "✓" : step}
              </div>
              <span className={`text-sm ${active ? "text-white font-medium" : "text-zinc-500"}`}>
                {label}
              </span>
            </div>
            {i < steps.length - 1 && (
              <div className={`h-px w-8 ${done ? "bg-zinc-600" : "bg-zinc-800"}`} />
            )}
          </div>
        );
      })}
    </div>
  );
}

export default function OnboardingPage() {
  const router = useRouter();
  const [step, setStep] = useState(1);
  const [channels, setChannels] = useState<ChannelResponse[]>([]);
  const [schedule, setSchedule] = useState<ScheduleSlot[]>(DEFAULT_SCHEDULE);
  const [savingSchedule, setSavingSchedule] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState("");

  async function handleSaveSchedule() {
    setSavingSchedule(true);
    setError("");
    try {
      await updateSchedule(schedule);
      setStep(3);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to save schedule");
    } finally {
      setSavingSchedule(false);
    }
  }

  async function handleGenerateNow() {
    setGenerating(true);
    setError("");
    try {
      await triggerScan();
      router.push("/dashboard");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to start scan");
      setGenerating(false);
    }
  }

  return (
    <main className="min-h-screen bg-zinc-950 flex flex-col items-center justify-center px-4 py-12">
      <div className="w-full max-w-2xl">
        <StepIndicator current={step} />

        {error && (
          <div className="mb-6 rounded-lg border border-red-800 bg-red-900/30 px-4 py-3 text-sm text-red-400">
            {error}
          </div>
        )}

        {/* Step 1 — Channels */}
        {step === 1 && (
          <div className="w-full max-w-lg">
            <h2 className="text-xl font-semibold text-white mb-1">Add your favourite channels</h2>
            <p className="text-zinc-400 text-sm mb-6">
              Search for YouTube fitness channels to include in your plan.
            </p>
            <ChannelManager channels={channels} onChannelsChange={setChannels} />
            <button
              onClick={() => setStep(2)}
              disabled={channels.length === 0}
              className="w-full mt-6 rounded-lg bg-white px-4 py-3 text-sm font-semibold text-zinc-900 hover:bg-zinc-100 disabled:opacity-30 transition"
            >
              Continue →
            </button>
          </div>
        )}

        {/* Step 2 — Schedule */}
        {step === 2 && (
          <div className="w-full max-w-2xl">
            <h2 className="text-xl font-semibold text-white mb-1">Set your weekly schedule</h2>
            <p className="text-zinc-400 text-sm mb-6">
              Pre-filled with a balanced split. Adjust to fit your goals.
            </p>
            <ScheduleEditor schedule={schedule} onScheduleChange={setSchedule} />
            <div className="flex gap-3 mt-8">
              <button
                onClick={() => setStep(1)}
                className="rounded-lg border border-zinc-700 px-4 py-3 text-sm font-medium text-zinc-300 hover:bg-zinc-800 transition"
              >
                ← Back
              </button>
              <button
                onClick={handleSaveSchedule}
                disabled={savingSchedule}
                className="flex-1 rounded-lg bg-white px-4 py-3 text-sm font-semibold text-zinc-900 hover:bg-zinc-100 disabled:opacity-40 transition"
              >
                {savingSchedule ? "Saving…" : "Save schedule →"}
              </button>
            </div>
          </div>
        )}

        {/* Step 3 — Done */}
        {step === 3 && (
          <div className="w-full max-w-lg text-center">
            <div className="text-4xl mb-4">🎉</div>
            <h2 className="text-xl font-semibold text-white mb-2">You&apos;re all set!</h2>
            <p className="text-zinc-400 text-sm mb-6">
              Every Sunday your plan will be generated automatically from{" "}
              <span className="text-white font-medium">
                {channels.length} channel{channels.length !== 1 ? "s" : ""}
              </span>.
            </p>
            <div className="rounded-lg border border-zinc-700 bg-zinc-900 p-4 mb-8 text-left">
              <p className="text-xs text-zinc-500 uppercase tracking-wide mb-3">Your channels</p>
              <div className="flex flex-wrap gap-2">
                {channels.map((ch) => (
                  <span
                    key={ch.id}
                    className="rounded-full bg-zinc-800 border border-zinc-700 px-3 py-1 text-sm text-white"
                  >
                    {ch.name}
                  </span>
                ))}
              </div>
            </div>
            <button
              onClick={handleGenerateNow}
              disabled={generating}
              className="w-full rounded-lg bg-white px-4 py-3 text-sm font-semibold text-zinc-900 hover:bg-zinc-100 disabled:opacity-40 transition mb-3"
            >
              {generating ? "Scanning channels…" : "Generate my first plan now"}
            </button>
            <p className="text-xs text-zinc-600">
              This scans your channels and classifies videos — takes a minute or two.
            </p>
          </div>
        )}
      </div>
    </main>
  );
}
