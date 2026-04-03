"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { getChannels, getMe, loginUrl, setToken } from "@/lib/api";
import { Footer } from "@/components/Footer";

// Verified unavatar.io handles - duplicated for seamless marquee loop
const CHANNELS = [
  { name: "Jeff Nippard",      handle: "JeffNippard" },
  { name: "Caroline Girvan",   handle: "CarolineGirvan" },
  { name: "Chris Heria",       handle: "ChrisHeria" },
  { name: "Chloe Ting",        handle: "ChloeTing" },
  { name: "Juice & Toya",      handle: "JuiceandToya" },
  { name: "Koboko Fitness",    handle: "KobokoFitness" },
  { name: "Yoga with Adriene", handle: "yogawithadriene" },
  { name: "Move with Nicole",  handle: "movewithnicole" },
  { name: "DanceWithDeepti",   handle: "dancewithdeepti" },
  { name: "HASfit",            handle: "hasfit" },
  { name: "MommaStrong",       handle: "mommastrong" },
  { name: "Sydney Cummings",   handle: "SydneyCummingsHoudyshell" },
];

function ChannelAvatar({ name, handle }: { name: string; handle: string }) {
  const [errored, setErrored] = useState(false);
  if (errored) return null;
  return (
    <div className="flex flex-col items-center gap-2 shrink-0 w-20">
      <img
        src={`https://unavatar.io/youtube/${handle}`}
        alt={name}
        width={64}
        height={64}
        className="w-16 h-16 rounded-full object-cover"
        onError={() => setErrored(true)}
      />
      <span className="text-xs text-zinc-500 dark:text-zinc-400 text-center leading-tight max-w-full truncate px-1">
        {name}
      </span>
    </div>
  );
}

function PausePage() {
  return (
    <main className="min-h-screen bg-white dark:bg-zinc-950 text-zinc-900 dark:text-white flex flex-col">

      {/* Nav */}
      <nav className="flex items-center justify-between px-6 py-5 max-w-6xl mx-auto w-full">
        <span className="font-semibold tracking-tight">Plan My Workout</span>
        <Link
          href="/guide"
          className="text-sm text-zinc-500 dark:text-zinc-400 hover:text-zinc-800 dark:hover:text-zinc-200 transition"
        >
          Guide
        </Link>
      </nav>

      {/* Pause message */}
      <section className="flex-1 flex flex-col items-center justify-center px-6 py-24 text-center max-w-xl mx-auto w-full">
        <div className="mb-6 inline-flex items-center rounded-full bg-amber-100 dark:bg-amber-900/30 border border-amber-200 dark:border-amber-800 px-3 py-1 text-xs text-amber-700 dark:text-amber-400">
          Paused - infrastructure offline
        </div>
        <h1 className="text-4xl font-bold tracking-tight mb-4">
          Taking a break
        </h1>
        <p className="text-zinc-600 dark:text-zinc-400 text-base leading-relaxed mb-8">
          Plan My Workout turns your favourite YouTube fitness channels into a structured weekly plan - automatically.
          The hosted app is currently offline to avoid ongoing server costs, but the project is fully open source.
        </p>
        <div className="flex flex-col sm:flex-row gap-3 justify-center">
          <a
            href="https://github.com/harshitbshah/youtube-workout-planner"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 rounded-lg bg-zinc-900 dark:bg-white px-6 py-3 text-sm font-semibold text-white dark:text-zinc-900 hover:bg-zinc-700 dark:hover:bg-zinc-100 transition"
          >
            <GitHubIcon />
            View on GitHub
          </a>
          <Link
            href="/guide"
            className="inline-flex items-center rounded-lg border border-zinc-200 dark:border-zinc-700 px-6 py-3 text-sm font-semibold text-zinc-700 dark:text-zinc-300 hover:bg-zinc-50 dark:hover:bg-zinc-800 transition"
          >
            Read the guide
          </Link>
        </div>
      </section>

      {/* Self-host note */}
      <section className="px-6 pb-16">
        <div className="max-w-xl mx-auto rounded-xl border border-zinc-100 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900 px-6 py-5">
          <h2 className="text-sm font-semibold mb-2">Run it yourself for free</h2>
          <p className="text-sm text-zinc-500 dark:text-zinc-400 leading-relaxed">
            The GitHub repo includes a CLI mode that runs on GitHub Actions every Sunday - no server required.
            Fork the repo, add your API keys as secrets, and it works at near-zero cost.
            Full setup instructions in the{" "}
            <Link href="/guide" className="underline hover:text-zinc-700 dark:hover:text-zinc-300 transition">
              user guide
            </Link>
            .
          </p>
        </div>
      </section>

      <Footer />
    </main>
  );
}

function GitHubIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <path d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0 1 12 6.844a9.59 9.59 0 0 1 2.504.337c1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.02 10.02 0 0 0 22 12.017C22 6.484 17.522 2 12 2z" />
    </svg>
  );
}

function GoogleIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <path d="M17.64 9.2c0-.637-.057-1.251-.164-1.84H9v3.481h4.844c-.209 1.125-.843 2.078-1.796 2.717v2.258h2.908c1.702-1.567 2.684-3.875 2.684-6.615z" fill="#4285F4"/>
      <path d="M9 18c2.43 0 4.467-.806 5.956-2.184l-2.908-2.258c-.806.54-1.837.86-3.048.86-2.344 0-4.328-1.584-5.036-3.711H.957v2.332A8.997 8.997 0 0 0 9 18z" fill="#34A853"/>
      <path d="M3.964 10.707A5.41 5.41 0 0 1 3.682 9c0-.593.102-1.17.282-1.707V4.961H.957A8.996 8.996 0 0 0 0 9c0 1.452.348 2.827.957 4.039l3.007-2.332z" fill="#FBBC05"/>
      <path d="M9 3.58c1.321 0 2.508.454 3.44 1.345l2.582-2.58C13.463.891 11.426 0 9 0A8.997 8.997 0 0 0 .957 4.961L3.964 6.293C4.672 4.166 6.656 3.58 9 3.58z" fill="#EA4335"/>
    </svg>
  );
}

