"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { useRouter } from "next/navigation";
import {
  getMe,
  getChannels,
  updateSchedule,
  updateEmailNotifications,
  triggerScan,
  getJobStatus,
  getSuggestions,
  setToken,
  loginUrl,
  type ChannelResponse,
  type ChannelSearchResult,
  type ScheduleSlot,
} from "@/lib/api";
import ChannelManager from "@/components/ChannelManager";
import ScheduleEditor from "@/components/ScheduleEditor";
import { buildSchedule, type LifeStage, type SessionLength } from "@/lib/scheduleTemplates";
import { DAY_LABELS } from "@/lib/utils";
import { EQUIPMENT_OPTIONS, GOALS, type GoalGroup } from "@/lib/constants";

// ─── Step Indicator ───────────────────────────────────────────────────────────

function StepIndicator({ internalStep }: { internalStep: number }) {
  const steps = ["Profile", "Channels", "Your Plan"];
  const visibleStep = internalStep <= 7 ? 1 : internalStep === 8 ? 2 : 3;
  return (
    <div className="flex items-center gap-3 mb-8">
      {steps.map((label, i) => {
        const step = i + 1;
        const active = step === visibleStep;
        const done = step < visibleStep;
        return (
          <div key={label} className="flex items-center gap-3">
            <div className="flex items-center gap-2">
              <div className={`h-7 w-7 rounded-full flex items-center justify-center text-xs font-bold transition-colors ${active ? "bg-zinc-900 dark:bg-white text-white dark:text-zinc-900" : done ? "bg-zinc-400 dark:bg-zinc-600 text-white" : "bg-zinc-100 dark:bg-zinc-800 text-zinc-500"}`}>
                {done ? "✓" : step}
              </div>
              <span className={`text-sm ${active ? "text-zinc-900 dark:text-white font-medium" : "text-zinc-500"}`}>
                {label}
              </span>
            </div>
            {i < steps.length - 1 && (
              <div className={`h-px w-8 ${done ? "bg-zinc-400 dark:bg-zinc-600" : "bg-zinc-200 dark:bg-zinc-800"}`} />
            )}
          </div>
        );
      })}
    </div>
  );
}

// ─── Card Button ──────────────────────────────────────────────────────────────

function OptionCard({
  label,
  sublabel,
  onClick,
  selected,
}: {
  label: string;
  sublabel?: string;
  onClick: () => void;
  selected?: boolean;
}) {
  return (
    <button
      onClick={onClick}
      className={`w-full text-left rounded-xl border px-5 py-4 transition cursor-pointer ${
        selected
          ? "border-zinc-900 dark:border-white bg-zinc-100 dark:bg-zinc-800"
          : "border-zinc-200 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-900 hover:border-zinc-400 dark:hover:border-zinc-500 hover:bg-zinc-100 dark:hover:bg-zinc-800"
      }`}
    >
      <p className="font-medium text-zinc-900 dark:text-white">{label}</p>
      {sublabel && <p className="text-sm text-zinc-600 dark:text-zinc-400 mt-0.5">{sublabel}</p>}
    </button>
  );
}

// ─── Nav Buttons ──────────────────────────────────────────────────────────────

function StepNav({
  onBack,
  onNext,
  nextDisabled,
  nextLabel = "Next →",
}: {
  onBack?: () => void;
  onNext: () => void;
  nextDisabled?: boolean;
  nextLabel?: string;
}) {
  return (
    <div className="flex items-center gap-3 mt-6">
      {onBack && (
        <button
          onClick={onBack}
          className="rounded-lg border border-zinc-200 dark:border-zinc-700 px-4 py-3 text-sm font-medium text-zinc-700 dark:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-800 transition cursor-pointer"
        >
          ← Back
        </button>
      )}
      <button
        onClick={onNext}
        disabled={nextDisabled}
        className="flex-1 rounded-lg bg-zinc-900 dark:bg-white px-4 py-3 text-sm font-semibold text-white dark:text-zinc-900 hover:bg-zinc-700 dark:hover:bg-zinc-100 disabled:opacity-30 transition cursor-pointer"
      >
        {nextLabel}
      </button>
    </div>
  );
}

