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

const baseChannel = {
  id: "1",
  name: "Athlean-X",
  youtube_url: "https://youtube.com/channel/abc",
  youtube_channel_id: "abc",
  added_at: "2026-01-01",
};

beforeEach(() => {
  vi.clearAllMocks();
  mockSearch.mockResolvedValue([]);
  mockAdd.mockResolvedValue(baseChannel);
  mockDelete.mockResolvedValue(undefined);
});

describe("ChannelManager — suggestions prop", () => {
  it("renders suggestion chips when suggestions provided", () => {
    render(
      <ChannelManager
        channels={[]}
        onChannelsChange={() => {}}
        suggestions={["Athlean-X", "Jeff Nippard"]}
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
        suggestions={["Athlean-X"]}
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

  it("clicking a suggestion chip triggers a search for that name", async () => {
    mockSearch.mockResolvedValue([]);
    render(
      <ChannelManager
        channels={[]}
        onChannelsChange={() => {}}
        suggestions={["Athlean-X"]}
      />
    );
    fireEvent.click(screen.getByText("Athlean-X"));
    await waitFor(() => {
      expect(mockSearch).toHaveBeenCalledWith("Athlean-X");
    });
  });

  it("already-added suggestion chip is disabled", () => {
    render(
      <ChannelManager
        channels={[baseChannel]}
        onChannelsChange={() => {}}
        suggestions={["Athlean-X"]}
      />
    );
    // When already added, the chip text is "Athlean-X ✓"
    const chip = screen.getByText("Athlean-X ✓");
    expect(chip.closest("button")).toBeDisabled();
  });
});

describe("ChannelManager — search", () => {
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
