import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import DashboardPage from "./page";
import * as api from "@/lib/api";
import userEvent from "@testing-library/user-event";

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
  getUpcomingPlan: vi.fn(),
  generatePlan: vi.fn(),
  publishPlan: vi.fn(),
  getPublishStatus: vi.fn(),
  triggerScan: vi.fn(),
  getJobStatus: vi.fn(),
  getActiveAnnouncement: vi.fn(),
  getLibrary: vi.fn(),
  swapPlanDay: vi.fn(),
  logout: vi.fn(),
  youtubeConnectUrl: () => "http://localhost:8000/auth/youtube/connect",
}));

const mockGetMe = api.getMe as ReturnType<typeof vi.fn>;
const mockGetChannels = api.getChannels as ReturnType<typeof vi.fn>;
const mockGetUpcomingPlan = api.getUpcomingPlan as ReturnType<typeof vi.fn>;
const mockGeneratePlan = api.generatePlan as ReturnType<typeof vi.fn>;
const mockPublishPlan = api.publishPlan as ReturnType<typeof vi.fn>;
const mockGetPublishStatus = api.getPublishStatus as ReturnType<typeof vi.fn>;
const mockGetJobStatus = api.getJobStatus as ReturnType<typeof vi.fn>;
const mockGetActiveAnnouncement = api.getActiveAnnouncement as ReturnType<typeof vi.fn>;
const mockGetLibrary = api.getLibrary as ReturnType<typeof vi.fn>;
const mockSwapPlanDay = api.swapPlanDay as ReturnType<typeof vi.fn>;

const mockUser = {
  id: 1,
  display_name: "Harshit",
  email: "test@example.com",
  youtube_connected: false,
  credentials_valid: true,
  is_admin: false,
};

function getCurrentMondayISO(): string {
  const today = new Date();
  const dayOfWeek = today.getDay();
  const daysToMonday = dayOfWeek === 0 ? -6 : 1 - dayOfWeek;
  const monday = new Date(today);
  monday.setDate(today.getDate() + daysToMonday);
  return monday.toISOString().slice(0, 10);
}

function makePlan(weekStart: string) {
  return {
    week_start: weekStart,
    days: [
      {
        day: "monday",
        video: {
          id: "abc123",
          title: "30 Min Full Body HIIT",
          url: "https://youtube.com/watch?v=abc123",
          channel_name: "FitnessBlender",
          duration_sec: 1800,
          workout_type: "HIIT",
          body_focus: null,
          difficulty: null,
        },
      },
      { day: "tuesday", video: null },
      { day: "wednesday", video: null },
      { day: "thursday", video: null },
      { day: "friday", video: null },
      { day: "saturday", video: null },
      { day: "sunday", video: null },
    ],
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  mockGetMe.mockResolvedValue(mockUser);
  mockGetChannels.mockResolvedValue([{ id: 1, name: "FitnessBlender" }]);
  mockGetJobStatus.mockResolvedValue({ stage: null, total: null, done: null });
  mockGetActiveAnnouncement.mockResolvedValue(null);
  mockGeneratePlan.mockResolvedValue(makePlan(getCurrentMondayISO()));
  mockPublishPlan.mockResolvedValue({ message: "Publishing started" });
  mockGetPublishStatus.mockResolvedValue({ status: "idle" });
  mockGetLibrary.mockResolvedValue({
    videos: [
      {
        id: "alt1",
        title: "20 Min Core Blast",
        url: "https://youtube.com/watch?v=alt1",
        channel_name: "HASfit",
        duration_sec: 1200,
        workout_type: "HIIT",
        body_focus: "core",
        difficulty: null,
      },
      {
        id: "alt2",
        title: "45 Min Leg Day",
        url: "https://youtube.com/watch?v=alt2",
        channel_name: "FitnessBlender",
        duration_sec: 2700,
        workout_type: "Strength",
        body_focus: "lower",
        difficulty: null,
      },
    ],
    total: 2,
    page: 1,
    pages: 1,
  });
  mockSwapPlanDay.mockResolvedValue({ day: "monday", video: null });
});

// ---------------------------------------------------------------------------
// Stale plan banner
// ---------------------------------------------------------------------------

