import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import ChannelManager from "./ChannelManager";
import * as api from "@/lib/api";

vi.mock("@/lib/api", () => ({
  searchChannels: vi.fn(),
  addChannel: vi.fn(),
  deleteChannel: vi.fn(),
}));

const mockSearch = api.searchChannels as ReturnType<typeof vi.fn>;
const mockAdd = api.addChannel as ReturnType<typeof vi.fn>;
const mockDelete = api.deleteChannel as ReturnType<typeof vi.fn>;

const baseChannel: api.ChannelResponse = {
  id: "1",
  name: "Athlean-X",
  youtube_url: "https://youtube.com/channel/abc",
  youtube_channel_id: "abc",
  thumbnail_url: null,
  added_at: "2026-01-01",
};

const mockSuggestion: api.ChannelSearchResult = {
  youtube_channel_id: "UCabc",
  name: "Athlean-X",
  description: "Build muscle fast",
  thumbnail_url: "https://example.com/thumb.jpg",
};

const mockSuggestion2: api.ChannelSearchResult = {
  youtube_channel_id: "UCdef",
  name: "Jeff Nippard",
  description: "Science-based lifting",
  thumbnail_url: null,
};

beforeEach(() => {
  vi.clearAllMocks();
  mockSearch.mockResolvedValue([]);
  mockAdd.mockResolvedValue(baseChannel);
  mockDelete.mockResolvedValue(undefined);
});

describe("ChannelManager - suggestions (card UI)", () => {
  it("renders suggestion cards when suggestions prop provided", () => {
    render(
      <ChannelManager
        channels={[]}
        onChannelsChange={() => {}}
        suggestions={[mockSuggestion, mockSuggestion2]}
      />
    );
    expect(screen.getByText("Athlean-X")).toBeInTheDocument();
    expect(screen.getByText("Jeff Nippard")).toBeInTheDocument();
  });

  it("renders 'Suggestions' label", () => {
    render(
      <ChannelManager
        channels={[]}
        onChannelsChange={() => {}}
        suggestions={[mockSuggestion]}
      />
    );
    expect(screen.getByText("Suggestions")).toBeInTheDocument();
  });

  it("does not render suggestions section when prop is absent", () => {
    render(<ChannelManager channels={[]} onChannelsChange={() => {}} />);
    expect(screen.queryByText("Suggestions")).not.toBeInTheDocument();
  });

  it("does not render suggestions section when suggestions is empty array", () => {
    render(<ChannelManager channels={[]} onChannelsChange={() => {}} suggestions={[]} />);
    expect(screen.queryByText("Suggestions")).not.toBeInTheDocument();
  });

  it("shows skeleton cards when suggestionsLoading is true", () => {
    const { container } = render(
      <ChannelManager channels={[]} onChannelsChange={() => {}} suggestionsLoading={true} />
    );
    expect(screen.getByText("Suggestions")).toBeInTheDocument();
    expect(container.querySelector(".animate-pulse")).toBeInTheDocument();
  });

  it("clicking + Add calls addChannel directly without triggering search", async () => {
    render(
      <ChannelManager
        channels={[]}
        onChannelsChange={() => {}}
        suggestions={[mockSuggestion]}
      />
    );
    fireEvent.click(screen.getByText("+ Add"));
    await waitFor(() => {
      expect(mockAdd).toHaveBeenCalledWith(
        expect.objectContaining({ youtube_channel_id: "UCabc" })
      );
      expect(mockSearch).not.toHaveBeenCalled();
    });
  });

  it("shows ✓ Added for already-subscribed suggestion", () => {
    const addedChannel = { ...baseChannel, youtube_channel_id: "UCabc" };
    render(
      <ChannelManager
        channels={[addedChannel]}
        onChannelsChange={() => {}}
        suggestions={[mockSuggestion]}
      />
    );
    expect(screen.getByText("✓ Added")).toBeInTheDocument();
    expect(screen.queryByText("+ Add")).not.toBeInTheDocument();
  });

  it("renders thumbnail img when thumbnail_url is provided", () => {
    const { container } = render(
      <ChannelManager
        channels={[]}
        onChannelsChange={() => {}}
        suggestions={[mockSuggestion]}
      />
    );
    const img = container.querySelector("img");
    expect(img).not.toBeNull();
    expect(img?.src).toContain("thumb.jpg");
  });

  it("renders placeholder div when thumbnail_url is null", () => {
    const { container } = render(
      <ChannelManager
        channels={[]}
        onChannelsChange={() => {}}
        suggestions={[mockSuggestion2]}
      />
    );
    // No img element - falls back to a div placeholder
    expect(container.querySelector("img")).toBeNull();
  });
});

