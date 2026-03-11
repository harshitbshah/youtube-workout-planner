"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { useRouter } from "next/navigation";
import {
  updateSchedule,
  triggerScan,
  getJobStatus,
  type ChannelResponse,
  type ScheduleSlot,
} from "@/lib/api";
import ChannelManager from "@/components/ChannelManager";
import ScheduleEditor from "@/components/ScheduleEditor";
import { buildSchedule, type LifeStage, type SessionLength } from "@/lib/scheduleTemplates";
import { DAY_LABELS } from "@/lib/utils";

// ─── Step Indicator ───────────────────────────────────────────────────────────

function StepIndicator({ internalStep }: { internalStep: number }) {
  const steps = ["Profile", "Channels", "Your Plan"];
  const visibleStep = internalStep <= 5 ? 1 : internalStep === 6 ? 2 : 3;
  return (
    <div className="flex items-center gap-3 mb-8">
      {steps.map((label, i) => {
        const step = i + 1;
        const active = step === visibleStep;
        const done = step < visibleStep;
        return (
          <div key={label} className="flex items-center gap-3">
            <div className="flex items-center gap-2">
              <div className={`h-7 w-7 rounded-full flex items-center justify-center text-xs font-bold transition-colors ${active ? "bg-white text-zinc-900" : done ? "bg-zinc-600 text-white" : "bg-zinc-800 text-zinc-500"}`}>
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

// ─── Card Button ──────────────────────────────────────────────────────────────

function OptionCard({ label, sublabel, onClick }: { label: string; sublabel?: string; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="w-full text-left rounded-xl border border-zinc-700 bg-zinc-900 px-5 py-4 hover:border-zinc-500 hover:bg-zinc-800 transition"
    >
      <p className="font-medium text-white">{label}</p>
      {sublabel && <p className="text-sm text-zinc-400 mt-0.5">{sublabel}</p>}
    </button>
  );
}

// ─── Schedule Preview ─────────────────────────────────────────────────────────

const WORKOUT_LABELS: Record<string, string> = {
  strength: "Strength training",
  hiit:     "HIIT",
  cardio:   "Light cardio",
  mobility: "Mobility & stretching",
};

function SchedulePreview({ schedule, isSenior }: { schedule: ScheduleSlot[]; isSenior: boolean }) {
  const restLabel = isSenior ? "Recovery day" : "Rest day";
  return (
    <div className="rounded-xl border border-zinc-700 bg-zinc-900 divide-y divide-zinc-800 overflow-hidden">
      {schedule.map((slot) => (
        <div key={slot.day} className="flex items-center gap-4 px-5 py-3">
          <span className="w-8 text-sm font-medium text-zinc-400 shrink-0">{DAY_LABELS[slot.day]}</span>
          {slot.workout_type ? (
            <>
              <span className="text-sm text-white">{WORKOUT_LABELS[slot.workout_type] ?? slot.workout_type}</span>
              {slot.duration_min != null && slot.duration_max != null && (
                <span className="ml-auto text-xs text-zinc-500 shrink-0">{slot.duration_min}–{slot.duration_max} min</span>
              )}
            </>
          ) : (
            <span className="text-sm text-zinc-500">{restLabel}</span>
          )}
        </div>
      ))}
    </div>
  );
}

// ─── Progress Tracker ─────────────────────────────────────────────────────────

const PROGRESS_ITEMS = [
  "Profile saved",
  "Schedule saved",
  "Scanning channels",
  "Classifying videos",
  "Building your first plan",
];
const STAGE_INDEX: Record<string, number> = {
  scanning: 2, classifying: 3, planning: 4,
};

function ProgressTracker({ stage }: { stage: string | null }) {
  // activeIndex is always >= 2, so items 0 ("Profile saved") and 1 ("Schedule saved")
  // are always shown as done — they were completed before step 7 was reached.
  const activeIndex = stage === "done" ? 5 : (stage ? (STAGE_INDEX[stage] ?? 2) : 2);
  return (
    <div className="space-y-4">
      {PROGRESS_ITEMS.map((item, i) => {
        const done = stage === "done" ? true : i < activeIndex;
        const active = stage !== "done" && i === activeIndex;
        return (
          <div key={item} className="flex items-center gap-3">
            <div className={`h-6 w-6 rounded-full flex items-center justify-center text-xs shrink-0 transition-colors ${done ? "bg-zinc-600 text-white" : active ? "bg-white text-zinc-900 animate-pulse" : "bg-zinc-800 text-zinc-600"}`}>
              {done ? "✓" : active ? "⟳" : ""}
            </div>
            <span className={`text-sm ${done ? "text-zinc-300" : active ? "text-white font-medium" : "text-zinc-600"}`}>
              {item}{active ? "…" : ""}
            </span>
          </div>
        );
      })}
    </div>
  );
}

// ─── Data ─────────────────────────────────────────────────────────────────────

const LIFE_STAGES: { value: LifeStage; label: string; sublabel: string }[] = [
  { value: "beginner", label: "Just starting out",  sublabel: "New to working out, or getting back into it" },
  { value: "adult",    label: "Active adult",        sublabel: "Reasonably fit, been training for a while" },
  { value: "senior",   label: "55 and thriving",     sublabel: "Low-impact, joint-friendly, no gym required" },
  { value: "athlete",  label: "Training seriously",  sublabel: "Structured programming, performance goals" },
];

const GOALS: Record<LifeStage, string[]> = {
  beginner: ["Build a habit", "Lose weight", "Feel more energetic"],
  adult:    ["Build muscle", "Lose fat", "Improve cardio", "Stay consistent"],
  senior:   ["Stay active & healthy", "Improve flexibility", "Build strength safely"],
  athlete:  ["Strength & hypertrophy", "Endurance", "Athletic performance", "Cut weight"],
};

const DEFAULT_DAYS: Record<LifeStage, number> = { beginner: 3, adult: 4, senior: 3, athlete: 5 };
const DEFAULT_DURATION: Record<LifeStage, SessionLength> = { beginner: "short", adult: "medium", senior: "short", athlete: "long" };

const SESSION_OPTIONS: { value: SessionLength; label: string; sublabel: string }[] = [
  { value: "short",  label: "15–20 min",      sublabel: "Quick and consistent" },
  { value: "medium", label: "25–35 min",      sublabel: "A solid session" },
  { value: "long",   label: "40–60 min",      sublabel: "Full workout" },
  { value: "any",    label: "No preference",  sublabel: "Let the video decide" },
];

const SUGGESTIONS: Record<LifeStage, string[]> = {
  senior:   ["Grow Young Fitness", "HASfit", "SilverSneakers"],
  beginner: ["Sydney Cummings Houdyshell", "Heather Robertson", "MommaStrong"],
  adult:    ["Athlean-X", "Heather Robertson", "Jeff Nippard", "Yoga with Adriene"],
  athlete:  ["Athlean-X", "Jeff Nippard", "Renaissance Periodization"],
};

// ─── Main ─────────────────────────────────────────────────────────────────────

export default function OnboardingPage() {
  const router = useRouter();

  const [step, setStep] = useState(1);
  const [profile, setProfile] = useState<LifeStage | null>(null);
  const [goal, setGoal] = useState<string | null>(null);
  const [trainingDays, setTrainingDays] = useState(3);
  const [sessionLength, setSessionLength] = useState<SessionLength>("medium");
  const [schedule, setSchedule] = useState<ScheduleSlot[]>([]);
  const [customising, setCustomising] = useState(false);
  const [channels, setChannels] = useState<ChannelResponse[]>([]);
  const [savingSchedule, setSavingSchedule] = useState(false);
  const [error, setError] = useState("");
  const [scanStage, setScanStage] = useState<string | null>(null);
  const [scanError, setScanError] = useState("");

  const isSenior = profile === "senior";

  function handleProfileSelect(p: LifeStage) {
    setProfile(p);
    setTrainingDays(DEFAULT_DAYS[p]);
    setSessionLength(DEFAULT_DURATION[p]);
    setGoal(null);
    setStep(2);
  }

  function handleGoalSelect(g: string) {
    setGoal(g);
    setStep(3);
  }

  function handleDaysSelect(d: number) {
    setTrainingDays(d);
    setStep(4);
  }

  function handleSessionLengthSelect(sl: SessionLength) {
    setSessionLength(sl);
    const generated = buildSchedule(profile!, goal!, trainingDays, sl);
    setSchedule(generated);
    setCustomising(false);
    setStep(5);
  }

  async function handleScheduleConfirm() {
    setSavingSchedule(true);
    setError("");
    try {
      await updateSchedule(schedule);
      setStep(6);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to save schedule");
    } finally {
      setSavingSchedule(false);
    }
  }

  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  async function executeScan(): Promise<string | null> {
    try {
      await triggerScan();
      return null;
    } catch (e: unknown) {
      return e instanceof Error ? e.message : "Failed to start scan";
    }
  }

  async function handleStartScan() {
    setError("");
    const err = await executeScan();
    if (err) setError(err);
    else setStep(7);
  }

  async function handleRetry() {
    setScanError("");
    setScanStage(null);
    const err = await executeScan();
    if (err) setScanError(err);
  }

  const pollStatus = useCallback(async () => {
    try {
      const status = await getJobStatus();
      setScanStage((prev) => (prev === status.stage ? prev : status.stage));
      if (status.error) {
        setScanError((prev) => (prev === status.error ? prev : status.error!));
      }
      if (status.stage === "done") {
        if (intervalRef.current) {
          clearInterval(intervalRef.current);
          intervalRef.current = null;
        }
        setTimeout(() => router.push("/dashboard"), 800);
      }
    } catch {
      // ignore transient poll errors
    }
  }, [router]);

  useEffect(() => {
    if (step !== 7) return;
    intervalRef.current = setInterval(pollStatus, 3000);
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [step, pollStatus]);

  const contentClass = `w-full ${isSenior ? "text-lg" : ""}`;

  return (
    <main className="min-h-screen bg-zinc-950 flex flex-col items-center justify-center px-4 py-12">
      <div className="w-full max-w-2xl">
        <StepIndicator internalStep={step} />

        {error && (
          <div className="mb-6 rounded-lg border border-red-800 bg-red-900/30 px-4 py-3 text-sm text-red-400">
            {error}
          </div>
        )}

        {/* Step 1 — Life Stage */}
        {step === 1 && (
          <div className={contentClass}>
            <h2 className="text-xl font-semibold text-white mb-1">First, tell us a bit about yourself</h2>
            <p className="text-zinc-400 text-sm mb-6">We&apos;ll tailor your plan to fit.</p>
            <div className="flex flex-col gap-3">
              {LIFE_STAGES.map((ls) => (
                <OptionCard key={ls.value} label={ls.label} sublabel={ls.sublabel} onClick={() => handleProfileSelect(ls.value)} />
              ))}
            </div>
          </div>
        )}

        {/* Step 2 — Goal */}
        {step === 2 && profile && (
          <div className={contentClass}>
            <h2 className="text-xl font-semibold text-white mb-1">What&apos;s your main goal?</h2>
            <p className="text-zinc-400 text-sm mb-6">Pick the one that feels most right.</p>
            <div className="flex flex-col gap-3">
              {GOALS[profile].map((g) => (
                <OptionCard key={g} label={g} onClick={() => handleGoalSelect(g)} />
              ))}
            </div>
            <button onClick={() => setStep(1)} className="mt-4 text-sm text-zinc-500 hover:text-zinc-300 transition">
              ← Back
            </button>
          </div>
        )}

        {/* Step 3 — Training Days */}
        {step === 3 && (
          <div className={contentClass}>
            <h2 className="text-xl font-semibold text-white mb-1">How many days a week can you train?</h2>
            <div className="flex gap-3 mt-6 mb-4">
              {(isSenior ? [2, 3, 4, 5] : [2, 3, 4, 5, 6]).map((d) => (
                <button
                  key={d}
                  onClick={() => handleDaysSelect(d)}
                  className={`h-12 w-12 rounded-xl border text-sm font-bold transition
                    ${trainingDays === d ? "border-white bg-white text-zinc-900" : "border-zinc-700 bg-zinc-900 text-white hover:border-zinc-500 hover:bg-zinc-800"}`}
                >
                  {d}
                </button>
              ))}
            </div>
            <p className="text-sm text-zinc-500">Even 2 days/week makes a real difference.</p>
            <button onClick={() => setStep(2)} className="mt-4 text-sm text-zinc-500 hover:text-zinc-300 transition">
              ← Back
            </button>
          </div>
        )}

        {/* Step 4 — Session Length */}
        {step === 4 && (
          <div className={contentClass}>
            <h2 className="text-xl font-semibold text-white mb-1">How long per session?</h2>
            {(isSenior || profile === "beginner") && (
              <p className="text-zinc-400 text-sm mb-2">Short sessions are just as effective when done consistently.</p>
            )}
            <div className="flex flex-col gap-3 mt-4">
              {SESSION_OPTIONS.map((opt) => (
                <OptionCard key={opt.value} label={opt.label} sublabel={opt.sublabel} onClick={() => handleSessionLengthSelect(opt.value)} />
              ))}
            </div>
            <button onClick={() => setStep(3)} className="mt-4 text-sm text-zinc-500 hover:text-zinc-300 transition">
              ← Back
            </button>
          </div>
        )}

        {/* Step 5 — Schedule Preview */}
        {step === 5 && (
          <div className="w-full">
            <h2 className="text-xl font-semibold text-white mb-1">Here&apos;s your personalised plan</h2>
            <p className="text-zinc-400 text-sm mb-6">Based on your goals. Tweak anything you like.</p>

            {!customising ? (
              <>
                <SchedulePreview schedule={schedule} isSenior={isSenior} />
                <div className="flex gap-3 mt-6">
                  <button
                    onClick={handleScheduleConfirm}
                    disabled={savingSchedule}
                    className="flex-1 rounded-lg bg-white px-4 py-3 text-sm font-semibold text-zinc-900 hover:bg-zinc-100 disabled:opacity-40 transition"
                  >
                    {savingSchedule ? "Saving…" : "Looks good →"}
                  </button>
                  <button
                    onClick={() => setCustomising(true)}
                    className="rounded-lg border border-zinc-700 px-4 py-3 text-sm font-medium text-zinc-300 hover:bg-zinc-800 transition"
                  >
                    Customise
                  </button>
                </div>
              </>
            ) : (
              <>
                <ScheduleEditor schedule={schedule} onScheduleChange={setSchedule} />
                <div className="flex gap-3 mt-6">
                  <button onClick={() => setStep(4)} className="rounded-lg border border-zinc-700 px-4 py-3 text-sm font-medium text-zinc-300 hover:bg-zinc-800 transition">
                    ← Back
                  </button>
                  <button
                    onClick={handleScheduleConfirm}
                    disabled={savingSchedule}
                    className="flex-1 rounded-lg bg-white px-4 py-3 text-sm font-semibold text-zinc-900 hover:bg-zinc-100 disabled:opacity-40 transition"
                  >
                    {savingSchedule ? "Saving…" : "Looks good →"}
                  </button>
                </div>
              </>
            )}
          </div>
        )}

        {/* Step 6 — Channels */}
        {step === 6 && profile && (
          <div className="w-full max-w-lg">
            <h2 className="text-xl font-semibold text-white mb-1">Add your favourite channels</h2>
            <p className="text-zinc-400 text-sm mb-6">
              {isSenior
                ? "Search for YouTube channels focused on gentle movement and healthy ageing."
                : profile === "beginner"
                ? "Search for beginner-friendly YouTube fitness channels."
                : "Search for YouTube fitness channels to include in your plan."}
            </p>
            <ChannelManager
              channels={channels}
              onChannelsChange={setChannels}
              suggestions={SUGGESTIONS[profile]}
            />
            <div className="flex gap-3 mt-6">
              <button onClick={() => setStep(5)} className="rounded-lg border border-zinc-700 px-4 py-3 text-sm font-medium text-zinc-300 hover:bg-zinc-800 transition">
                ← Back
              </button>
              <button
                onClick={handleStartScan}
                disabled={channels.length === 0}
                className="flex-1 rounded-lg bg-white px-4 py-3 text-sm font-semibold text-zinc-900 hover:bg-zinc-100 disabled:opacity-30 transition"
              >
                Continue →
              </button>
            </div>
          </div>
        )}

        {/* Step 7 — Live Progress */}
        {step === 7 && (
          <div className="w-full max-w-md">
            <h2 className="text-xl font-semibold text-white mb-2">Setting up your plan…</h2>
            <p className="text-zinc-400 text-sm mb-8">Hang tight, this usually takes a minute or two.</p>
            <ProgressTracker stage={scanStage} />
            {scanError && (
              <div className="mt-6 rounded-lg border border-red-800 bg-red-900/30 px-4 py-3">
                <p className="text-sm text-red-400 mb-3">{scanError}</p>
                <button
                  onClick={handleRetry}
                  className="rounded-lg bg-red-800 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 transition"
                >
                  Try again
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </main>
  );
}
