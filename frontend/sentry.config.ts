import * as Sentry from "@sentry/nextjs";

export function initSentry() {
  console.log("[Sentry] init called, DSN:", process.env.NEXT_PUBLIC_SENTRY_DSN ? "set" : "MISSING");
  Sentry.init({
    dsn: process.env.NEXT_PUBLIC_SENTRY_DSN,
    tracesSampleRate: 0.1,
    environment: process.env.NODE_ENV,
    enabled: process.env.NODE_ENV === "production",
  });
}
