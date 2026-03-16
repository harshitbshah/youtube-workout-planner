"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Footer } from "@/components/Footer";
import FeedbackWidget from "@/components/FeedbackWidget";
import {
  getMe,
  getChannels,
  getSchedule,
  getSuggestions,
  patchMe,
  deleteMe,
  updateSchedule,
  updateEmailNotifications,
  updateProfile,
  generatePlan,
  logout,
  type User,
  type ChannelResponse,
  type ChannelSearchResult,
  type ScheduleSlot,
} from "@/lib/api";

const LIFE_STAGES = [
  { value: "beginner", label: "Just starting out" },
  { value: "adult",    label: "Active adult" },
  { value: "senior",   label: "55 and thriving" },
  { value: "athlete",  label: "Training seriously" },
] as const;

type LifeStage = typeof LIFE_STAGES[number]["value"];

const GOALS: Record<LifeStage, string[]> = {
  beginner: ["Build a habit", "Lose weight", "Feel more energetic"],
  adult:    ["Build muscle", "Lose fat", "Improve cardio", "Stay consistent"],
  senior:   ["Stay active & healthy", "Improve flexibility", "Build strength safely"],
  athlete:  ["Strength & hypertrophy", "Endurance", "Athletic performance", "Cut weight"],
};
import ChannelManager from "@/components/ChannelManager";
import ScheduleEditor from "@/components/ScheduleEditor";

function SectionCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-6">
      <h2 className="text-sm font-semibold text-zinc-900 dark:text-white mb-5">{title}</h2>
      {children}
    </div>
  );
}

