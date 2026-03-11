import Link from "next/link";

export function Footer({ isAdmin }: { isAdmin?: boolean } = {}) {
  return (
    <footer className="border-t border-zinc-800 px-6 py-6 text-center space-y-2">
      <div className="flex items-center justify-center flex-wrap gap-x-4 gap-y-1 text-xs text-zinc-600">
        <Link href="/guide" className="hover:text-zinc-400 transition">User Guide</Link>
        {isAdmin && (
          <Link href="/admin/guide" className="hover:text-zinc-400 transition">Admin Guide</Link>
        )}
        <Link href="/privacy" className="hover:text-zinc-400 transition">Privacy Policy</Link>
        <Link href="/terms" className="hover:text-zinc-400 transition">Terms of Service</Link>
      </div>
      <p className="text-xs text-zinc-700">
        This product uses the{" "}
        <a href="https://www.youtube.com/t/terms" target="_blank" rel="noopener noreferrer" className="hover:text-zinc-500 transition underline">YouTube API Services</a>
        {" "}·{" "}
        <a href="https://policies.google.com/privacy" target="_blank" rel="noopener noreferrer" className="hover:text-zinc-500 transition underline">Google Privacy Policy</a>
      </p>
      <p className="text-xs text-zinc-700">Not affiliated with YouTube, Google, or any featured channels.</p>
      <p className="text-xs text-zinc-700">© {new Date().getFullYear()} Plan My Workout.</p>
    </footer>
  );
}