describe("ChannelManager - channel limit", () => {
  const fiveChannels: api.ChannelResponse[] = Array.from({ length: 5 }, (_, i) => ({
    id: `ch${i}`,
    name: `Channel ${i}`,
    youtube_url: `https://youtube.com/@ch${i}`,
    youtube_channel_id: `UC${i}`,
    thumbnail_url: null,
    added_at: "2026-01-01",
  }));

  it("hides search bar and shows limit message when at 5 channels", () => {
    render(<ChannelManager channels={fiveChannels} onChannelsChange={() => {}} />);
    expect(screen.queryByPlaceholderText(/TIFFxDAN/i)).not.toBeInTheDocument();
    expect(screen.getByText(/5-channel limit/i)).toBeInTheDocument();
  });

  it("shows 'Limit reached' on suggestion cards when at 5 channels", () => {
    render(
      <ChannelManager
        channels={fiveChannels}
        onChannelsChange={() => {}}
        suggestions={[mockSuggestion]}
      />
    );
    expect(screen.getByText(/Limit reached/i)).toBeInTheDocument();
    expect(screen.queryByText("+ Add")).not.toBeInTheDocument();
  });

  it("shows search bar when below limit", () => {
    render(<ChannelManager channels={[baseChannel]} onChannelsChange={() => {}} />);
    expect(screen.getByPlaceholderText(/TIFFxDAN/i)).toBeInTheDocument();
  });
});

describe("ChannelManager - search", () => {
  it("search button is disabled when query is empty", () => {
    render(<ChannelManager channels={[]} onChannelsChange={() => {}} />);
    expect(screen.getByRole("button", { name: /Search/i })).toBeDisabled();
  });

  it("shows search results after a search", async () => {
    mockSearch.mockResolvedValue([
      { youtube_channel_id: "ch1", name: "HASfit", description: "Fitness channel", thumbnail_url: null },
    ]);
    render(<ChannelManager channels={[]} onChannelsChange={() => {}} />);
    fireEvent.change(screen.getByPlaceholderText(/TIFFxDAN/i), { target: { value: "HASfit" } });
    fireEvent.click(screen.getByRole("button", { name: /Search/i }));
    await waitFor(() => expect(screen.getByText("HASfit")).toBeInTheDocument());
  });

  it("shows 'No channels found' when search returns empty", async () => {
    mockSearch.mockResolvedValue([]);
    render(<ChannelManager channels={[]} onChannelsChange={() => {}} />);
    fireEvent.change(screen.getByPlaceholderText(/TIFFxDAN/i), { target: { value: "xyz" } });
    fireEvent.click(screen.getByRole("button", { name: /Search/i }));
    await waitFor(() => expect(screen.getByText(/No channels found/i)).toBeInTheDocument());
  });

  it("shows existing channels as pills", () => {
    render(<ChannelManager channels={[baseChannel]} onChannelsChange={() => {}} />);
    expect(screen.getByText("Athlean-X")).toBeInTheDocument();
    expect(screen.getByTitle("Remove channel")).toBeInTheDocument();
  });
});
