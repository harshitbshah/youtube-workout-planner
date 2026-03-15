import Link from "next/link";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Page Not Found — Plan My Workout",
};

export default function NotFound() {
  return (
    <main className="min-h-screen bg-white dark:bg-zinc-950 flex flex-col items-center justify-center px-4 text-center">
      <p className="text-5xl font-bold text-zinc-200 dark:text-zinc-700 mb-6">404</p>
      <h1 className="text-xl font-semibold text-zinc-900 dark:text-white mb-2">Page not found</h1>
      <p className="text-sm text-zinc-500 dark:text-zinc-400 mb-8">
        The page you&apos;re looking for doesn&apos;t exist.
      </p>
      <Link
        href="/"
        className="rounded-lg border border-zinc-200 dark:border-zinc-700 px-5 py-2.5 text-sm font-medium text-zinc-700 dark:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-800 transition"
      >
        ← Back to home
      </Link>
    </main>
  );
}
