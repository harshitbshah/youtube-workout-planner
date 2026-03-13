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
  suggestions?: string[];
}

export default function ChannelManager({ channels, onChannelsChange, suggestions }: Props) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<ChannelSearchResult[]>([]);
  const [searching, setSearching] = useState(false);
  const [adding, setAdding] = useState<string | null>(null);
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

  async function handleSuggestionClick(name: string) {
    setQuery(name);
    await performSearch(name);
  }

  async function handleAdd(result: ChannelSearchResult) {
    setAdding(result.youtube_channel_id);
    setError("");
    try {
      const ch = await addChannel({
        name: result.name,
        youtube_url: `https://www.youtube.com/channel/${result.youtube_channel_id}`,
        youtube_channel_id: result.youtube_channel_id,
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
    try {
      await deleteChannel(id);
      onChannelsChange(channels.filter((ch) => ch.id !== id));
    } catch {
      // ignore — channel stays in list if delete fails
    }
  }

  const addedIds = new Set(channels.map((c) => c.youtube_channel_id));

  return (
    <div>
      {/* Suggestions */}
      {suggestions && suggestions.length > 0 && (
        <div className="mb-4">
          <p className="text-xs text-zinc-500 uppercase tracking-wide mb-2">Suggestions</p>
          <div className="flex gap-2 overflow-x-auto pb-1 scrollbar-none">
            {suggestions.map((name) => {
              const alreadyAdded = channels.some((c) => c.name.toLowerCase() === name.toLowerCase());
              return (
                <button
                  key={name}
                  onClick={() => handleSuggestionClick(name)}
                  disabled={alreadyAdded || searching}
                  className="shrink-0 rounded-full border border-zinc-200 dark:border-zinc-700 bg-zinc-100 dark:bg-zinc-800 px-3 py-1.5 text-sm text-zinc-900 dark:text-white hover:bg-zinc-200 dark:hover:bg-zinc-700 disabled:opacity-40 transition"
                >
                  {alreadyAdded ? `${name} ✓` : name}
                </button>
              );
            })}
          </div>
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
          <div className="flex flex-wrap gap-2">
            {channels.map((ch) => (
              <div
                key={ch.id}
                className="flex items-center gap-2 rounded-full bg-zinc-100 dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 px-3 py-1.5"
              >
                <span className="text-sm text-zinc-900 dark:text-white">{ch.name}</span>
                <button
                  onClick={() => handleRemove(ch.id)}
                  className="text-zinc-500 hover:text-red-400 text-xs transition"
                  title="Remove channel"
                >
                  ✕
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
