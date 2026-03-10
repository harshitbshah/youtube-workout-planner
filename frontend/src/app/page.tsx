"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { getMe, loginUrl, setToken } from "@/lib/api";

const HOW_IT_WORKS = [
  {
    step: "01",
    title: "Add your channels",
    body: "Pick the YouTube fitness creators you already follow. We pull from their libraries — not generic content.",
  },
  {
    step: "02",
    title: "Set your split",
    body: "Tell us your weekly training goals — strength, HIIT, cardio, rest days, duration. You're in control.",
  },
  {
    step: "03",
    title: "Get your plan",
    body: "Every Sunday we scan your channels, classify videos with AI, and build a fresh personalised weekly plan.",
  },
];

const FEATURES = [
  {
    title: "Powered by creators you love",
    body: "No algorithm pushing random content. Your plan is built exclusively from channels you've chosen.",
  },
  {
    title: "Intelligent classification",
    body: "Every video is classified by workout type, body focus, and difficulty so the right video lands on the right day.",
  },
  {
    title: "No decision fatigue",
    body: "Open the app on Monday and your workout is waiting. Just press play.",
  },
];

export default function LandingPage() {
  const router = useRouter();
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    // Extract token from URL after OAuth redirect (e.g. /?token=xxx)
    const params = new URLSearchParams(window.location.search);
    const token = params.get("token");
    if (token) {
      setToken(token);
      window.history.replaceState({}, "", window.location.pathname);
    }

    getMe()
      .then(() => router.replace("/dashboard"))
      .catch(() => setChecking(false));
  }, [router]);

  if (checking) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-zinc-950">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-zinc-600 border-t-white" />
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-zinc-950 text-white">

      {/* Nav */}
      <nav className="flex items-center justify-between px-6 py-5 max-w-5xl mx-auto">
        <span className="font-semibold text-white tracking-tight">Workout Planner</span>
        <div className="flex items-center gap-3">
          <Link
            href="/guide"
            className="text-sm text-zinc-400 hover:text-zinc-200 transition"
          >
            Guide
          </Link>
          <a
            href={loginUrl()}
            className="rounded-lg border border-zinc-700 px-4 py-2 text-sm text-zinc-300 hover:bg-zinc-800 transition"
          >
            Sign in
          </a>
        </div>
      </nav>

      {/* Hero */}
      <section className="flex flex-col items-center text-center px-6 pt-20 pb-24 max-w-3xl mx-auto">
        <div className="mb-4 rounded-full bg-zinc-800 border border-zinc-700 px-3 py-1 text-xs text-zinc-400 tracking-wide">
          Free · No credit card required
        </div>
        <h1 className="text-4xl sm:text-5xl font-bold text-white leading-tight mb-6">
          Your YouTube workout plan,{" "}
          <span className="text-zinc-400">on autopilot.</span>
        </h1>
        <p className="text-zinc-400 text-lg leading-relaxed mb-10 max-w-xl">
          Add your favourite fitness channels, set your weekly training split, and
          get a fresh plan curated from content you already love — every Sunday.
        </p>
        <a
          href={loginUrl()}
          className="rounded-lg bg-white px-8 py-3.5 text-sm font-semibold text-zinc-900 hover:bg-zinc-100 transition"
        >
          Get started free →
        </a>
        <p className="mt-4 text-xs text-zinc-600">Sign up with your Google account. Takes 2 minutes.</p>
      </section>

      {/* How it works */}
      <section className="px-6 py-20 border-t border-zinc-800">
        <div className="max-w-5xl mx-auto">
          <h2 className="text-xs font-semibold text-zinc-500 uppercase tracking-widest text-center mb-12">
            How it works
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-8">
            {HOW_IT_WORKS.map(({ step, title, body }) => (
              <div key={step}>
                <div className="text-3xl font-bold text-zinc-700 mb-3">{step}</div>
                <h3 className="text-base font-semibold text-white mb-2">{title}</h3>
                <p className="text-sm text-zinc-400 leading-relaxed">{body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Features */}
      <section className="px-6 py-20 border-t border-zinc-800">
        <div className="max-w-5xl mx-auto">
          <h2 className="text-xs font-semibold text-zinc-500 uppercase tracking-widest text-center mb-12">
            Why Workout Planner
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-8">
            {FEATURES.map(({ title, body }) => (
              <div key={title} className="rounded-xl border border-zinc-800 bg-zinc-900 p-6">
                <h3 className="text-sm font-semibold text-white mb-2">{title}</h3>
                <p className="text-sm text-zinc-400 leading-relaxed">{body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Bottom CTA */}
      <section className="px-6 py-24 border-t border-zinc-800 text-center">
        <h2 className="text-2xl font-bold text-white mb-4">Ready to stop guessing?</h2>
        <p className="text-zinc-400 text-sm mb-8">
          Join and get your first personalised plan in minutes.
        </p>
        <a
          href={loginUrl()}
          className="rounded-lg bg-white px-8 py-3.5 text-sm font-semibold text-zinc-900 hover:bg-zinc-100 transition"
        >
          Get started free →
        </a>
      </section>

      {/* Footer */}
      <footer className="border-t border-zinc-800 px-6 py-6 text-center space-y-2">
        <div className="flex items-center justify-center gap-4 text-xs text-zinc-600">
          <Link href="/guide" className="hover:text-zinc-400 transition">User Guide</Link>
        </div>
        <p className="text-xs text-zinc-600">© 2026 Workout Planner. Built with YouTube + AI.</p>
      </footer>

    </main>
  );
}