describe("DashboardPage - stale plan banner", () => {
  it("shows banner when week_start is from a past week", async () => {
    mockGetUpcomingPlan.mockResolvedValue(makePlan("2000-01-03"));
    render(<DashboardPage />);
    await waitFor(() =>
      expect(screen.getByText(/Welcome back/i)).toBeInTheDocument()
    );
    expect(screen.getByText(/Generate a fresh plan/i)).toBeInTheDocument();
  });

  it("does not show banner when week_start is the current week", async () => {
    mockGetUpcomingPlan.mockResolvedValue(makePlan(getCurrentMondayISO()));
    render(<DashboardPage />);
    await waitFor(() =>
      expect(screen.queryByText(/Welcome back/i)).not.toBeInTheDocument()
    );
  });

  it("does not show banner when there is no plan", async () => {
    mockGetUpcomingPlan.mockResolvedValue(null);
    render(<DashboardPage />);
    await waitFor(() =>
      expect(screen.queryByText(/Welcome back/i)).not.toBeInTheDocument()
    );
  });

  it("dismisses banner when ✕ is clicked", async () => {
    mockGetUpcomingPlan.mockResolvedValue(makePlan("2000-01-03"));
    render(<DashboardPage />);
    await waitFor(() =>
      expect(screen.getByText(/Welcome back/i)).toBeInTheDocument()
    );
    // The stale banner's ✕ is the only dismiss button when no announcement is shown
    fireEvent.click(screen.getByRole("button", { name: "✕" }));
    expect(screen.queryByText(/Welcome back/i)).not.toBeInTheDocument();
  });

  it("calls generatePlan when 'Generate a fresh plan' is clicked", async () => {
    mockGetUpcomingPlan.mockResolvedValue(makePlan("2000-01-03"));
    render(<DashboardPage />);
    await waitFor(() =>
      expect(screen.getByText(/Generate a fresh plan/i)).toBeInTheDocument()
    );
    fireEvent.click(screen.getByText(/Generate a fresh plan/i));
    await waitFor(() => expect(mockGeneratePlan).toHaveBeenCalledOnce());
  });
});

// ---------------------------------------------------------------------------
// Plan rendering
// ---------------------------------------------------------------------------

describe("DashboardPage - plan display", () => {
  it("renders video title from the plan", async () => {
    mockGetUpcomingPlan.mockResolvedValue(makePlan(getCurrentMondayISO()));
    render(<DashboardPage />);
    await waitFor(() =>
      expect(screen.getByText("30 Min Full Body HIIT")).toBeInTheDocument()
    );
  });

  it("shows 'No plan generated yet' when plan is null and not scanning", async () => {
    mockGetUpcomingPlan.mockResolvedValue(null);
    render(<DashboardPage />);
    await waitFor(() =>
      expect(screen.getByText(/No plan generated yet/i)).toBeInTheDocument()
    );
  });

  it("shows 'Regenerate' button when a non-empty plan exists", async () => {
    mockGetUpcomingPlan.mockResolvedValue(makePlan(getCurrentMondayISO()));
    render(<DashboardPage />);
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /Regenerate/i })).toBeInTheDocument()
    );
  });

  it("shows week label in header when plan exists", async () => {
    mockGetUpcomingPlan.mockResolvedValue(makePlan(getCurrentMondayISO()));
    render(<DashboardPage />);
    await waitFor(() =>
      expect(screen.getByText(/Week of/i)).toBeInTheDocument()
    );
  });

  it("shows rest day cards for days with no video and no scheduled_workout_type", async () => {
    mockGetUpcomingPlan.mockResolvedValue(makePlan(getCurrentMondayISO()));
    render(<DashboardPage />);
    await waitFor(() => screen.getByText("30 Min Full Body HIIT"));
    // 6 days have no video and no scheduled_workout_type - each gets a Rest label
    const restLabels = screen.getAllByText("Rest");
    expect(restLabels.length).toBe(6);
  });

  it("shows all 7 day labels in the grid", async () => {
    mockGetUpcomingPlan.mockResolvedValue(makePlan(getCurrentMondayISO()));
    render(<DashboardPage />);
    await waitFor(() => screen.getByText("30 Min Full Body HIIT"));
    expect(screen.getByText("Mon")).toBeInTheDocument();
    expect(screen.getByText("Tue")).toBeInTheDocument();
    expect(screen.getByText("Wed")).toBeInTheDocument();
    expect(screen.getByText("Thu")).toBeInTheDocument();
    expect(screen.getByText("Fri")).toBeInTheDocument();
    expect(screen.getByText("Sat")).toBeInTheDocument();
    expect(screen.getByText("Sun")).toBeInTheDocument();
  });

  it("shows MissingVideoCard for days with scheduled_workout_type but no video", async () => {
    const planWithMissing = {
      week_start: getCurrentMondayISO(),
      days: [
        {
          day: "monday",
          video: {
            id: "abc123", title: "30 Min Full Body HIIT",
            url: "https://youtube.com/watch?v=abc123",
            channel_name: "FitnessBlender", duration_sec: 1800,
            workout_type: "HIIT", body_focus: null, difficulty: null,
          },
        },
        { day: "tuesday", video: null, scheduled_workout_type: "strength" },
        { day: "wednesday", video: null, scheduled_workout_type: null },
        { day: "thursday", video: null, scheduled_workout_type: null },
        { day: "friday", video: null, scheduled_workout_type: null },
        { day: "saturday", video: null, scheduled_workout_type: null },
        { day: "sunday", video: null, scheduled_workout_type: null },
      ],
    };
    mockGetUpcomingPlan.mockResolvedValue(planWithMissing);
    render(<DashboardPage />);
    await waitFor(() => screen.getByText("30 Min Full Body HIIT"));
    expect(screen.getAllByText("Strength").length).toBeGreaterThan(0);
    expect(screen.getByText("No matching video found.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Add channels in Settings/i })).toBeInTheDocument();
    // Tuesday has a missing video card, not a rest card - only 5 rest cards
    const restLabels = screen.getAllByText("Rest");
    expect(restLabels.length).toBe(5);
  });

  it("rest day messages are deterministic for the same day and week_start", async () => {
    mockGetUpcomingPlan.mockResolvedValue(makePlan(getCurrentMondayISO()));
    const { unmount } = render(<DashboardPage />);
    await waitFor(() => screen.getByText("30 Min Full Body HIIT"));
    const tuesdayCard = screen.getAllByText("Rest")[0].closest("div");
    const firstMessage = tuesdayCard?.querySelector("p")?.textContent;
    unmount();

    render(<DashboardPage />);
    await waitFor(() => screen.getByText("30 Min Full Body HIIT"));
    const tuesdayCard2 = screen.getAllByText("Rest")[0].closest("div");
    const secondMessage = tuesdayCard2?.querySelector("p")?.textContent;
    expect(firstMessage).toBe(secondMessage);
  });
});

