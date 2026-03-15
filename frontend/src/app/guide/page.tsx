import Link from "next/link";
import { Footer } from "@/components/Footer";

const SECTIONS = [
  { id: "getting-started", label: "Getting started" },
  { id: "your-plan", label: "Your weekly plan" },
  { id: "library", label: "Library" },
  { id: "settings", label: "Settings" },
  { id: "how-it-works", label: "How the plan is built" },
  { id: "publish", label: "Publish to YouTube" },
  { id: "faq", label: "FAQ" },
];

function Section({ id, title, children }: { id: string; title: string; children: React.ReactNode }) {
  return (
    <section id={id} className="scroll-mt-8 pt-10 first:pt-0">
      <h2 className="text-xl font-bold text-zinc-900 dark:text-white mb-4 pb-3 border-b border-zinc-200 dark:border-zinc-800">{title}</h2>
      <div className="space-y-4 text-zinc-600 dark:text-zinc-400 text-sm leading-relaxed">{children}</div>
    </section>
  );
}

function Note({ children }: { children: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-zinc-200 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-900 px-4 py-3 text-zinc-600 dark:text-zinc-400 text-sm">
      {children}
    </div>
  );
}

function Table({ rows }: { rows: [string, string][] }) {
  return (
    <div className="overflow-x-auto rounded-lg border border-zinc-200 dark:border-zinc-800">
      <table className="w-full text-sm">
        <tbody>
          {rows.map(([a, b], i) => (
            <tr key={i} className="border-b border-zinc-200 dark:border-zinc-800 last:border-0">
              <td className="px-4 py-2.5 font-medium text-zinc-900 dark:text-white w-1/3">{a}</td>
              <td className="px-4 py-2.5 text-zinc-600 dark:text-zinc-400">{b}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function GuidePage() {
  return (
    <div className="min-h-screen bg-white dark:bg-zinc-950 text-zinc-900 dark:text-white">

      {/* Nav */}
      <nav className="flex items-center justify-between px-6 py-5 max-w-5xl mx-auto border-b border-zinc-200 dark:border-zinc-800">
        <Link href="/" className="font-semibold text-zinc-900 dark:text-white tracking-tight hover:text-zinc-700 dark:hover:text-zinc-300 transition">
          Plan My Workout
        </Link>
        <Link
          href="/"
          className="rounded-lg border border-zinc-200 dark:border-zinc-700 px-4 py-2 text-sm text-zinc-700 dark:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-800 transition"
        >
          Get started free →
        </Link>
      </nav>

      <div className="max-w-5xl mx-auto px-6 py-12 flex gap-12">

        {/* Sidebar - sticky on desktop */}
        <aside className="hidden lg:block w-52 shrink-0">
          <div className="sticky top-8">
            <p className="text-xs font-semibold text-zinc-500 uppercase tracking-widest mb-4">Contents</p>
            <nav className="space-y-1">
              {SECTIONS.map(({ id, label }) => (
                <a
                  key={id}
                  href={`#${id}`}
                  className="block text-sm text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-200 py-1 transition"
                >
                  {label}
                </a>
              ))}
            </nav>
          </div>
        </aside>

        {/* Content */}
        <main className="flex-1 min-w-0 space-y-2">

          {/* Page header */}
          <div className="mb-10">
            <h1 className="text-3xl font-bold text-zinc-900 dark:text-white mb-2">User Guide</h1>
            <p className="text-zinc-600 dark:text-zinc-400">Everything you need to know to get the most out of Plan My Workout.</p>
          </div>

          <Section id="getting-started" title="Getting started">
            <p>
              Plan My Workout builds your weekly workout schedule automatically from YouTube fitness
              channels you already follow. Every Sunday it scans your channels, picks the best video
              for each training day, and has your plan ready when Monday rolls around.
            </p>

            <h3 className="text-zinc-900 dark:text-white font-semibold text-base mt-6 mb-2">1. Sign up</h3>
            <p>
              Go to the homepage and click <strong className="text-zinc-900 dark:text-white">Get started free</strong>.
              Sign in with your Google account - no password, no credit card required.
            </p>

            <h3 className="text-zinc-900 dark:text-white font-semibold text-base mt-6 mb-2">2. Tell us about yourself</h3>
            <p>
              A short setup wizard tailors your plan before you add a single channel. Four quick screens:
            </p>
            <Table
              rows={[
                ["Life stage", "Just starting out · Active adult · 55 and thriving · Training seriously"],
                ["Your goal", "Options vary by life stage - e.g. Build muscle, Lose fat, Stay active & healthy"],
                ["Training days", "How many days a week you can train (2–6)"],
                ["Session length", "15–20 min · 25–35 min · 40–60 min · No preference"],
              ]}
            />
            <p>
              Each screen advances automatically when you tap - no Continue button needed.
            </p>

            <h3 className="text-zinc-900 dark:text-white font-semibold text-base mt-6 mb-2">3. Review your personalised schedule</h3>
            <p>
              Based on your answers, the app builds a weekly training split and shows it to you before anything is saved.
              Hit <strong className="text-zinc-900 dark:text-white">Looks good →</strong> to keep it, or{" "}
              <strong className="text-zinc-900 dark:text-white">Customise</strong> to adjust any day yourself.
            </p>

            <h3 className="text-zinc-900 dark:text-white font-semibold text-base mt-6 mb-2">4. Add your channels</h3>
            <p>
              Search for the YouTube fitness creators you follow and add them. The app shows curated
              suggestions based on your profile - tap a chip to search instantly. You need at least one
              channel to continue.
            </p>

            <h3 className="text-zinc-900 dark:text-white font-semibold text-base mt-6 mb-2">5. Watch it set up in real time</h3>
            <p>
              Hit <strong className="text-zinc-900 dark:text-white">Continue</strong> and a live progress screen tracks each stage:
            </p>
            <ul className="list-disc list-inside space-y-1 pl-1">
              <li><strong className="text-zinc-900 dark:text-white">Scanning</strong> - fetching your channels&apos; recent videos from YouTube</li>
              <li><strong className="text-zinc-900 dark:text-white">Classifying</strong> - analysing videos with AI (shows a live progress count)</li>
              <li><strong className="text-zinc-900 dark:text-white">Building your plan</strong> - picking the best video for each day</li>
            </ul>
            <p>
              When it&apos;s done, you&apos;re taken straight to your dashboard - no button to click.
            </p>
            <Note>
              The first scan typically takes <strong className="text-zinc-900 dark:text-white">5–10 minutes</strong> because
              it processes up to 300 videos. The plan appears automatically when it&apos;s ready.
            </Note>
          </Section>

          <Section id="your-plan" title="Your weekly plan">
            <p>
              The dashboard shows your current week - one video card per training day, with a
              thumbnail, duration, channel name, and workout tags. Click any card to open the video
              directly on YouTube.
            </p>

            <h3 className="text-zinc-900 dark:text-white font-semibold text-base mt-6 mb-2">Regenerate</h3>
            <p>
              Want a fresh set of picks? Hit <strong className="text-zinc-900 dark:text-white">Regenerate</strong> in the
              header. The plan is rebuilt instantly from your existing video library - no new scan needed.
              You'll see a brief spinner while it runs, then the grid updates.
            </p>

            <h3 className="text-zinc-900 dark:text-white font-semibold text-base mt-6 mb-2">Automatic weekly refresh</h3>
            <p>
              New plans are generated automatically every Sunday so your week is always ready by Monday
              morning. You don't need to do anything - just open the app.
            </p>
          </Section>

          <Section id="library" title="Library">
            <p>
              The Library contains every video from your channels that has been scanned and classified.
              Use it to browse, filter, and manually assign videos to specific days.
            </p>

            <h3 className="text-zinc-900 dark:text-white font-semibold text-base mt-6 mb-2">Filters</h3>
            <p>Narrow down videos by:</p>
            <ul className="list-disc list-inside space-y-1 pl-1">
              <li><strong className="text-zinc-900 dark:text-white">Workout type</strong> - Strength, HIIT, Cardio, Mobility</li>
              <li><strong className="text-zinc-900 dark:text-white">Body focus</strong> - upper, lower, full body, core, and more</li>
              <li><strong className="text-zinc-900 dark:text-white">Difficulty</strong> - beginner, intermediate, advanced</li>
              <li><strong className="text-zinc-900 dark:text-white">Channel</strong> - filter to a specific creator</li>
            </ul>

            <h3 className="text-zinc-900 dark:text-white font-semibold text-base mt-6 mb-2">Assign to a day</h3>
            <p>
              Found a video you want to do on Wednesday? Use the{" "}
              <strong className="text-zinc-900 dark:text-white">Assign to day</strong> dropdown on the card. It swaps
              that day's video in your current plan immediately.
            </p>
          </Section>

          <Section id="settings" title="Settings">
            <p>Access Settings from the top nav on your dashboard.</p>

            <h3 className="text-zinc-900 dark:text-white font-semibold text-base mt-6 mb-2">Profile</h3>
            <p>Update the display name shown in your dashboard header.</p>

            <h3 className="text-zinc-900 dark:text-white font-semibold text-base mt-6 mb-2">Channels</h3>
            <p>
              Add or remove YouTube channels at any time. Removing a channel won't affect your current
              week's plan, but future plans won't draw from it. Adding a new channel takes effect on
              the next scan.
            </p>

            <h3 className="text-zinc-900 dark:text-white font-semibold text-base mt-6 mb-2">Weekly schedule</h3>
            <p>
              Change your training split whenever your goals change. Adjust workout types, body focus,
              duration targets, or flip any day to a rest day. Save and your next plan will reflect the
              new schedule.
            </p>

            <h3 className="text-zinc-900 dark:text-white font-semibold text-base mt-6 mb-2">Delete account</h3>
            <p>
              Settings → scroll to <strong className="text-zinc-900 dark:text-white">Danger Zone</strong> →{" "}
              <strong className="text-zinc-900 dark:text-white">Delete my account</strong>. This permanently removes
              everything - your channels, schedule, plan history, and credentials.
            </p>
          </Section>

          <Section id="how-it-works" title="How the plan is built">
            <p>A few things worth knowing about how videos are selected each week:</p>

            <div className="space-y-4 mt-2">
              <div className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900 p-4">
                <h4 className="text-zinc-900 dark:text-white font-semibold mb-1">No repeats for 8 weeks</h4>
                <p>The same video won't appear in your plan for 8 weeks after it was last used, keeping things fresh.</p>
              </div>
              <div className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900 p-4">
                <h4 className="text-zinc-900 dark:text-white font-semibold mb-1">Channel spread</h4>
                <p>The planner tries to use each of your channels across the week rather than leaning on one creator every day.</p>
              </div>
              <div className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900 p-4">
                <h4 className="text-zinc-900 dark:text-white font-semibold mb-1">Recency boost</h4>
                <p>Newer videos are slightly preferred over older ones to keep the plan feeling current.</p>
              </div>
              <div className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900 p-4">
                <h4 className="text-zinc-900 dark:text-white font-semibold mb-1">Smart fallback</h4>
                <p>If your library is light on a given workout type, constraints are relaxed gradually until a match is found. You'll always get a full plan.</p>
              </div>
              <div className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900 p-4">
                <h4 className="text-zinc-900 dark:text-white font-semibold mb-1">Shorts & non-workout content filtered out</h4>
                <p>Videos under 3 minutes, anything tagged #Shorts, and non-workout content like vlogs, podcasts, and recipes are automatically excluded.</p>
              </div>
            </div>
          </Section>

          <Section id="publish" title="Publish to YouTube">
            <p>
              Hit <strong className="text-zinc-900 dark:text-white">Publish to YouTube</strong> on the dashboard to push
              your current weekly plan to a private YouTube playlist in your account. The playlist is
              created automatically on your first publish and reused each week.
            </p>
            <p>
              The plan is also published automatically every Sunday when your weekly plan refreshes,
              as long as your Google account is connected.
            </p>
            <Note>
              <strong className="text-zinc-900 dark:text-white">Button greyed out?</strong> Either you don't have a plan
              yet, or your YouTube access has been revoked. Look for the amber banner on your dashboard
              - sign out and sign in again with Google to reconnect.
            </Note>
          </Section>

          <Section id="faq" title="FAQ">
            <div className="space-y-6">
              {[
                {
                  q: "My plan hasn't updated yet - why?",
                  a: "Plans regenerate automatically every Sunday evening. If it's early in the week and you want a fresh one now, hit Regenerate on the dashboard.",
                },
                {
                  q: "Can I use channels that aren't fitness channels?",
                  a: "The search is open - you can add any YouTube channel. The classifier will label non-workout videos as 'Other' and they'll be excluded from your plan automatically.",
                },
                {
                  q: "What if a video I want isn't in my plan?",
                  a: "Go to the Library, find it, and use 'Assign to day' to put it on a specific day.",
                },
                {
                  q: "Can I change my schedule mid-week?",
                  a: "Yes - update it in Settings anytime. It applies from the next generated plan onward; it won't change your current week retroactively.",
                },
                {
                  q: "How do I remove a channel?",
                  a: "Go to Settings → Channels and hit the ✕ next to any channel. It won't affect videos already in your current plan.",
                },
                {
                  q: "How do I delete my account?",
                  a: "Settings → scroll to Danger Zone → Delete my account. This permanently removes everything - your channels, schedule, plan history, and credentials.",
                },
                {
                  q: "Is it really free?",
                  a: "Yes, completely free. No credit card, no subscription.",
                },
              ].map(({ q, a }) => (
                <div key={q}>
                  <h4 className="text-zinc-900 dark:text-white font-semibold mb-1">{q}</h4>
                  <p>{a}</p>
                </div>
              ))}
            </div>
          </Section>

          {/* CTA */}
          <div className="mt-16 rounded-xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900 p-8 text-center">
            <h3 className="text-zinc-900 dark:text-white font-bold text-lg mb-2">Ready to get started?</h3>
            <p className="text-zinc-600 dark:text-zinc-400 text-sm mb-6">Sign up free and have your first plan in minutes.</p>
            <Link
              href="/"
              className="rounded-lg bg-zinc-900 dark:bg-white px-8 py-3 text-sm font-semibold text-white dark:text-zinc-900 hover:bg-zinc-700 dark:hover:bg-zinc-100 transition"
            >
              Get started free →
            </Link>
          </div>

        </main>
      </div>

      <Footer />

    </div>
  );
}
