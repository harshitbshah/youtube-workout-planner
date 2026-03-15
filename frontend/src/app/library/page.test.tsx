import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import LibraryPage from "./page";
import * as api from "@/lib/api";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn() }),
}));

vi.mock("next/link", () => ({
  default: ({ href, children, ...props }: { href: string; children: React.ReactNode; [key: string]: unknown }) => (
    <a href={href} {...props}>{children}</a>
  ),
}));

vi.mock("@/components/Footer", () => ({ Footer: () => null }));
vi.mock("@/components/FeedbackWidget", () => ({ default: () => null }));
vi.mock("@/components/Badge", () => ({
  default: ({ label }: { label: string }) => <span>{label}</span>,
}));

vi.mock("@/lib/api", () => ({
  getMe: vi.fn(),
  getChannels: vi.fn(),
  getJobStatus: vi.fn(),
  getLibrary: vi.fn(),
  swapPlanDay: vi.fn(),
}));

const mockGetMe = api.getMe as ReturnType<typeof vi.fn>;
const mockGetChannels = api.getChannels as ReturnType<typeof vi.fn>;
const mockGetJobStatus = api.getJobStatus as ReturnType<typeof vi.fn>;
const mockGetLibrary = api.getLibrary as ReturnType<typeof vi.fn>;
const mockSwapPlanDay = api.swapPlanDay as ReturnType<typeof vi.fn>;

function makeLibraryResponse(overrides = {}) {
  return {
    videos: [
      {
        id: "vid1",
        title: "30 Min Full Body Strength",
        url: "https://youtube.com/watch?v=vid1",
        channel_name: "FitnessBlender",
        duration_sec: 1800,
        workout_type: "Strength",
        body_focus: "full",
        difficulty: "intermediate",
      },
      {
        id: "vid2",
        title: "20 Min HIIT Cardio",
        url: "https://youtube.com/watch?v=vid2",
        channel_name: "HASfit",
        duration_sec: 1200,
        workout_type: "HIIT",
        body_focus: null,
        difficulty: null,
      },
    ],
    total: 2,
    page: 1,
    pages: 1,
    ...overrides,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  mockGetMe.mockResolvedValue({ id: 1, email: "test@example.com" });
  mockGetChannels.mockResolvedValue([]);
  mockGetJobStatus.mockResolvedValue({ stage: "done", total: null, done: null, error: null, background_classifying: false });
  mockGetLibrary.mockResolvedValue(makeLibraryResponse());
  mockSwapPlanDay.mockResolvedValue(undefined);
});

describe("LibraryPage — rendering", () => {
  it("renders Video Library heading", async () => {
    render(<LibraryPage />);
    await waitFor(() =>
      expect(screen.getByText("Video Library")).toBeInTheDocument()
    );
  });

  it("displays video titles from library response", async () => {
    render(<LibraryPage />);
    await waitFor(() =>
      expect(screen.getByText("30 Min Full Body Strength")).toBeInTheDocument()
    );
    expect(screen.getByText("20 Min HIIT Cardio")).toBeInTheDocument();
  });

  it("shows total video count", async () => {
    render(<LibraryPage />);
    await waitFor(() =>
      expect(screen.getByText(/2 videos/i)).toBeInTheDocument()
    );
  });

  it("shows empty state when library has no videos", async () => {
    mockGetLibrary.mockResolvedValue({ videos: [], total: 0, page: 1, pages: 1 });
    render(<LibraryPage />);
    await waitFor(() =>
      expect(screen.getByText(/No videos in your library yet/i)).toBeInTheDocument()
    );
  });
});

describe("LibraryPage — filters", () => {
  it("renders workout type filter select", async () => {
    render(<LibraryPage />);
    await waitFor(() => screen.getByText("Video Library"));
    expect(screen.getByDisplayValue("Workout type")).toBeInTheDocument();
  });

  it("re-fetches library when workout type filter changes", async () => {
    render(<LibraryPage />);
    await waitFor(() => screen.getByText("Video Library"));
    const typeSelect = screen.getByDisplayValue("Workout type");
    fireEvent.change(typeSelect, { target: { value: "hiit" } });
    await waitFor(() =>
      expect(mockGetLibrary).toHaveBeenCalledWith(
        expect.objectContaining({ workout_type: "hiit" })
      )
    );
  });

  it("shows 'Clear filters' button when a filter is active", async () => {
    render(<LibraryPage />);
    await waitFor(() => screen.getByText("Video Library"));
    const typeSelect = screen.getByDisplayValue("Workout type");
    fireEvent.change(typeSelect, { target: { value: "strength" } });
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /Clear filters/i })).toBeInTheDocument()
    );
  });

  it("clears filters and re-fetches when 'Clear filters' is clicked", async () => {
    render(<LibraryPage />);
    await waitFor(() => screen.getByText("Video Library"));
    const typeSelect = screen.getByDisplayValue("Workout type");
    fireEvent.change(typeSelect, { target: { value: "strength" } });
    await waitFor(() => screen.getByRole("button", { name: /Clear filters/i }));
    fireEvent.click(screen.getByRole("button", { name: /Clear filters/i }));
    await waitFor(() =>
      expect(mockGetLibrary).toHaveBeenCalledWith(
        expect.objectContaining({ workout_type: undefined })
      )
    );
  });

  it("shows 'No videos match these filters' when filtered result is empty", async () => {
    render(<LibraryPage />);
    await waitFor(() => screen.getByText("Video Library"));
    mockGetLibrary.mockResolvedValue({ videos: [], total: 0, page: 1, pages: 1 });
    const typeSelect = screen.getByDisplayValue("Workout type");
    fireEvent.change(typeSelect, { target: { value: "mobility" } });
    await waitFor(() =>
      expect(screen.getByText(/No videos match these filters/i)).toBeInTheDocument()
    );
  });
});