export default function SettingsPage() {
  const router = useRouter();

  const [user, setUser] = useState<User | null>(null);
  const [channels, setChannels] = useState<ChannelResponse[]>([]);
  const [schedule, setSchedule] = useState<ScheduleSlot[]>([]);
  const [loading, setLoading] = useState(true);
  const [channelSuggestions, setChannelSuggestions] = useState<ChannelSearchResult[]>([]);
  const [suggestionsLoading, setSuggestionsLoading] = useState(true);

  // Profile
  const [displayName, setDisplayName] = useState("");
  const [savingName, setSavingName] = useState(false);
  const [nameStatus, setNameStatus] = useState<"idle" | "ok" | "err">("idle");

  // Fitness profile
  const [selectedLifeStage, setSelectedLifeStage] = useState<LifeStage | "">("");
  const [selectedGoals, setSelectedGoals] = useState<string[]>([]);
  const [savingFitnessProfile, setSavingFitnessProfile] = useState(false);
  const [fitnessProfileStatus, setFitnessProfileStatus] = useState<"idle" | "ok" | "err">("idle");

  // Notifications
  const [savingNotifications, setSavingNotifications] = useState(false);

  // Schedule
  const [savingSchedule, setSavingSchedule] = useState(false);
  const [scheduleStatus, setScheduleStatus] = useState<"idle" | "ok" | "err">("idle");

  // Channel removal banner
  const [showRegenerateBanner, setShowRegenerateBanner] = useState(false);
  const [regenerating, setRegenerating] = useState(false);
  const [regenerateStatus, setRegenerateStatus] = useState<"idle" | "ok" | "err">("idle");

  // Danger zone
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    Promise.all([getMe(), getChannels(), getSchedule()])
      .then(([u, ch, sched]) => {
        setUser(u);
        setDisplayName(u.display_name ?? "");
        if (u.profile) setSelectedLifeStage(u.profile as LifeStage);
        if (u.goal) setSelectedGoals(u.goal);
        setChannels(ch);
        setSchedule(sched.schedule);
      })
      .catch(() => router.replace("/"))
      .finally(() => setLoading(false));
  }, [router]);

  useEffect(() => {
    getSuggestions()
      .then(setChannelSuggestions)
      .catch(() => {})
      .finally(() => setSuggestionsLoading(false));
  }, []);

  async function handleSaveName() {
    setSavingName(true);
    setNameStatus("idle");
    try {
      const updated = await patchMe(displayName);
      setUser(updated);
      setNameStatus("ok");
      setTimeout(() => setNameStatus("idle"), 2500);
    } catch {
      setNameStatus("err");
    } finally {
      setSavingName(false);
    }
  }

  async function handleSaveFitnessProfile() {
    if (!selectedLifeStage || selectedGoals.length === 0) return;
    setSavingFitnessProfile(true);
    setFitnessProfileStatus("idle");
    try {
      const updated = await updateProfile(selectedLifeStage, selectedGoals);
      setUser(updated);
      setFitnessProfileStatus("ok");
      setTimeout(() => setFitnessProfileStatus("idle"), 2500);
    } catch {
      setFitnessProfileStatus("err");
    } finally {
      setSavingFitnessProfile(false);
    }
  }

  async function handleToggleNotifications(checked: boolean) {
    setSavingNotifications(true);
    try {
      const updated = await updateEmailNotifications(checked);
      setUser(updated);
    } finally {
      setSavingNotifications(false);
    }
  }

  async function handleSaveSchedule() {
    setSavingSchedule(true);
    setScheduleStatus("idle");
    try {
      await updateSchedule(schedule);
      setScheduleStatus("ok");
      setTimeout(() => setScheduleStatus("idle"), 2500);
    } catch {
      setScheduleStatus("err");
    } finally {
      setSavingSchedule(false);
    }
  }

  function handleChannelsChange(newChannels: ChannelResponse[]) {
    if (newChannels.length !== channels.length) {
      setShowRegenerateBanner(true);
      setRegenerateStatus("idle");
    }
    setChannels(newChannels);
  }

  async function handleRegenerate() {
    setRegenerating(true);
    setRegenerateStatus("idle");
    try {
      await generatePlan();
      setRegenerateStatus("ok");
      setShowRegenerateBanner(false);
    } catch {
      setRegenerateStatus("err");
    } finally {
      setRegenerating(false);
    }
  }

  async function handleDeleteAccount() {
    setDeleting(true);
    try {
      await deleteMe();
      await logout();
      router.replace("/");
    } catch {
      setDeleting(false);
      setConfirmDelete(false);
    }
  }

  if (loading) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-white dark:bg-zinc-950">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-zinc-300 border-t-zinc-900 dark:border-zinc-600 dark:border-t-white" />
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-white dark:bg-zinc-950 px-4 py-8">
      <div className="max-w-2xl mx-auto">

        {/* Header */}
        <div className="flex items-center gap-4 mb-8">
          <Link href="/dashboard" className="text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300 text-sm transition">
            ← Dashboard
          </Link>
          <h1 className="text-2xl font-bold text-zinc-900 dark:text-white">Settings</h1>
        </div>

        <div className="space-y-6">

          {/* Profile */}
          <SectionCard title="Profile">
            <div className="space-y-4">
              <div>
                <label className="block text-xs text-zinc-500 mb-1.5">Display name</label>
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={displayName}
                    onChange={(e) => setDisplayName(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && handleSaveName()}
                    placeholder="Your name"
                    className="flex-1 rounded-lg bg-zinc-100 dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 px-4 py-2.5 text-sm text-zinc-900 dark:text-white placeholder-zinc-500 focus:outline-none focus:border-zinc-500"
                  />
                  <button
                    onClick={handleSaveName}
                    disabled={savingName || displayName === (user?.display_name ?? "")}
                    className="rounded-lg bg-zinc-900 dark:bg-white px-4 py-2.5 text-sm font-semibold text-white dark:text-zinc-900 hover:bg-zinc-700 dark:hover:bg-zinc-100 disabled:opacity-40 transition"
                  >
                    {savingName ? "Saving…" : "Save"}
                  </button>
                </div>
                {nameStatus === "ok" && (
                  <p className="text-xs text-green-400 mt-1.5">Display name updated.</p>
                )}
                {nameStatus === "err" && (
                  <p className="text-xs text-red-400 mt-1.5">Failed to update name.</p>
                )}
              </div>
              <div>
                <label className="block text-xs text-zinc-500 mb-1.5">Email</label>
                <p className="text-sm text-zinc-600 dark:text-zinc-400">{user?.email}</p>
              </div>
            </div>
          </SectionCard>

          {/* Fitness Profile */}
          <SectionCard title="Fitness Profile">
            <p className="text-xs text-zinc-500 mb-4">
              Used to personalise your plan and validate new channels. Update this if your goals or fitness level have changed.
            </p>
            <div className="space-y-3">
              <div>
                <label className="block text-xs text-zinc-500 mb-1.5">Life stage</label>
                <select
                  value={selectedLifeStage}
                  onChange={(e) => {
                    const ls = e.target.value as LifeStage;
                    setSelectedLifeStage(ls);
                    setSelectedGoals([]);
                  }}
                  className="w-full rounded-lg bg-zinc-100 dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 px-4 py-2.5 text-sm text-zinc-900 dark:text-white focus:outline-none focus:border-zinc-500"
                >
                  <option value="" disabled>Select life stage</option>
                  {LIFE_STAGES.map((ls) => (
                    <option key={ls.value} value={ls.value}>{ls.label}</option>
                  ))}
                </select>
              </div>
              {selectedLifeStage && (
                <div>
                  <label className="block text-xs text-zinc-500 mb-2">Goals <span className="text-zinc-400">(pick up to 3)</span></label>
                  <div className="flex flex-col gap-2">
                    {GOALS[selectedLifeStage].map((g) => {
                      const checked = selectedGoals.includes(g);
                      const atMax = selectedGoals.length >= 3 && !checked;
                      return (
                        <label key={g} className={`flex items-center gap-3 rounded-lg border px-4 py-2.5 cursor-pointer transition ${
                          checked
                            ? "border-zinc-900 dark:border-white bg-zinc-100 dark:bg-zinc-800"
                            : "border-zinc-200 dark:border-zinc-700 hover:border-zinc-400 dark:hover:border-zinc-500"
                        } ${atMax ? "opacity-40 cursor-not-allowed" : ""}`}>
                          <input
                            type="checkbox"
                            checked={checked}
                            disabled={atMax}
                            onChange={() => {
                              if (checked) {
                                setSelectedGoals(selectedGoals.filter((x) => x !== g));
                              } else if (!atMax) {
                                setSelectedGoals([...selectedGoals, g]);
                              }
                            }}
                            className="h-4 w-4 rounded accent-zinc-900 dark:accent-white"
                          />
                          <span className="text-sm text-zinc-900 dark:text-white">{g}</span>
                        </label>
                      );
                    })}
                  </div>
                </div>
              )}
              <div className="flex items-center gap-3 pt-1">
                <button
                  onClick={handleSaveFitnessProfile}
                  disabled={
                    savingFitnessProfile ||
                    !selectedLifeStage ||
                    selectedGoals.length === 0 ||
                    (selectedLifeStage === user?.profile &&
                      JSON.stringify([...(selectedGoals)].sort()) === JSON.stringify([...(user?.goal ?? [])].sort()))
                  }
                  className="rounded-lg bg-zinc-900 dark:bg-white px-4 py-2.5 text-sm font-semibold text-white dark:text-zinc-900 hover:bg-zinc-700 dark:hover:bg-zinc-100 disabled:opacity-40 transition"
                >
                  {savingFitnessProfile ? "Saving…" : "Save profile"}
                </button>
                {fitnessProfileStatus === "ok" && (
                  <span className="text-xs text-green-400">Profile updated.</span>
                )}
                {fitnessProfileStatus === "err" && (
                  <span className="text-xs text-red-400">Failed to update. Try again.</span>
                )}
              </div>
            </div>
          </SectionCard>

          {/* Notifications */}
          <div id="notifications">
            <SectionCard title="Notifications">
              <label className="flex items-center gap-3 cursor-pointer">
                <div className="relative">
                  <input
                    type="checkbox"
                    className="sr-only"
                    checked={user?.email_notifications ?? true}
                    disabled={savingNotifications}
                    onChange={(e) => handleToggleNotifications(e.target.checked)}
                  />
                  <div
                    className={`w-10 h-6 rounded-full transition ${
                      user?.email_notifications ? "bg-zinc-900 dark:bg-white" : "bg-zinc-200 dark:bg-zinc-700"
                    }`}
                  />
                  <div
                    className={`absolute top-1 w-4 h-4 rounded-full transition-all ${
                      user?.email_notifications
                        ? "left-5 bg-white dark:bg-zinc-900"
                        : "left-1 bg-zinc-400"
                    }`}
                  />
                </div>
                <span className="text-sm text-zinc-700 dark:text-zinc-300">
                  Send me a weekly plan summary every Sunday evening
                </span>
              </label>
              {savingNotifications && (
                <p className="text-xs text-zinc-500 mt-2">Saving…</p>
              )}
            </SectionCard>
          </div>

          {/* Channels */}
          <SectionCard title="Channels">
            <p className="text-xs text-zinc-500 mb-4">
              Add or remove YouTube fitness channels. Changes take effect on the next weekly scan.
            </p>
            <ChannelManager
              channels={channels}
              onChannelsChange={handleChannelsChange}
              suggestions={channelSuggestions}
              suggestionsLoading={suggestionsLoading}
            />
            {showRegenerateBanner && (
              <div className="mt-4 flex items-center justify-between gap-3 rounded-lg border border-amber-500/30 bg-amber-50 dark:bg-amber-900/20 px-4 py-3">
                <p className="text-xs text-amber-700 dark:text-amber-300">
                  Your plan doesn&apos;t reflect your latest channel changes.
                </p>
                <div className="flex items-center gap-3 shrink-0">
                  <button
                    onClick={handleRegenerate}
                    disabled={regenerating}
                    className="text-xs font-semibold text-amber-700 dark:text-amber-300 hover:underline disabled:opacity-50"
                  >
                    {regenerating ? "Regenerating…" : "Regenerate now"}
                  </button>
                  <button
                    onClick={() => setShowRegenerateBanner(false)}
                    className="text-xs text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-300"
                  >
                    Dismiss
                  </button>
                </div>
              </div>
            )}
            {regenerateStatus === "ok" && (
              <p className="mt-2 text-xs text-green-500">Plan regenerated.</p>
            )}
            {regenerateStatus === "err" && (
              <p className="mt-2 text-xs text-red-400">Failed to regenerate. Try again from the dashboard.</p>
            )}
          </SectionCard>

          {/* Schedule */}
          <SectionCard title="Weekly Schedule">
            <p className="text-xs text-zinc-500 mb-4">
              Changes apply to the next generated plan.
            </p>
            <ScheduleEditor schedule={schedule} onScheduleChange={setSchedule} />
            <div className="mt-5 flex items-center gap-3">
              <button
                onClick={handleSaveSchedule}
                disabled={savingSchedule}
                className="rounded-lg bg-zinc-900 dark:bg-white px-5 py-2.5 text-sm font-semibold text-white dark:text-zinc-900 hover:bg-zinc-700 dark:hover:bg-zinc-100 disabled:opacity-40 transition"
              >
                {savingSchedule ? "Saving…" : "Save schedule"}
              </button>
              {scheduleStatus === "ok" && (
                <span className="text-xs text-green-400">Schedule saved.</span>
              )}
              {scheduleStatus === "err" && (
                <span className="text-xs text-red-400">Failed to save.</span>
              )}
            </div>
          </SectionCard>

          {/* Danger zone */}
          <div className="rounded-xl border border-red-900/50 bg-white dark:bg-zinc-900 p-6">
            <h2 className="text-sm font-semibold text-red-400 mb-2">Danger zone</h2>
            <p className="text-xs text-zinc-500 mb-5">
              Permanently delete your account and all data - channels, schedule, plan history.
              This cannot be undone.
            </p>

            {!confirmDelete ? (
              <button
                onClick={() => setConfirmDelete(true)}
                className="rounded-lg border border-red-800 px-4 py-2 text-sm text-red-400 hover:bg-red-900/30 transition"
              >
                Delete my account
              </button>
            ) : (
              <div className="rounded-lg border border-red-800 bg-red-900/20 p-4">
                <p className="text-sm text-red-300 mb-4">
                  Are you sure? This will delete everything and cannot be undone.
                </p>
                <div className="flex gap-3">
                  <button
                    onClick={handleDeleteAccount}
                    disabled={deleting}
                    className="rounded-lg bg-red-600 px-4 py-2 text-sm font-semibold text-white hover:bg-red-700 disabled:opacity-40 transition"
                  >
                    {deleting ? "Deleting…" : "Yes, delete my account"}
                  </button>
                  <button
                    onClick={() => setConfirmDelete(false)}
                    className="rounded-lg border border-zinc-200 dark:border-zinc-700 px-4 py-2 text-sm text-zinc-600 dark:text-zinc-400 hover:bg-zinc-100 dark:hover:bg-zinc-800 transition"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            )}
          </div>

        </div>
      </div>
      <Footer />
      <FeedbackWidget />
    </main>
  );
}
