"use client";

import { useEffect, useState } from "react";
import { getImpersonationEmail, stopImpersonation } from "@/lib/api";

export default function ImpersonationBanner() {
  const [email, setEmail] = useState<string | null>(null);

  useEffect(() => {
    setEmail(getImpersonationEmail());
  }, []);

  if (!email) return null;

  const handleExit = () => {
    stopImpersonation();
    window.location.href = "/admin";
  };

  return (
    <div className="fixed top-0 left-0 right-0 z-50 bg-amber-400 text-amber-950 text-sm font-medium flex items-center justify-between px-4 py-2 shadow-md">
      <div className="flex items-center gap-2">
        <svg className="w-4 h-4 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
            d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
            d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
        </svg>
        <span>Viewing as <strong>{email}</strong></span>
      </div>
      <button
        onClick={handleExit}
        className="ml-4 px-3 py-1 rounded-lg bg-amber-950 text-amber-50 text-xs font-semibold hover:bg-amber-900 transition-colors"
      >
        Exit
      </button>
    </div>
  );
}
