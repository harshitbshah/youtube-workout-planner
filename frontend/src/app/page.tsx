"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { getChannels, getMe, loginUrl, setToken } from "@/lib/api";
import { Footer } from "@/components/Footer";

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
      .then(() => getChannels())
      .then((channels) =>
        router.replace(channels.length === 0 ? "/onboarding" : "/dashboard")
      )
      .catch(() => setChecking(false));
  }, [router]);

  if (checking) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-white dark:bg-zinc-950">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-zinc-300 border-t-zinc-900 dark:border-zinc-600 dark:border-t-white" />
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-white dark:bg-zinc-950 text-zinc-900 dark:text-white">

      {/* Nav */}
      <nav className="flex items-center justify-between px-6 py-5 max-w-5xl mx-auto">
        <span className="font-semibold text-zinc-900 dark:text-white tracking-tight">Plan My Workout</span>
        <div className="flex items-center gap-3">
          <Link
            href="/guide"
            className="text-sm text-zinc-600 dark:text-zinc-400 hover:text-zinc-800 dark:hover:text-zinc-200 transition"
          >
            Guide
          </Link>
          <a
            href={loginUrl()}
            className="rounded-lg border border-zinc-200 dark:border-zinc-700 px-4 py-2 text-sm text-zinc-700 dark:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-800 transition"
          >
            Sign in
          </a>
        </div>
      </nav>

      {/* Hero */}
      <section className="flex flex-col items-center text-center px-6 pt-20 pb-24 max-w-3xl mx-auto">
        <div className="mb-4 rounded-full bg-zinc-100 dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 px-3 py-1 text-xs text-zinc-600 dark:text-zinc-400 tracking-wide">
          Free · No credit card required
        </div>
        <h1 className="text-4xl sm:text-5xl font-bold text-zinc-900 dark:text-white leading-tight mb-6">
          Your YouTube workout plan,{" "}
          <span className="text-zinc-600 dark:text-zinc-400">on autopilot.</span>
        </h1>
        <p className="text-zinc-600 dark:text-zinc-400 text-lg leading-relaxed mb-10 max-w-xl">
          Add your favourite fitness channels, set your weekly training split, and
          get a fresh plan curated from content you already love — every Sunday.
        </p>
        <a
          href={loginUrl()}
          className="flex items-center gap-2.5 rounded-lg bg-zinc-900 dark:bg-white px-8 py-3.5 text-sm font-semibold text-white dark:text-zinc-900 hover:bg-zinc-700 dark:hover:bg-zinc-100 transition"
        >
          <svg width="18" height="18" viewBox="0 0 18 18" xmlns="http://www.w3.org/2000/svg">
            <path d="M17.64 9.2c0-.637-.057-1.251-.164-1.84H9v3.481h4.844c-.209 1.125-.843 2.078-1.796 2.717v2.258h2.908c1.702-1.567 2.684-3.875 2.684-6.615z" fill="#4285F4"/>
            <path d="M9 18c2.43 0 4.467-.806 5.956-2.184l-2.908-2.258c-.806.54-1.837.86-3.048.86-2.344 0-4.328-1.584-5.036-3.711H.957v2.332A8.997 8.997 0 0 0 9 18z" fill="#34A853"/>
            <path d="M3.964 10.707A5.41 5.41 0 0 1 3.682 9c0-.593.102-1.17.282-1.707V4.961H.957A8.996 8.996 0 0 0 0 9c0 1.452.348 2.827.957 4.039l3.007-2.332z" fill="#FBBC05"/>
            <path d="M9 3.58c1.321 0 2.508.454 3.44 1.345l2.582-2.58C13.463.891 11.426 0 9 0A8.997 8.997 0 0 0 .957 4.961L3.964 6.293C4.672 4.166 6.656 3.58 9 3.58z" fill="#EA4335"/>
          </svg>
          Get started free
        </a>
        <p className="mt-4 text-xs text-zinc-500">
          Already have an account?{" "}
          <a href={loginUrl()} className="underline underline-offset-2 hover:text-zinc-700 dark:hover:text-zinc-300 transition">
            Sign in
          </a>
        </p>
      </section>

      {/* How it works */}
      <section className="px-6 py-20 border-t border-zinc-200 dark:border-zinc-800">
        <div className="max-w-5xl mx-auto">
          <h2 className="text-xs font-semibold text-zinc-500 uppercase tracking-widest text-center mb-12">
            How it works
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-8">
            {HOW_IT_WORKS.map(({ step, title, body }) => (
              <div key={step}>
                <div className="text-3xl font-bold text-zinc-200 dark:text-zinc-700 mb-3">{step}</div>
                <h3 className="text-base font-semibold text-zinc-900 dark:text-white mb-2">{title}</h3>
                <p className="text-sm text-zinc-600 dark:text-zinc-400 leading-relaxed">{body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Features */}
      <section className="px-6 py-20 border-t border-zinc-200 dark:border-zinc-800">
        <div className="max-w-5xl mx-auto">
          <h2 className="text-xs font-semibold text-zinc-500 uppercase tracking-widest text-center mb-12">
            Why Plan My Workout
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-8">
            {FEATURES.map(({ title, body }) => (
              <div key={title} className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-6">
                <h3 className="text-sm font-semibold text-zinc-900 dark:text-white mb-2">{title}</h3>
                <p className="text-sm text-zinc-600 dark:text-zinc-400 leading-relaxed">{body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Bottom CTA */}
      <section className="px-6 py-24 border-t border-zinc-200 dark:border-zinc-800 text-center">
        <h2 className="text-2xl font-bold text-zinc-900 dark:text-white mb-4">Ready to stop guessing?</h2>
        <p className="text-zinc-600 dark:text-zinc-400 text-sm mb-8">
          Join and get your first personalised plan in minutes.
        </p>
        <a
          href={loginUrl()}
          className="rounded-lg bg-zinc-900 dark:bg-white px-8 py-3.5 text-sm font-semibold text-white dark:text-zinc-900 hover:bg-zinc-700 dark:hover:bg-zinc-100 transition"
        >
          Get started free →
        </a>
      </section>

      <Footer />

    </main>
  );
}