// ─── Schedule Preview ─────────────────────────────────────────────────────────

const WORKOUT_LABELS: Record<string, string> = {
  strength: "Strength training",
  hiit:     "HIIT",
  cardio:   "Light cardio",
  mobility: "Mobility & stretching",
  yoga:     "Yoga",
  pilates:  "Pilates",
  dance:    "Dance fitness",
};

function SchedulePreview({ schedule, isSenior }: { schedule: ScheduleSlot[]; isSenior: boolean }) {
  const restLabel = isSenior ? "Recovery day" : "Rest day";
  return (
    <div className="rounded-xl border border-zinc-200 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-900 divide-y divide-zinc-200 dark:divide-zinc-800 overflow-hidden">
      {schedule.map((slot) => (
        <div key={slot.day} className="flex items-center gap-4 px-5 py-3">
          <span className="w-8 text-sm font-medium text-zinc-600 dark:text-zinc-400 shrink-0">{DAY_LABELS[slot.day]}</span>
          {slot.workout_type ? (
            <>
              <span className="text-sm text-zinc-900 dark:text-white">{WORKOUT_LABELS[slot.workout_type] ?? slot.workout_type}</span>
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
  scanning: 2, classifying: 3, generating: 4,
};

function ProgressTracker({
  stage,
  classifyProgress,
}: {
  stage: string | null;
  classifyProgress: { total: number; done: number } | null;
}) {
  const activeIndex = stage === "done" ? 5 : (stage ? (STAGE_INDEX[stage] ?? 2) : 2);
  return (
    <div className="space-y-4">
      {PROGRESS_ITEMS.map((item, i) => {
        const done = stage === "done" ? true : i < activeIndex;
        const active = stage !== "done" && i === activeIndex;
        const showProgress = active && i === 3 && classifyProgress;
        // Negative done = batch still being built (Phase 1); positive = AI processing (Phase 3)
        const isBuilding = showProgress && classifyProgress!.done < 0;
        const pct = showProgress && !isBuilding
          ? Math.round((classifyProgress!.done / classifyProgress!.total) * 100)
          : 0;
        return (
          <div key={item}>
            <div className="flex items-center gap-3">
              <div className={`h-6 w-6 rounded-full flex items-center justify-center text-xs shrink-0 transition-colors ${done ? "bg-zinc-400 dark:bg-zinc-600 text-white" : active ? "bg-zinc-900 dark:bg-white text-white dark:text-zinc-900 animate-pulse" : "bg-zinc-100 dark:bg-zinc-800 text-zinc-500 dark:text-zinc-600"}`}>
                {done ? "✓" : active ? "⟳" : ""}
              </div>
              <span className={`text-sm ${done ? "text-zinc-700 dark:text-zinc-300" : active ? "text-zinc-900 dark:text-white font-medium" : "text-zinc-500 dark:text-zinc-600"}`}>
                {item}{active ? "…" : ""}
                {showProgress && (
                  <span className="ml-2 text-zinc-600 dark:text-zinc-400 font-normal">
                    {isBuilding
                      ? `preparing ${Math.abs(classifyProgress!.done)} / ${classifyProgress!.total}`
                      : `${classifyProgress!.done} / ${classifyProgress!.total}`}
                  </span>
                )}
              </span>
            </div>
            {showProgress && !isBuilding && (
              <div className="ml-9 mt-2 w-full bg-zinc-200 dark:bg-zinc-800 rounded-full h-1">
                <div
                  className="bg-zinc-900 dark:bg-white h-1 rounded-full transition-all duration-500"
                  style={{ width: `${pct}%` }}
                />
              </div>
            )}
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


const DEFAULT_DAYS: Record<LifeStage, number> = { beginner: 3, adult: 4, senior: 3, athlete: 5 };
const DEFAULT_DURATION: Record<LifeStage, SessionLength> = { beginner: "short", adult: "medium", senior: "short", athlete: "long" };

const SESSION_OPTIONS: { value: SessionLength; label: string; sublabel: string }[] = [
  { value: "short",  label: "15–20 min",      sublabel: "Quick and consistent" },
  { value: "medium", label: "25–35 min",      sublabel: "A solid session" },
  { value: "long",   label: "40–60 min",      sublabel: "Full workout" },
  { value: "any",    label: "No preference",  sublabel: "Let the video decide" },
];


// ─── Main ─────────────────────────────────────────────────────────────────────

export default function OnboardingPage() {
  const router = useRouter();

  const [step, setStep] = useState(1);
  const [profile, setProfile] = useState<LifeStage | null>(null);
  const [goals, setGoals] = useState<string[]>([]);
  const [equipment, setEquipment] = useState<string[]>([]);
  const [trainingDays, setTrainingDays] = useState(3);
  const [sessionLength, setSessionLength] = useState<SessionLength>("medium");
  const [schedule, setSchedule] = useState<ScheduleSlot[]>([]);
  const [customising, setCustomising] = useState(false);
  const [channels, setChannels] = useState<ChannelResponse[]>([]);
  const [suggestions, setSuggestions] = useState<ChannelSearchResult[]>([]);
  const [suggestionsLoading, setSuggestionsLoading] = useState(false);
  const [emailNotifications, setEmailNotifications] = useState(true);
  const [savingNotifications, setSavingNotifications] = useState(false);
  const [savingSchedule, setSavingSchedule] = useState(false);
  const [error, setError] = useState("");
  const [scanStage, setScanStage] = useState<string | null>(null);
  const [scanError, setScanError] = useState("");
  const [classifyProgress, setClassifyProgress] = useState<{ total: number; done: number } | null>(null);

  const [guardChecking, setGuardChecking] = useState(true);
  const [isAuthenticated, setIsAuthenticated] = useState(false);

  const isSenior = profile === "senior";

  // Guard: redirect already-onboarded users to dashboard; allow unauthenticated for pre-auth steps
  useEffect(() => {
    let cancelled = false;
    // Extract token if we arrived directly from OAuth callback
    const params = new URLSearchParams(window.location.search);
    const token = params.get("token");
    if (token) {
      setToken(token);
      window.history.replaceState({}, "", window.location.pathname);
    }
    getMe()
      .then((user) => {
        if (cancelled) return;
        setIsAuthenticated(true);
        if (user.is_admin) { setGuardChecking(false); return; }
        return getChannels().then((ch) => {
          if (cancelled) return;
          if (ch.length > 0) {
            localStorage.removeItem("onboarding_pending");
            router.replace("/dashboard?from=onboarding");
            return;
          }
          // New user - check if returning from OAuth with saved pre-auth state
          const pending = localStorage.getItem("onboarding_pending");
          if (pending) {
            try {
              const saved = JSON.parse(pending);
              localStorage.removeItem("onboarding_pending");
              if (saved.profile) setProfile(saved.profile);
              if (saved.goals) setGoals(saved.goals);
              if (saved.equipment) setEquipment(saved.equipment);
              if (saved.trainingDays) setTrainingDays(saved.trainingDays);
              if (saved.sessionLength) setSessionLength(saved.sessionLength);
              if (saved.schedule?.length) {
                setSchedule(saved.schedule);
                updateSchedule(saved.schedule, saved.profile, saved.goals, saved.equipment)
                  .then(() => { if (!cancelled) setStep(7); })
                  .catch((e: unknown) => {
                    if (!cancelled) {
                      setStep(6);
                      setError(e instanceof Error ? e.message : "Failed to save schedule");
                    }
                  })
                  .finally(() => { if (!cancelled) setGuardChecking(false); });
                return;
              }
            } catch {
              localStorage.removeItem("onboarding_pending");
            }
          }
          setGuardChecking(false);
        });
      })
      .catch(() => {
        // Unauthenticated - allow pre-auth steps 1-6 without redirect
        if (!cancelled) setGuardChecking(false);
      });
    return () => { cancelled = true; };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Step 1: select profile (highlight only - Next button advances)
  function handleProfileSelect(p: LifeStage) {
    setProfile(p);
    setTrainingDays(DEFAULT_DAYS[p]);
    setSessionLength(DEFAULT_DURATION[p]);
    setGoals([]);
  }

  // Step 2: toggle goal in/out of selection (max 3)
  function handleGoalToggle(g: string) {
    setGoals((prev) =>
      prev.includes(g) ? prev.filter((x) => x !== g) : prev.length < 3 ? [...prev, g] : prev
    );
  }

  // Step 5 (equipment): toggle equipment item in/out of selection
  function handleEquipmentToggle(id: string) {
    setEquipment((prev) => prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]);
  }

  // Step 4: select session length (highlight only - Next button advances)
  function handleSessionLengthSelect(sl: SessionLength) {
    setSessionLength(sl);
  }

  // Step 5 → 6: build schedule then advance to preview
  function handleBuildSchedule() {
    const generated = buildSchedule(profile!, goals, trainingDays, sessionLength);
    setSchedule(generated);
    setCustomising(false);
    setStep(6);
  }

  async function handleScheduleConfirm() {
    if (!isAuthenticated) {
      localStorage.setItem("onboarding_pending", JSON.stringify({
        profile, goals, equipment, trainingDays, sessionLength, schedule,
      }));
      window.location.href = loginUrl();
      return;
    }
    setSavingSchedule(true);
    setError("");
    try {
      await updateSchedule(schedule, profile!, goals, equipment);
      setStep(7);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to save schedule");
    } finally {
      setSavingSchedule(false);
    }
  }

  async function handleEmailNotificationsContinue() {
    setSavingNotifications(true);
    try {
      await updateEmailNotifications(emailNotifications);
    } catch {
      // non-blocking - don't prevent user from continuing
    } finally {
      setSavingNotifications(false);
    }
    setStep(8);
  }

  // Fetch curated suggestion cards when the user reaches the channels step
  useEffect(() => {
    if (step !== 8 || !profile) return;
    setSuggestionsLoading(true);
    getSuggestions(profile, goals)
      .then(setSuggestions)
      .catch(() => {})
      .finally(() => setSuggestionsLoading(false));
  }, [step, profile, goals]);

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
    else setStep(9);
  }

  async function handleRetry() {
    setScanError("");
    setScanStage(null);
    const err = await executeScan();
    if (err) setScanError(err);
  }

  const pollStatus = useCallback(async () => {
    try {
      const { stage, total, done, error } = await getJobStatus();
      setScanStage((prev) => (prev === stage ? prev : stage));
      if (stage === "classifying" && total !== null && done !== null) {
        setClassifyProgress((prev) =>
          prev?.total === total && prev?.done === done ? prev : { total, done }
        );
      } else {
        setClassifyProgress(null);
      }
      if (error) {
        setScanError((prev) => (prev === error ? prev : error));
      }
      if (stage === "done") {
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
    if (step !== 9) return;
    intervalRef.current = setInterval(pollStatus, 3000);
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [step, pollStatus]);

  const contentClass = `w-full ${isSenior ? "text-lg" : ""}`;

  if (guardChecking) return null;

  return (
    <main className="min-h-screen bg-white dark:bg-zinc-950 flex flex-col items-center justify-center px-4 py-12">
      <div className="w-full max-w-2xl">
        <StepIndicator internalStep={step} />

        {error && (
          <div className="mb-6 rounded-lg border border-red-800 bg-red-900/30 px-4 py-3 text-sm text-red-400">
            {error}
          </div>
        )}

        {/* Step 1 - Life Stage */}
        {step === 1 && (
          <div className={contentClass}>
            <h2 className="text-xl font-semibold text-zinc-900 dark:text-white mb-1">First, tell us a bit about yourself</h2>
            <p className="text-zinc-600 dark:text-zinc-400 text-sm mb-6">We&apos;ll tailor your plan to fit.</p>
            <div className="flex flex-col gap-3">
              {LIFE_STAGES.map((ls) => (
                <OptionCard
                  key={ls.value}
                  label={ls.label}
                  sublabel={ls.sublabel}
                  selected={profile === ls.value}
                  onClick={() => handleProfileSelect(ls.value)}
                />
              ))}
            </div>
            <StepNav onNext={() => setStep(2)} nextDisabled={!profile} />
          </div>
        )}

        {/* Step 2 - Goals (grouped by style) */}
        {step === 2 && profile && (
          <div className={contentClass}>
            <h2 className="text-xl font-semibold text-zinc-900 dark:text-white mb-1">What are your goals?</h2>
            <p className="text-zinc-600 dark:text-zinc-400 text-sm mb-6">Pick up to 3 that apply.</p>
            <div className="space-y-5">
              {GOALS[profile].map((group) => (
                <div key={group.group}>
                  <p className="text-xs font-semibold uppercase tracking-wide text-zinc-500 mb-2">{group.group}</p>
                  <div className="flex flex-col gap-2">
                    {group.options.map((g) => {
                      const selected = goals.includes(g);
                      const atMax = goals.length >= 3 && !selected;
                      return (
                        <button
                          key={g}
                          onClick={() => handleGoalToggle(g)}
                          disabled={atMax}
                          className={`w-full text-left rounded-xl border px-5 py-3.5 transition cursor-pointer disabled:opacity-40 ${
                            selected
                              ? "border-zinc-900 dark:border-white bg-zinc-100 dark:bg-zinc-800"
                              : "border-zinc-200 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-900 hover:border-zinc-400 dark:hover:border-zinc-500 hover:bg-zinc-100 dark:hover:bg-zinc-800"
                          }`}
                        >
                          <div className="flex items-center gap-3">
                            <div className={`h-4 w-4 rounded shrink-0 border-2 flex items-center justify-center transition ${
                              selected ? "border-zinc-900 dark:border-white bg-zinc-900 dark:bg-white" : "border-zinc-400 dark:border-zinc-600"
                            }`}>
                              {selected && <span className="text-white dark:text-zinc-900 text-xs font-bold leading-none">✓</span>}
                            </div>
                            <p className="font-medium text-zinc-900 dark:text-white">{g}</p>
                          </div>
                        </button>
                      );
                    })}
                  </div>
                </div>
              ))}
            </div>
            <StepNav onBack={() => setStep(1)} onNext={() => setStep(3)} nextDisabled={goals.length === 0} />
          </div>
        )}

        {/* Step 3 - Training Days */}
        {step === 3 && (
          <div className={contentClass}>
            <h2 className="text-xl font-semibold text-zinc-900 dark:text-white mb-1">How many days a week can you train?</h2>
            <div className="flex gap-3 mt-6 mb-4">
              {(isSenior ? [2, 3, 4, 5] : [2, 3, 4, 5, 6]).map((d) => (
                <button
                  key={d}
                  onClick={() => setTrainingDays(d)}
                  className={`h-12 w-12 rounded-xl border text-sm font-bold transition cursor-pointer
                    ${trainingDays === d ? "border-zinc-900 bg-zinc-900 text-white dark:border-white dark:bg-white dark:text-zinc-900" : "border-zinc-200 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-900 text-zinc-900 dark:text-white hover:border-zinc-400 dark:hover:border-zinc-500 hover:bg-zinc-100 dark:hover:bg-zinc-800"}`}
                >
                  {d}
                </button>
              ))}
            </div>
            <p className="text-sm text-zinc-500">Even 2 days/week makes a real difference.</p>
            <StepNav onBack={() => setStep(2)} onNext={() => setStep(4)} />
          </div>
        )}

        {/* Step 4 - Session Length */}
        {step === 4 && (
          <div className={contentClass}>
            <h2 className="text-xl font-semibold text-zinc-900 dark:text-white mb-1">How long per session?</h2>
            {(isSenior || profile === "beginner") && (
              <p className="text-zinc-600 dark:text-zinc-400 text-sm mb-2">Short sessions are just as effective when done consistently.</p>
            )}
            <div className="flex flex-col gap-3 mt-4">
              {SESSION_OPTIONS.map((opt) => (
                <OptionCard
                  key={opt.value}
                  label={opt.label}
                  sublabel={opt.sublabel}
                  selected={sessionLength === opt.value}
                  onClick={() => handleSessionLengthSelect(opt.value)}
                />
              ))}
            </div>
            <StepNav onBack={() => setStep(3)} onNext={() => setStep(5)} />
          </div>
        )}

        {/* Step 5 - Equipment */}
        {step === 5 && (
          <div className={contentClass}>
            <h2 className="text-xl font-semibold text-zinc-900 dark:text-white mb-1">What do you have at home?</h2>
            <p className="text-zinc-600 dark:text-zinc-400 text-sm mb-6">
              We&apos;ll only suggest videos that match your setup. Tick everything you have.
            </p>
            <div className="flex flex-wrap gap-2 mb-2">
              {EQUIPMENT_OPTIONS.map((opt) => {
                const selected = equipment.includes(opt.id);
                return (
                  <button
                    key={opt.id}
                    type="button"
                    onClick={() => handleEquipmentToggle(opt.id)}
                    className={`rounded-full border px-4 py-2 text-sm font-medium transition cursor-pointer ${
                      selected
                        ? "border-zinc-900 dark:border-white bg-zinc-900 dark:bg-white text-white dark:text-zinc-900"
                        : "border-zinc-200 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-900 text-zinc-700 dark:text-zinc-300 hover:border-zinc-400 dark:hover:border-zinc-500 hover:bg-zinc-100 dark:hover:bg-zinc-800"
                    }`}
                  >
                    {opt.label}
                  </button>
                );
              })}
            </div>
            <p className="text-xs text-zinc-500 mt-3 mb-1">Nothing selected means bodyweight / no equipment - that&apos;s totally fine.</p>
            <StepNav onBack={() => setStep(4)} onNext={handleBuildSchedule} nextLabel="Build my schedule →" />
          </div>
        )}

        {/* Step 6 - Schedule Preview (was step 5) */}
        {step === 6 && (
          <div className="w-full">
            <h2 className="text-xl font-semibold text-zinc-900 dark:text-white mb-1">Here&apos;s your personalised plan</h2>
            <p className="text-zinc-600 dark:text-zinc-400 text-sm mb-6">Based on your goals. Tweak anything you like.</p>

            {!customising ? (
              <>
                <SchedulePreview schedule={schedule} isSenior={isSenior} />
                <div className="flex gap-3 mt-6">
                  <button onClick={() => setStep(5)} className="rounded-lg border border-zinc-200 dark:border-zinc-700 px-4 py-3 text-sm font-medium text-zinc-700 dark:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-800 transition cursor-pointer">
                    ← Back
                  </button>
                  <button
                    onClick={() => setCustomising(true)}
                    className="rounded-lg border border-zinc-200 dark:border-zinc-700 px-4 py-3 text-sm font-medium text-zinc-700 dark:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-800 transition cursor-pointer"
                  >
                    Customise
                  </button>
                  <button
                    onClick={handleScheduleConfirm}
                    disabled={savingSchedule}
                    className="flex-1 rounded-lg bg-zinc-900 dark:bg-white px-4 py-3 text-sm font-semibold text-white dark:text-zinc-900 hover:bg-zinc-700 dark:hover:bg-zinc-100 disabled:opacity-40 transition cursor-pointer"
                  >
                    {savingSchedule ? "Saving…" : isAuthenticated ? "Looks good →" : "Create free account →"}
                  </button>
                </div>
                {!isAuthenticated && (
                  <p className="text-xs text-zinc-400 dark:text-zinc-600 text-center mt-2">Takes 10 seconds - no credit card needed</p>
                )}
              </>
            ) : (
              <>
                <ScheduleEditor schedule={schedule} onScheduleChange={setSchedule} />
                <div className="flex gap-3 mt-6">
                  <button onClick={() => setStep(5)} className="rounded-lg border border-zinc-200 dark:border-zinc-700 px-4 py-3 text-sm font-medium text-zinc-700 dark:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-800 transition cursor-pointer">
                    ← Back
                  </button>
                  <button
                    onClick={handleScheduleConfirm}
                    disabled={savingSchedule}
                    className="flex-1 rounded-lg bg-zinc-900 dark:bg-white px-4 py-3 text-sm font-semibold text-white dark:text-zinc-900 hover:bg-zinc-700 dark:hover:bg-zinc-100 disabled:opacity-40 transition cursor-pointer"
                  >
                    {savingSchedule ? "Saving…" : isAuthenticated ? "Looks good →" : "Create free account →"}
                  </button>
                </div>
                {!isAuthenticated && (
                  <p className="text-xs text-zinc-400 dark:text-zinc-600 text-center mt-2">Takes 10 seconds - no credit card needed</p>
                )}
              </>
            )}
          </div>
        )}

        {/* Step 7 - Email Notifications (was step 6) */}
        {step === 7 && (
          <div className={contentClass}>
            <h2 className="text-xl font-semibold text-zinc-900 dark:text-white mb-1">Get your weekly plan by email?</h2>
            <p className="text-zinc-600 dark:text-zinc-400 text-sm mb-6">
              We&apos;ll send you a fresh workout plan every Monday - easy to reference, even offline.
            </p>
            <div className="flex flex-col gap-3">
              <OptionCard
                label="Yes, email me my weekly plan"
                sublabel="Arrives every Sunday evening"
                selected={emailNotifications}
                onClick={() => setEmailNotifications(true)}
              />
              <OptionCard
                label="No thanks"
                sublabel="I'll check the app directly"
                selected={!emailNotifications}
                onClick={() => setEmailNotifications(false)}
              />
            </div>
            <StepNav
              onBack={() => setStep(6)}
              onNext={handleEmailNotificationsContinue}
              nextLabel={savingNotifications ? "Saving…" : "Next →"}
              nextDisabled={savingNotifications}
            />
          </div>
        )}

        {/* Step 8 - Channels (was step 7) */}
        {step === 8 && profile && (
          <div className="w-full max-w-lg">
            <h2 className="text-xl font-semibold text-zinc-900 dark:text-white mb-1">Add your favourite channels</h2>
            <p className="text-zinc-600 dark:text-zinc-400 text-sm mb-6">
              {isSenior
                ? "Search for YouTube channels focused on gentle movement and healthy ageing."
                : profile === "beginner"
                ? "Search for beginner-friendly YouTube fitness channels."
                : "Search for YouTube fitness channels to include in your plan."}
            </p>
            <ChannelManager
              channels={channels}
              onChannelsChange={setChannels}
              suggestions={suggestions}
              suggestionsLoading={suggestionsLoading}
            />
            <div className="flex gap-3 mt-6">
              <button onClick={() => setStep(7)} className="rounded-lg border border-zinc-200 dark:border-zinc-700 px-4 py-3 text-sm font-medium text-zinc-700 dark:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-800 transition cursor-pointer">
                ← Back
              </button>
              <button
                onClick={handleStartScan}
                disabled={channels.length === 0}
                className="flex-1 rounded-lg bg-zinc-900 dark:bg-white px-4 py-3 text-sm font-semibold text-white dark:text-zinc-900 hover:bg-zinc-700 dark:hover:bg-zinc-100 disabled:opacity-30 transition cursor-pointer"
              >
                Continue →
              </button>
            </div>
          </div>
        )}

        {/* Step 9 - Live Progress (was step 8) */}
        {step === 9 && (
          <div className="w-full max-w-md">
            <h2 className="text-xl font-semibold text-zinc-900 dark:text-white mb-2">Setting up your plan…</h2>
            <p className="text-zinc-600 dark:text-zinc-400 text-sm mb-8">
              We&apos;re scanning your channels and classifying videos with AI.
              This takes 2–5 minutes on first setup - worth the wait.
            </p>
            <ProgressTracker stage={scanStage} classifyProgress={classifyProgress} />
            {scanError && (
              <div className="mt-6 rounded-lg border border-red-800 bg-red-900/30 px-4 py-3">
                <p className="text-sm text-red-400 mb-3">{scanError}</p>
                <button
                  onClick={handleRetry}
                  className="rounded-lg bg-red-800 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 transition cursor-pointer"
                >
                  Try again
                </button>
              </div>
            )}
            <p className="mt-8 text-xs text-zinc-500 text-center">
              Taking too long?{" "}
              <button
                onClick={() => router.push("/dashboard")}
                className="underline hover:text-zinc-300 transition cursor-pointer"
              >
                Go to dashboard
              </button>
              {" "}- setup continues in the background.
            </p>
          </div>
        )}
      </div>
    </main>
  );
}
