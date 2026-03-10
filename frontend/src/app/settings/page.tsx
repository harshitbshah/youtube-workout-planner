"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Footer } from "@/components/Footer";
import {
  getMe,
  getChannels,
  getSchedule,
  patchMe,
  deleteMe,
  updateSchedule,
  logout,
  type User,
  type ChannelResponse,
  type ScheduleSlot,
} from "@/lib/api";
import ChannelManager from "@/components/ChannelManager";
import ScheduleEditor from "@/components/ScheduleEditor";

function SectionCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900 p-6">
      <h2 className="text-sm font-semibold text-white mb-5">{title}</h2>
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

  // Profile
  const [displayName, setDisplayName] = useState("");
  const [savingName, setSavingName] = useState(false);
  const [nameStatus, setNameStatus] = useState<"idle" | "ok" | "err">("idle");

  // Schedule
  const [savingSchedule, setSavingSchedule] = useState(false);
  const [scheduleStatus, setScheduleStatus] = useState<"idle" | "ok" | "err">("idle");

  // Danger zone
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    Promise.all([getMe(), getChannels(), getSchedule()])
      .then(([u, ch, sched]) => {
        setUser(u);
        setDisplayName(u.display_name ?? "");
        setChannels(ch);
        setSchedule(sched.schedule);
      })
      .catch(() => router.replace("/"))
      .finally(() => setLoading(false));
  }, [router]);

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
      <main className="flex min-h-screen items-center justify-center bg-zinc-950">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-zinc-600 border-t-white" />
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-zinc-950 px-4 py-8">
      <div className="max-w-2xl mx-auto">

        {/* Header */}
        <div className="flex items-center gap-4 mb-8">
          <Link href="/dashboard" className="text-zinc-500 hover:text-zinc-300 text-sm transition">
            ← Dashboard
          </Link>
          <h1 className="text-2xl font-bold text-white">Settings</h1>
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
                    className="flex-1 rounded-lg bg-zinc-800 border border-zinc-700 px-4 py-2.5 text-sm text-white placeholder-zinc-500 focus:outline-none focus:border-zinc-500"
                  />
                  <button
                    onClick={handleSaveName}
                    disabled={savingName || displayName === (user?.display_name ?? "")}
                    className="rounded-lg bg-white px-4 py-2.5 text-sm font-semibold text-zinc-900 hover:bg-zinc-100 disabled:opacity-40 transition"
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
                <p className="text-sm text-zinc-400">{user?.email}</p>
              </div>
            </div>
          </SectionCard>

          {/* Channels */}
          <SectionCard title="Channels">
            <p className="text-xs text-zinc-500 mb-4">
              Add or remove YouTube fitness channels. Changes take effect on the next weekly scan.
            </p>
            <ChannelManager channels={channels} onChannelsChange={setChannels} />
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
                className="rounded-lg bg-white px-5 py-2.5 text-sm font-semibold text-zinc-900 hover:bg-zinc-100 disabled:opacity-40 transition"
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
          <div className="rounded-xl border border-red-900/50 bg-zinc-900 p-6">
            <h2 className="text-sm font-semibold text-red-400 mb-2">Danger zone</h2>
            <p className="text-xs text-zinc-500 mb-5">
              Permanently delete your account and all data — channels, schedule, plan history.
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
                    className="rounded-lg border border-zinc-700 px-4 py-2 text-sm text-zinc-400 hover:bg-zinc-800 transition"
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
    </main>
  );
}
