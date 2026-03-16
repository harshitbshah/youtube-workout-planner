"use client";

import { useEffect, useState } from "react";

interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
}

const DISMISSED_KEY = "pwa-install-dismissed";

export default function PWAInstallPrompt() {
  const [installEvent, setInstallEvent] = useState<BeforeInstallPromptEvent | null>(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    // Don't show if already dismissed this session (or permanently)
    if (sessionStorage.getItem(DISMISSED_KEY)) return;

    const handler = (e: Event) => {
      e.preventDefault();
      setInstallEvent(e as BeforeInstallPromptEvent);
      setVisible(true);
    };

    window.addEventListener("beforeinstallprompt", handler);
    return () => window.removeEventListener("beforeinstallprompt", handler);
  }, []);

  const handleInstall = async () => {
    if (!installEvent) return;
    await installEvent.prompt();
    const { outcome } = await installEvent.userChoice;
    if (outcome === "accepted") {
      setVisible(false);
    }
  };

  const handleDismiss = () => {
    sessionStorage.setItem(DISMISSED_KEY, "1");
    setVisible(false);
  };

  if (!visible) return null;

  return (
    <div className="fixed bottom-20 left-4 right-4 sm:left-auto sm:right-24 sm:w-80 z-40 bg-zinc-900 dark:bg-zinc-800 text-white rounded-xl shadow-2xl border border-zinc-700 p-4 flex items-start gap-3">
      {/* Icon */}
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src="/icons/icon-192.png" alt="" className="w-10 h-10 rounded-lg flex-shrink-0" />
      <div className="flex-1 min-w-0">
        <p className="text-sm font-semibold leading-tight">Add to Home Screen</p>
        <p className="text-xs text-zinc-400 mt-0.5 leading-snug">
          Install Plan My Workout for quick access and offline viewing.
        </p>
        <div className="flex gap-2 mt-3">
          <button
            onClick={handleInstall}
            className="flex-1 text-xs font-semibold bg-white text-zinc-900 rounded-lg py-1.5 px-3 hover:bg-zinc-100 transition-colors"
          >
            Install
          </button>
          <button
            onClick={handleDismiss}
            className="flex-1 text-xs font-medium text-zinc-400 hover:text-white rounded-lg py-1.5 px-3 border border-zinc-700 hover:border-zinc-500 transition-colors"
          >
            Not now
          </button>
        </div>
      </div>
    </div>
  );
}
