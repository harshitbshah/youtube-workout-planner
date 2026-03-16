"use client";

export default function OfflinePage() {
  return (
    <div className="min-h-screen bg-white dark:bg-zinc-950 flex items-center justify-center p-6">
      <div className="text-center max-w-sm">
        {/* Icon */}
        <div className="w-16 h-16 rounded-2xl bg-zinc-100 dark:bg-zinc-800 flex items-center justify-center mx-auto mb-6">
          <svg
            className="w-8 h-8 text-zinc-400"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={1.5}
              d="M3 3l18 18M8.111 8.111A3 3 0 0012 6a3 3 0 013 3 3 3 0 01-.111.889M6.343 6.343A8 8 0 004 12a8 8 0 0011.657 5.657M12 18a6 6 0 006-6 6 6 0 00-.343-2M15 9a3 3 0 00-3-3"
            />
          </svg>
        </div>

        <h1 className="text-xl font-bold text-zinc-900 dark:text-white mb-2">
          You&apos;re offline
        </h1>
        <p className="text-sm text-zinc-500 dark:text-zinc-400 leading-relaxed mb-6">
          No internet connection right now. Your previously loaded workout plan may still
          be visible - try going back to the dashboard.
        </p>

        <div className="flex flex-col gap-3">
          <a
            href="/dashboard"
            className="w-full bg-zinc-900 dark:bg-white text-white dark:text-zinc-900 text-sm font-semibold py-3 px-4 rounded-xl hover:opacity-90 transition-opacity text-center"
          >
            Go to dashboard
          </a>
          <button
            onClick={() => window.location.reload()}
            className="w-full border border-zinc-200 dark:border-zinc-700 text-zinc-600 dark:text-zinc-400 text-sm font-medium py-3 px-4 rounded-xl hover:bg-zinc-50 dark:hover:bg-zinc-800 transition-colors"
          >
            Try again
          </button>
        </div>
      </div>
    </div>
  );
}