describe("LibraryPage — assign to day", () => {
  it("renders 'Assign to day' dropdowns for each video", async () => {
    render(<LibraryPage />);
    await waitFor(() => screen.getByText("30 Min Full Body Strength"));
    const assignSelects = screen.getAllByRole("combobox", {
      name: "",
    });
    // At least the assign dropdowns exist (they show "Assign to day…" option)
    const assignOpts = screen.getAllByText(/Assign to day/i);
    expect(assignOpts.length).toBeGreaterThan(0);
  });

  it("calls swapPlanDay when a day is selected", async () => {
    render(<LibraryPage />);
    await waitFor(() => screen.getByText("30 Min Full Body Strength"));
    // Find the assign select for the first video — it contains "Assign to day…" as default
    const [firstAssignSelect] = screen.getAllByDisplayValue("Assign to day…");
    fireEvent.change(firstAssignSelect, { target: { value: "monday" } });
    await waitFor(() =>
      expect(mockSwapPlanDay).toHaveBeenCalledWith("monday", "vid1")
    );
  });

  it("shows success confirmation after assigning", async () => {
    render(<LibraryPage />);
    await waitFor(() => screen.getByText("30 Min Full Body Strength"));
    const [firstAssignSelect] = screen.getAllByDisplayValue("Assign to day…");
    fireEvent.change(firstAssignSelect, { target: { value: "friday" } });
    await waitFor(() =>
      expect(screen.getByText(/Assigned to Fri/i)).toBeInTheDocument()
    );
  });

  it("shows error when swapPlanDay fails", async () => {
    mockSwapPlanDay.mockRejectedValue(new Error("No plan"));
    render(<LibraryPage />);
    await waitFor(() => screen.getByText("30 Min Full Body Strength"));
    const [firstAssignSelect] = screen.getAllByDisplayValue("Assign to day…");
    fireEvent.change(firstAssignSelect, { target: { value: "monday" } });
    await waitFor(() =>
      expect(screen.getByText(/Failed — generate a plan first/i)).toBeInTheDocument()
    );
  });
});

describe("LibraryPage — background classifying banner", () => {
  it("shows banner when background_classifying is true", async () => {
    mockGetJobStatus.mockResolvedValue({ stage: "done", total: null, done: null, error: null, background_classifying: true });
    render(<LibraryPage />);
    await waitFor(() =>
      expect(screen.getByText(/library is still building/i)).toBeInTheDocument()
    );
  });

  it("does not show banner when background_classifying is false", async () => {
    render(<LibraryPage />);
    await waitFor(() => screen.getByText("Video Library"));
    expect(screen.queryByText(/library is still building/i)).not.toBeInTheDocument();
  });

  it("does not show banner when getJobStatus fails", async () => {
    mockGetJobStatus.mockRejectedValue(new Error("network error"));
    render(<LibraryPage />);
    await waitFor(() => screen.getByText("Video Library"));
    expect(screen.queryByText(/library is still building/i)).not.toBeInTheDocument();
  });

  it("dismisses banner when ✕ is clicked", async () => {
    mockGetJobStatus.mockResolvedValue({ stage: "done", total: null, done: null, error: null, background_classifying: true });
    render(<LibraryPage />);
    await waitFor(() => screen.getByText(/library is still building/i));
    fireEvent.click(screen.getByRole("button", { name: /Dismiss/i }));
    expect(screen.queryByText(/library is still building/i)).not.toBeInTheDocument();
  });
});

describe("LibraryPage — pagination", () => {
  it("shows Previous/Next buttons when there are multiple pages", async () => {
    mockGetLibrary.mockResolvedValue(makeLibraryResponse({ pages: 3, total: 30 }));
    render(<LibraryPage />);
    await waitFor(() => screen.getByText("Video Library"));
    expect(screen.getByRole("button", { name: /Previous/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Next/i })).toBeInTheDocument();
  });

  it("Previous button is disabled on page 1", async () => {
    mockGetLibrary.mockResolvedValue(makeLibraryResponse({ pages: 3, total: 30 }));
    render(<LibraryPage />);
    await waitFor(() => screen.getByRole("button", { name: /Previous/i }));
    expect(screen.getByRole("button", { name: /Previous/i })).toBeDisabled();
  });

  it("does not show pagination when there is only one page", async () => {
    render(<LibraryPage />);
    await waitFor(() => screen.getByText("Video Library"));
    expect(screen.queryByRole("button", { name: /Previous/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Next/i })).not.toBeInTheDocument();
  });
});
