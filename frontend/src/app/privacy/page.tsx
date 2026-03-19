import Link from "next/link";
import type { Metadata } from "next";
import { LegalSection as Section } from "@/components/LegalSection";

export const metadata: Metadata = {
  title: "Privacy Policy - Plan My Workout",
};

export default function PrivacyPage() {
  return (
    <main className="min-h-screen bg-white dark:bg-zinc-950 px-4 py-12">
      <div className="max-w-2xl mx-auto space-y-8 text-zinc-700 dark:text-zinc-300">

        <div>
          <Link href="/" className="text-xs text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-400 transition">← Home</Link>
          <h1 className="text-2xl font-bold text-zinc-900 dark:text-white mt-4">Privacy Policy</h1>
          <p className="text-xs text-zinc-500 mt-1">Effective date: 10 March 2026</p>
        </div>

        <Section title="1. Who we are">
          <p>Plan My Workout ("we", "us") is a web application that helps you discover and plan workout videos from YouTube channels you choose.</p>
        </Section>

        <Section title="2. What data we collect">
          <p>When you sign in with Google, we receive and store:</p>
          <ul>
            <li>Your name and profile picture (for display purposes)</li>
            <li>Your primary Google account email address (used as your account identifier)</li>
            <li>A Google OAuth token, which we use to create and manage a YouTube playlist in your account on your request</li>
          </ul>
          <p>When you use the app, we also store:</p>
          <ul>
            <li>The YouTube channel URLs you add</li>
            <li>Metadata about videos from those channels (title, description, duration, tags) - we do not store video files</li>
            <li>Your weekly workout schedule preferences</li>
            <li>Your generated workout plans</li>
            <li>Timestamps of your account activity</li>
          </ul>
        </Section>

        <Section title="3. How we use your data">
          <p>We use your data solely to provide the service:</p>
          <ul>
            <li>To identify your account and show your content</li>
            <li>To scan your chosen YouTube channels for workout videos</li>
            <li>To classify videos using AI (Anthropic Claude) and generate a personalised weekly plan</li>
            <li>To publish your plan to a YouTube playlist in your account, if you request it</li>
          </ul>
          <p>We do not sell your data. We do not use your data for advertising.</p>
        </Section>

        <Section title="4. YouTube API Services">
          <p>
            This app uses the YouTube API Services to read video metadata from channels you select and to create and manage a YouTube playlist in your account.
          </p>
          <p>
            By using this app, you are also agreeing to the{" "}
            <a href="https://www.youtube.com/t/terms" target="_blank" rel="noopener noreferrer" className="text-zinc-600 dark:text-zinc-400 underline hover:text-zinc-900 dark:hover:text-white">YouTube Terms of Service</a>{" "}
            and the{" "}
            <a href="https://policies.google.com/privacy" target="_blank" rel="noopener noreferrer" className="text-zinc-600 dark:text-zinc-400 underline hover:text-zinc-900 dark:hover:text-white">Google Privacy Policy</a>.
          </p>
          <p>
            You can revoke this app&apos;s access to your YouTube account at any time via your{" "}
            <a href="https://myaccount.google.com/permissions" target="_blank" rel="noopener noreferrer" className="text-zinc-600 dark:text-zinc-400 underline hover:text-zinc-900 dark:hover:text-white">Google Account security settings</a>.
          </p>
        </Section>

        <Section title="5. AI processing">
          <p>Video metadata (titles, descriptions, tags) is sent to Anthropic&apos;s API for classification into workout categories. No personally identifiable information is sent to Anthropic. Anthropic&apos;s privacy policy applies to that processing.</p>
        </Section>

        <Section title="6. Data retention and deletion">
          <p>You can delete your account at any time from the Settings page. This permanently deletes all your data including your channels, videos, plans, schedule, and OAuth credentials. YouTube OAuth tokens are deleted immediately upon account deletion, in accordance with Google API ToS requirements.</p>
        </Section>

        <Section title="7. Data security">
          <p>OAuth tokens are encrypted at rest using AES-256 (Fernet). Your data is stored on Railway&apos;s managed PostgreSQL infrastructure.</p>
        </Section>

        <Section title="8. Third-party services">
          <p>We use the following third-party services to operate the app:</p>
          <ul>
            <li><strong className="text-zinc-800 dark:text-zinc-200">Google OAuth</strong> - sign-in and YouTube access</li>
            <li><strong className="text-zinc-800 dark:text-zinc-200">Anthropic Claude</strong> - AI video classification</li>
            <li><strong className="text-zinc-800 dark:text-zinc-200">Railway</strong> - backend hosting and database</li>
            <li><strong className="text-zinc-800 dark:text-zinc-200">Vercel</strong> - frontend hosting</li>
          </ul>
        </Section>

        <Section title="9. Children's privacy">
          <p>This app is not intended for users under 13. We do not knowingly collect data from children.</p>
        </Section>

        <Section title="10. Changes to this policy">
          <p>We will update this page if the policy changes and revise the effective date. Continued use of the app after changes constitutes acceptance.</p>
        </Section>

        <Section title="11. Contact">
          <p>Questions? Open an issue on <a href="https://github.com/harshitbshah/youtube-workout-planner" className="text-zinc-600 dark:text-zinc-400 underline hover:text-zinc-900 dark:hover:text-white">GitHub</a>.</p>
        </Section>

      </div>
    </main>
  );
}

