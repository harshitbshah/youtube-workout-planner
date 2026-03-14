"use client";

import { useState } from "react";
import { submitFeedback } from "@/lib/api";

const CATEGORIES = [
  { value: "feedback", label: "💬 General feedback" },
  { value: "help",     label: "🙋 I need help" },
  { value: "bug",      label: "🐛 Found a bug" },
];

export default function FeedbackWidget() {
  const [open, setOpen] = useState(false);
  const [category, setCategory] = useState("feedback");
  const [message, setMessage] = useState("");
  const [status, setStatus] = useState<"idle" | "submitting" | "done" | "err">("idle");

  async function handleSubmit() {
    if (!message.trim()) return;
    setStatus("submitting");
    try {
      await submitFeedback(category, message);
      setStatus("done");
      setMessage("");
    } catch {
      setStatus("err");
    }
  }

  function handleClose() {
    setOpen(false);
    setStatus("idle");
    setMessage("");
    setCategory("feedback");
  }

  return (
    <>
      {/* Floating button */}
      <button
        onClick={() => setOpen(true)}
        className="fixed bottom-6 right-6 z-40 flex items-center gap-2 rounded-full bg-white px-4 py-2.5 text-sm font-semibold text-zinc-900 shadow-lg ring-1 ring-zinc-200 hover:bg-zinc-100 transition cursor-pointer"
      >
        <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 shrink-0" viewBox="0 0 20 20" fill="currentColor">
          <path d="M2 10.5a1.5 1.5 0 113 0v6a1.5 1.5 0 01-3 0v-6zM6 10.333v5.43a2 2 0 001.106 1.79l.05.025A4 4 0 008.943 18h5.416a2 2 0 001.962-1.608l1.2-6A2 2 0 0015.56 8H12V4a2 2 0 00-2-2 1 1 0 00-1 1v.667a4 4 0 01-.8 2.4L6.8 7.933a4 4 0 00-.8 2.4z" />
        </svg>
        Feedback
      </button>

      {/* Backdrop */}
      {open && (
        <div
          className="fixed inset-0 z-40 bg-black/50"
          onClick={handleClose}
        />
      )}

      {/* Modal */}
      {open && (
        <div className="fixed bottom-20 z-50 left-4 right-4 sm:left-auto sm:right-6 sm:w-full sm:max-w-sm rounded-xl border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-900 p-5 shadow-2xl">

          {status === "done" ? (
            <div className="py-6 text-center">
              <p className="text-zinc-900 dark:text-white font-medium mb-1">Thanks for the feedback!</p>
              <p className="text-sm text-zinc-600 dark:text-zinc-400 mb-5">We&apos;ll get back to you if needed.</p>
              <button
                onClick={handleClose}
                className="rounded-lg bg-white px-5 py-2 text-sm font-semibold text-zinc-900 hover:bg-zinc-100 transition"
              >
                Close
              </button>
            </div>
          ) : (
            <>
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-semibold text-zinc-900 dark:text-white">Share feedback or get help</h3>
                <button
                  onClick={handleClose}
                  className="text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300 text-lg leading-none transition"
                >
                  ✕
                </button>
              </div>

              <div className="space-y-3">
                <div className="flex gap-2">
                  {CATEGORIES.map((c) => (
                    <button
                      key={c.value}
                      onClick={() => setCategory(c.value)}
                      className={`flex-1 rounded-lg border px-2 py-2 text-xs font-medium transition cursor-pointer ${
                        category === c.value
                          ? "border-white bg-white text-zinc-900"
                          : "border-zinc-200 dark:border-zinc-700 text-zinc-600 dark:text-zinc-400 hover:border-zinc-400 dark:hover:border-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-200"
                      }`}
                    >
                      {c.label}
                    </button>
                  ))}
                </div>

                <textarea
                  value={message}
                  onChange={(e) => setMessage(e.target.value)}
                  placeholder="Tell us what's on your mind…"
                  rows={4}
                  className="w-full rounded-lg bg-zinc-100 dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 px-3 py-2.5 text-sm text-zinc-900 dark:text-white placeholder-zinc-500 focus:outline-none focus:border-zinc-500 resize-none"
                />

                {status === "err" && (
                  <p className="text-xs text-red-400">Something went wrong — try again.</p>
                )}

                <button
                  onClick={handleSubmit}
                  disabled={!message.trim() || status === "submitting"}
                  className="w-full rounded-lg bg-white py-2.5 text-sm font-semibold text-zinc-900 hover:bg-zinc-100 disabled:opacity-40 transition"
                >
                  {status === "submitting" ? "Sending…" : "Send"}
                </button>
              </div>
            </>
          )}
        </div>
      )}
    </>
  );
}
