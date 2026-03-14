import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import DashboardPage from "./page";
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
  getUpcomingPlan: vi.fn(),
  generatePlan: vi.fn(),
  publishPlan: vi.fn(),
  triggerScan: vi.fn(),
  getJobStatus: vi.fn(),
  getActiveAnnouncement: vi.fn(),
  logout: vi.fn(),
}));

const mockGetMe = api.getMe as ReturnType<typeof vi.fn>;
const mockGetChannels = api.getChannels as ReturnType<typeof vi.fn>;
const mockGetUpcomingPlan = api.getUpcomingPlan as ReturnType<typeof vi.fn>;
const mockGeneratePlan = api.generatePlan as ReturnType<typeof vi.fn>;
const mockGetJobStatus = api.getJobStatus as ReturnType<typeof vi.fn>;
const mockGetActiveAnnouncement = api.getActiveAnnouncement as ReturnType<typeof vi.fn>;

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
});

// ---------------------------------------------------------------------------
// Stale plan banner
// ---------------------------------------------------------------------------

describe("DashboardPage — stale plan banner", () => {
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

describe("DashboardPage — plan display", () => {
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
});

// ---------------------------------------------------------------------------
// Announcement banner
// ---------------------------------------------------------------------------

describe("DashboardPage — announcement banner", () => {
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