// ---------------------------------------------------------------------------
// Announcement banner
// ---------------------------------------------------------------------------

describe("DashboardPage - announcement banner", () => {
  it("shows announcement when active announcement exists", async () => {
    mockGetUpcomingPlan.mockResolvedValue(null);
    mockGetActiveAnnouncement.mockResolvedValue({
      id: 1,
      message: "We are doing maintenance on Sunday.",
    });
    render(<DashboardPage />);
    await waitFor(() =>
      expect(
        screen.getByText("We are doing maintenance on Sunday.")
      ).toBeInTheDocument()
    );
  });

  it("dismisses announcement when ✕ is clicked", async () => {
    mockGetUpcomingPlan.mockResolvedValue(null);
    mockGetActiveAnnouncement.mockResolvedValue({
      id: 1,
      message: "Maintenance notice",
    });
    render(<DashboardPage />);
    await waitFor(() =>
      expect(screen.getByText("Maintenance notice")).toBeInTheDocument()
    );
    fireEvent.click(screen.getByRole("button", { name: "✕" }));
    expect(screen.queryByText("Maintenance notice")).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Swap picker
// ---------------------------------------------------------------------------

describe("DashboardPage - swap picker", () => {
  it("shows 'Swap video' button for each plan day", async () => {
    mockGetUpcomingPlan.mockResolvedValue(makePlan(getCurrentMondayISO()));
    render(<DashboardPage />);
    await waitFor(() => screen.getByText("30 Min Full Body HIIT"));
    expect(screen.getByRole("button", { name: /Swap video/i })).toBeInTheDocument();
  });

  it("opens swap picker when 'Swap video' is clicked", async () => {
    mockGetUpcomingPlan.mockResolvedValue(makePlan(getCurrentMondayISO()));
    render(<DashboardPage />);
    await waitFor(() => screen.getByText("30 Min Full Body HIIT"));
    fireEvent.click(screen.getByRole("button", { name: /Swap video/i }));
    await waitFor(() =>
      expect(screen.getByText(/Pick a replacement/i)).toBeInTheDocument()
    );
  });

  it("shows fetched videos in the picker", async () => {
    mockGetUpcomingPlan.mockResolvedValue(makePlan(getCurrentMondayISO()));
    render(<DashboardPage />);
    await waitFor(() => screen.getByText("30 Min Full Body HIIT"));
    fireEvent.click(screen.getByRole("button", { name: /Swap video/i }));
    await waitFor(() =>
      expect(screen.getByText("20 Min Core Blast")).toBeInTheDocument()
    );
    expect(screen.getByText("45 Min Leg Day")).toBeInTheDocument();
  });

  it("calls getLibrary with the current day's workout_type as default filter", async () => {
    mockGetUpcomingPlan.mockResolvedValue(makePlan(getCurrentMondayISO()));
    render(<DashboardPage />);
    await waitFor(() => screen.getByText("30 Min Full Body HIIT"));
    fireEvent.click(screen.getByRole("button", { name: /Swap video/i }));
    await waitFor(() =>
      expect(mockGetLibrary).toHaveBeenCalledWith(
        expect.objectContaining({ workout_type: "HIIT" })
      )
    );
  });

  it("closes picker when Cancel is clicked", async () => {
    mockGetUpcomingPlan.mockResolvedValue(makePlan(getCurrentMondayISO()));
    render(<DashboardPage />);
    await waitFor(() => screen.getByText("30 Min Full Body HIIT"));
    fireEvent.click(screen.getByRole("button", { name: /Swap video/i }));
    await waitFor(() => screen.getByText(/Pick a replacement/i));
    fireEvent.click(screen.getByRole("button", { name: /Cancel/i }));
    expect(screen.queryByText(/Pick a replacement/i)).not.toBeInTheDocument();
  });

  it("calls swapPlanDay and updates the plan when a video is selected", async () => {
    mockGetUpcomingPlan.mockResolvedValue(makePlan(getCurrentMondayISO()));
    mockSwapPlanDay.mockResolvedValue({ day: "monday", video: null });
    render(<DashboardPage />);
    await waitFor(() => screen.getByText("30 Min Full Body HIIT"));
    fireEvent.click(screen.getByRole("button", { name: /Swap video/i }));
    await waitFor(() => screen.getByText("20 Min Core Blast"));
    fireEvent.click(screen.getByText("20 Min Core Blast"));
    await waitFor(() =>
      expect(mockSwapPlanDay).toHaveBeenCalledWith("monday", "alt1")
    );
  });

  it("closes picker after a swap is made", async () => {
    mockGetUpcomingPlan.mockResolvedValue(makePlan(getCurrentMondayISO()));
    render(<DashboardPage />);
    await waitFor(() => screen.getByText("30 Min Full Body HIIT"));
    fireEvent.click(screen.getByRole("button", { name: /Swap video/i }));
    await waitFor(() => screen.getByText("20 Min Core Blast"));
    fireEvent.click(screen.getByText("20 Min Core Blast"));
    await waitFor(() =>
      expect(screen.queryByText(/Pick a replacement/i)).not.toBeInTheDocument()
    );
  });

  it("fetches all types when 'Show all types' is clicked", async () => {
    mockGetUpcomingPlan.mockResolvedValue(makePlan(getCurrentMondayISO()));
    render(<DashboardPage />);
    await waitFor(() => screen.getByText("30 Min Full Body HIIT"));
    fireEvent.click(screen.getByRole("button", { name: /Swap video/i }));
    await waitFor(() => screen.getByText(/Show all types/i));
    fireEvent.click(screen.getByText(/Show all types/i));
    await waitFor(() =>
      expect(mockGetLibrary).toHaveBeenCalledWith(
        expect.objectContaining({ workout_type: undefined })
      )
    );
  });
});

describe("DashboardPage - already set up banner", () => {
  it("shows banner when navigated from onboarding", async () => {
    // Simulate ?from=onboarding in the URL
    Object.defineProperty(window, "location", {
      value: { ...window.location, search: "?from=onboarding" },
      writable: true,
    });
    mockGetUpcomingPlan.mockResolvedValue(makePlan(getCurrentMondayISO()));
    render(<DashboardPage />);
    await waitFor(() =>
      expect(screen.getByText(/You're already all set/i)).toBeInTheDocument()
    );
    // Restore
    Object.defineProperty(window, "location", {
      value: { ...window.location, search: "" },
      writable: true,
    });
  });

  it("does not show banner without from=onboarding param", async () => {
    mockGetUpcomingPlan.mockResolvedValue(makePlan(getCurrentMondayISO()));
    render(<DashboardPage />);
    await waitFor(() => screen.getByText(/Regenerate/i));
    expect(screen.queryByText(/You're already all set/i)).not.toBeInTheDocument();
  });

  it("dismisses banner when X is clicked", async () => {
    Object.defineProperty(window, "location", {
      value: { ...window.location, search: "?from=onboarding" },
      writable: true,
    });
    mockGetUpcomingPlan.mockResolvedValue(makePlan(getCurrentMondayISO()));
    render(<DashboardPage />);
    await waitFor(() => screen.getByText(/You're already all set/i));
    fireEvent.click(screen.getByRole("button", { name: /Dismiss/i }));
    expect(screen.queryByText(/You're already all set/i)).not.toBeInTheDocument();
    Object.defineProperty(window, "location", {
      value: { ...window.location, search: "" },
      writable: true,
    });
  });
});

// ---------------------------------------------------------------------------
// Publish flow
// ---------------------------------------------------------------------------

const mockUserWithYouTube = {
  ...mockUser,
  youtube_connected: true,
  credentials_valid: true,
};

describe("DashboardPage - publish flow", () => {
  it("shows 'Publishing...' on button while publishing", async () => {
    mockGetMe.mockResolvedValue(mockUserWithYouTube);
    mockGetUpcomingPlan.mockResolvedValue(makePlan(getCurrentMondayISO()));
    // publishPlan resolves but getPublishStatus stays publishing
    mockPublishPlan.mockResolvedValue({ message: "Publishing started" });
    mockGetPublishStatus.mockResolvedValue({ status: "publishing" });

    render(<DashboardPage />);
    await waitFor(() => screen.getByText("Publish to YouTube"));
    fireEvent.click(screen.getByText("Publish to YouTube"));
    await waitFor(() =>
      expect(screen.getByText("Publishing…")).toBeInTheDocument()
    );
  });

  it("shows publishing in progress banner while status is publishing", async () => {
    mockGetMe.mockResolvedValue(mockUserWithYouTube);
    mockGetUpcomingPlan.mockResolvedValue(makePlan(getCurrentMondayISO()));
    mockPublishPlan.mockResolvedValue({ message: "Publishing started" });
    mockGetPublishStatus.mockResolvedValue({ status: "publishing" });

    render(<DashboardPage />);
    await waitFor(() => screen.getByText("Publish to YouTube"));
    fireEvent.click(screen.getByText("Publish to YouTube"));
    await waitFor(() =>
      expect(screen.getByText(/Publishing your plan to YouTube/i)).toBeInTheDocument()
    );
  });

  it("shows success banner when publish completes", async () => {
    mockGetMe.mockResolvedValue(mockUserWithYouTube);
    mockGetUpcomingPlan.mockResolvedValue(makePlan(getCurrentMondayISO()));
    mockPublishPlan.mockResolvedValue({ message: "Publishing started" });
    // Poll returns done immediately when called
    mockGetPublishStatus.mockResolvedValue({
      status: "done",
      playlist_url: "https://youtube.com/playlist?list=abc",
      video_count: 4,
      error: null,
    });

    vi.useFakeTimers({ shouldAdvanceTime: true });
    render(<DashboardPage />);

    // Wait for page to load with real-timer resolution
    vi.useRealTimers();
    await waitFor(() => screen.getByText("Publish to YouTube"));
    fireEvent.click(screen.getByText("Publish to YouTube"));

    // setInterval fires at 2000ms - wait for the poll to be called
    await waitFor(() =>
      expect(mockGetPublishStatus).toHaveBeenCalled()
    , { timeout: 4000 });

    await waitFor(() =>
      expect(screen.getByText(/Plan published/i)).toBeInTheDocument()
    , { timeout: 4000 });
    expect(screen.getByText(/Open playlist/i)).toBeInTheDocument();
  }, 10000);

  it("shows error banner when publishPlan itself fails", async () => {
    mockGetMe.mockResolvedValue(mockUserWithYouTube);
    mockGetUpcomingPlan.mockResolvedValue(makePlan(getCurrentMondayISO()));
    mockPublishPlan.mockRejectedValue(new Error("No plan generated yet"));

    render(<DashboardPage />);
    await waitFor(() => screen.getByText("Publish to YouTube"));
    fireEvent.click(screen.getByText("Publish to YouTube"));
    // Error is shown via publishStatus failed banner
    await waitFor(() =>
      expect(screen.getByText("No plan generated yet")).toBeInTheDocument()
    , { timeout: 3000 });
  });
});