export default function LandingPage() {
  if (process.env.NEXT_PUBLIC_PAUSED === "true") return <PausePage />;

  const router = useRouter();
  // Only check auth (and show spinner) if there's a stored token to validate.
  // Logged-out visitors see the landing page immediately with no flicker.
  const [checking, setChecking] = useState(() => {
    if (typeof window === "undefined") return false;
    return Boolean(localStorage.getItem("auth_token"));
  });

  useEffect(() => {
    let cancelled = false;
    const params = new URLSearchParams(window.location.search);
    const token = params.get("token");
    if (token) {
      setToken(token);
      window.history.replaceState({}, "", window.location.pathname);
    }
    getMe()
      .then(() => getChannels())
      .then((channels) => {
        if (!cancelled) router.replace(channels.length === 0 ? "/onboarding" : "/dashboard");
      })
      .catch(() => { if (!cancelled) setChecking(false); });
    return () => { cancelled = true; };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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
      <nav className="flex items-center justify-between px-6 py-5 max-w-6xl mx-auto">
        <span className="font-semibold tracking-tight">Plan My Workout</span>
        <div className="flex items-center gap-4">
          <Link
            href="/guide"
            className="text-sm text-zinc-500 dark:text-zinc-400 hover:text-zinc-800 dark:hover:text-zinc-200 transition"
          >
            Guide
          </Link>
          <a
            href={loginUrl()}
            className="rounded-lg bg-zinc-900 dark:bg-white px-4 py-2 text-sm font-semibold text-white dark:text-zinc-900 hover:bg-zinc-700 dark:hover:bg-zinc-100 transition"
          >
            Sign in
          </a>
        </div>
      </nav>

      {/* Hero */}
      <section className="max-w-4xl mx-auto px-6 pt-14 pb-16 text-center">
        <div className="mb-5 inline-flex items-center rounded-full bg-zinc-100 dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 px-3 py-1 text-xs text-zinc-500 dark:text-zinc-400">
          Free - no credit card required
        </div>
        <h1 className="text-5xl sm:text-6xl font-bold leading-[1.1] tracking-tight mb-6">
          Stop watching.<br />
          <span className="text-zinc-400 dark:text-zinc-500">Start doing.</span>
        </h1>
        <p className="text-zinc-600 dark:text-zinc-400 text-lg leading-relaxed mb-8 max-w-xl mx-auto">
          Turn your favourite YouTube fitness channels into a structured weekly plan - automatically.
          A different workout, every day.
        </p>
        <Link
          href="/onboarding"
          className="inline-flex items-center rounded-lg bg-zinc-900 dark:bg-white px-7 py-3.5 text-sm font-semibold text-white dark:text-zinc-900 hover:bg-zinc-700 dark:hover:bg-zinc-100 transition"
        >
          Get started free
        </Link>
        <p className="mt-3 text-xs text-zinc-400 dark:text-zinc-600">
          Ready in under 3 minutes
        </p>
      </section>

      {/* Dashboard screenshot */}
      <section className="max-w-5xl mx-auto px-6 pb-20">
        <div className="rounded-2xl border border-zinc-200 dark:border-zinc-700 overflow-hidden shadow-2xl shadow-zinc-200/60 dark:shadow-zinc-950/60">
          {/* Browser chrome */}
          <div className="flex items-center gap-1.5 px-4 py-3 bg-zinc-100 dark:bg-zinc-800 border-b border-zinc-200 dark:border-zinc-700">
            <div className="w-3 h-3 rounded-full bg-zinc-300 dark:bg-zinc-600" />
            <div className="w-3 h-3 rounded-full bg-zinc-300 dark:bg-zinc-600" />
            <div className="w-3 h-3 rounded-full bg-zinc-300 dark:bg-zinc-600" />
            <div className="ml-3 flex-1 max-w-xs rounded-md bg-zinc-200 dark:bg-zinc-700 px-3 py-1 text-[11px] text-zinc-500 dark:text-zinc-400">
              planmyworkout.app/dashboard
            </div>
          </div>
          {/* Screenshots - swap with theme */}
          <img
            src="/dashboard-light.png"
            alt="Plan My Workout dashboard"
            className="w-full block dark:hidden"
          />
          <img
            src="/dashboard-dark.png"
            alt="Plan My Workout dashboard"
            className="w-full hidden dark:block"
          />
        </div>
      </section>

      {/* Channel marquee */}
      <section className="border-t border-zinc-100 dark:border-zinc-800/60 py-8 overflow-hidden">
        <p className="text-center text-[11px] font-semibold text-zinc-400 uppercase tracking-widest mb-6">
          Works with creators you already follow
        </p>
        <div className="flex gap-8 animate-marquee">
          {[...CHANNELS, ...CHANNELS].map((ch, i) => (
            <ChannelAvatar key={i} name={ch.name} handle={ch.handle} />
          ))}
        </div>
      </section>

      {/* How it works */}
      <section className="px-6 py-24 border-t border-zinc-100 dark:border-zinc-800/60">
        <div className="max-w-6xl mx-auto">
          <h2 className="text-[11px] font-semibold text-zinc-400 uppercase tracking-widest text-center mb-16">
            How it works
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-12">
            <div>
              <div className="text-4xl font-bold text-zinc-100 dark:text-zinc-800 mb-4">01</div>
              <h3 className="text-base font-semibold mb-2">Add your channels</h3>
              <p className="text-sm text-zinc-500 dark:text-zinc-400 leading-relaxed">
                Pick the YouTube fitness creators you already follow. We pull from their libraries - not generic content.
              </p>
            </div>
            <div>
              <div className="text-4xl font-bold text-zinc-100 dark:text-zinc-800 mb-4">02</div>
              <h3 className="text-base font-semibold mb-2">Set your split</h3>
              <p className="text-sm text-zinc-500 dark:text-zinc-400 leading-relaxed">
                Tell us your training days, workout types, and session length. Takes about 2 minutes.
              </p>
            </div>
            <div>
              <div className="text-4xl font-bold text-zinc-100 dark:text-zinc-800 mb-4">03</div>
              <h3 className="text-base font-semibold mb-2">Get your plan</h3>
              <p className="text-sm text-zinc-500 dark:text-zinc-400 leading-relaxed">
                Every Sunday we scan your channels and build a fresh weekly plan from videos that match your schedule. Just press play on Monday.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Bottom CTA */}
      <section className="px-6 pb-20">
        <div className="max-w-5xl mx-auto rounded-2xl bg-zinc-900 dark:bg-zinc-800 px-8 py-16 text-center">
          <h2 className="text-3xl font-bold text-white mb-4">
            Ready to stop guessing?
          </h2>
          <p className="text-zinc-400 text-sm mb-8 max-w-sm mx-auto leading-relaxed">
            Your first personalised plan is waiting. Three minutes from now you&apos;ll know exactly what to do on Monday.
          </p>
          <Link
            href="/onboarding"
            className="inline-flex items-center rounded-lg bg-white px-8 py-3.5 text-sm font-semibold text-zinc-900 hover:bg-zinc-100 transition"
          >
            Get started free
          </Link>
        </div>
      </section>

      <Footer />
    </main>
  );
}
