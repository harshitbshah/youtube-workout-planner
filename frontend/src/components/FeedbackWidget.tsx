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
        className="fixed bottom-6 right-6 z-40 rounded-full bg-zinc-800 border border-zinc-700 px-4 py-2 text-sm text-zinc-300 hover:bg-zinc-700 hover:text-white transition shadow-lg"
      >
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
        <div className="fixed bottom-20 right-6 z-50 w-full max-w-sm rounded-xl border border-zinc-700 bg-zinc-900 p-5 shadow-2xl">

          {status === "done" ? (
            <div className="py-6 text-center">
              <p className="text-white font-medium mb-1">Thanks for the feedback!</p>
              <p className="text-sm text-zinc-400 mb-5">We&apos;ll get back to you if needed.</p>
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
                <h3 className="text-sm font-semibold text-white">Share feedback or get help</h3>
                <button
                  onClick={handleClose}
                  className="text-zinc-500 hover:text-zinc-300 text-lg leading-none transition"
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
                      className={`flex-1 rounded-lg border px-2 py-2 text-xs font-medium transition ${
                        category === c.value
                          ? "border-white bg-white text-zinc-900"
                          : "border-zinc-700 text-zinc-400 hover:border-zinc-500 hover:text-zinc-200"
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
                  className="w-full rounded-lg bg-zinc-800 border border-zinc-700 px-3 py-2.5 text-sm text-white placeholder-zinc-500 focus:outline-none focus:border-zinc-500 resize-none"
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
