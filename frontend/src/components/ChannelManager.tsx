"use client";

import { useState } from "react";
import {
  searchChannels,
  addChannel,
  deleteChannel,
  type ChannelResponse,
  type ChannelSearchResult,
} from "@/lib/api";

interface Props {
  channels: ChannelResponse[];
  onChannelsChange: (channels: ChannelResponse[]) => void;
  /** Pre-fetched suggestion cards from GET /channels/suggestions */
  suggestions?: ChannelSearchResult[];
  /** True while the parent is fetching suggestions - shows skeleton cards */
  suggestionsLoading?: boolean;
}

export default function ChannelManager({
  channels,
  onChannelsChange,
  suggestions,
  suggestionsLoading,
}: Props) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<ChannelSearchResult[]>([]);
  const [searching, setSearching] = useState(false);
  const [adding, setAdding] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState("");
  const [error, setError] = useState("");

  async function performSearch(searchQuery: string) {
    setSearching(true);
    setError("");
    setResults([]);
    try {
      const data = await searchChannels(searchQuery);
      setResults(data);
      if (data.length === 0) setError("No channels found. Try a different name.");
    } catch {
      setError("Search failed. Check your connection.");
    } finally {
      setSearching(false);
    }
  }

  async function handleSearch() {
    if (!query.trim()) return;
    await performSearch(query.trim());
  }

  async function handleAdd(result: ChannelSearchResult) {
    setAdding(result.youtube_channel_id);
    setError("");
    try {
      const ch = await addChannel({
        name: result.name,
        youtube_url: `https://www.youtube.com/channel/${result.youtube_channel_id}`,
        youtube_channel_id: result.youtube_channel_id,
        description: result.description,
      });
      onChannelsChange([...channels, ch]);
      setResults((r) => r.filter((x) => x.youtube_channel_id !== result.youtube_channel_id));
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to add channel");
    } finally {
      setAdding(null);
    }
  }

  async function handleRemove(id: string) {
    setDeletingId(id);
    setDeleteError("");
    try {
      await deleteChannel(id);
      onChannelsChange(channels.filter((ch) => ch.id !== id));
    } catch {
      setDeleteError("Failed to remove channel. Please try again.");
    } finally {
      setDeletingId(null);
    }
  }

  const addedIds = new Set(channels.map((c) => c.youtube_channel_id));
  const showSuggestions = suggestionsLoading || (suggestions && suggestions.length > 0);

  return (
    <div>
      {/* Suggestions */}
      {showSuggestions && (
        <div className="mb-5">
          <p className="text-xs text-zinc-500 uppercase tracking-wide mb-3">Suggestions</p>
          {suggestionsLoading ? (
            <div className="grid grid-cols-3 gap-3">
              {[0, 1, 2].map((i) => (
                <div
                  key={i}
                  className="flex flex-col items-center gap-2 rounded-xl border border-zinc-200 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-900 p-3 animate-pulse"
                >
                  <div className="h-10 w-10 rounded-full bg-zinc-200 dark:bg-zinc-700" />
                  <div className="h-3 w-3/4 bg-zinc-200 dark:bg-zinc-700 rounded" />
                  <div className="h-2.5 w-1/2 bg-zinc-200 dark:bg-zinc-700 rounded" />
                </div>
              ))}
            </div>
          ) : (
            <div className="grid grid-cols-3 gap-3">
              {suggestions!.map((ch) => {
                const alreadyAdded = addedIds.has(ch.youtube_channel_id);
                return (
                  <div
                    key={ch.youtube_channel_id}
                    className="flex flex-col items-center text-center rounded-xl border border-zinc-200 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-900 p-3 gap-2"
                  >
                    {ch.thumbnail_url ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img
                        src={ch.thumbnail_url}
                        alt=""
                        className="h-10 w-10 rounded-full object-cover"
                      />
                    ) : (
                      <div className="h-10 w-10 rounded-full bg-zinc-200 dark:bg-zinc-700" />
                    )}
                    <p className="text-xs font-medium text-zinc-900 dark:text-white leading-tight line-clamp-2">
                      {ch.name}
                    </p>
                    {alreadyAdded ? (
                      <span className="text-xs text-zinc-500">✓ Added</span>
                    ) : (
                      <button
                        onClick={() => handleAdd(ch)}
                        disabled={adding === ch.youtube_channel_id}
                        className="rounded-full border border-zinc-300 dark:border-zinc-600 px-3 py-1 text-xs text-zinc-700 dark:text-zinc-300 hover:bg-zinc-200 dark:hover:bg-zinc-700 disabled:opacity-40 transition cursor-pointer"
                      >
                        {adding === ch.youtube_channel_id ? "Adding…" : "+ Add"}
                      </button>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* Search */}
      <div className="flex gap-2 mb-4">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSearch()}
          placeholder="e.g. TIFFxDAN, HASfit"
          className="flex-1 rounded-lg bg-zinc-100 dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 px-4 py-2.5 text-sm text-zinc-900 dark:text-white placeholder-zinc-500 focus:outline-none focus:border-zinc-500"
        />
        <button
          onClick={handleSearch}
          disabled={searching || !query.trim()}
          className="rounded-lg bg-zinc-200 dark:bg-zinc-700 px-4 py-2.5 text-sm font-medium text-zinc-900 dark:text-white hover:bg-zinc-300 dark:hover:bg-zinc-600 disabled:opacity-40 transition"
        >
          {searching ? "Searching…" : "Search"}
        </button>
      </div>

      {error && <p className="text-red-400 text-xs mb-3">{error}</p>}

      {/* Search results */}
      {results.length > 0 && (
        <div className="rounded-lg border border-zinc-200 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-900 mb-5 divide-y divide-zinc-200 dark:divide-zinc-800">
          {results.map((r) => (
            <div key={r.youtube_channel_id} className="flex items-center gap-3 px-4 py-3">
              {r.thumbnail_url && (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={r.thumbnail_url} alt="" className="h-9 w-9 rounded-full object-cover" />
              )}
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-zinc-900 dark:text-white truncate">{r.name}</p>
                <p className="text-xs text-zinc-500 truncate">{r.description}</p>
              </div>
              {addedIds.has(r.youtube_channel_id) ? (
                <span className="text-xs text-zinc-500 shrink-0">Added</span>
              ) : (
                <button
                  onClick={() => handleAdd(r)}
                  disabled={adding === r.youtube_channel_id}
                  className="rounded-md bg-zinc-200 dark:bg-zinc-700 px-3 py-1.5 text-xs font-medium text-zinc-900 dark:text-white hover:bg-zinc-300 dark:hover:bg-zinc-600 disabled:opacity-40 transition shrink-0"
                >
                  {adding === r.youtube_channel_id ? "Adding…" : "Add"}
                </button>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Current channels */}
      {channels.length > 0 && (
        <div>
          <p className="text-xs text-zinc-500 uppercase tracking-wide mb-2">Your channels</p>
          {deleteError && <p className="text-red-400 text-xs mb-2">{deleteError}</p>}
          <div className="flex flex-wrap gap-2">
            {channels.map((ch) => (
              <div
                key={ch.id}
                className="flex items-center gap-2 rounded-full bg-zinc-100 dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 pl-1.5 pr-3 py-1.5"
              >
                {ch.thumbnail_url ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={ch.thumbnail_url} alt="" className="h-6 w-6 rounded-full object-cover shrink-0" />
                ) : (
                  <div className="h-6 w-6 rounded-full bg-zinc-300 dark:bg-zinc-600 shrink-0" />
                )}
                <span className="text-sm text-zinc-900 dark:text-white">{ch.name}</span>
                <button
                  onClick={() => handleRemove(ch.id)}
                  disabled={deletingId === ch.id}
                  className="text-zinc-500 hover:text-red-400 text-xs transition disabled:opacity-40 cursor-pointer"
                  title="Remove channel"
                >
                  {deletingId === ch.id ? "…" : "✕"}
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
