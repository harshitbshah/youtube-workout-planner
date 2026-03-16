"use client";
import { useEffect } from "react";
import { initSentry } from "../../sentry.config";

export default function SentryInit() {
  useEffect(() => {
    initSentry();
  }, []);
  return null;
}
