import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import OnboardingPage from "./page";
import * as api from "@/lib/api";

// Mock next/navigation
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

// Mock api calls
vi.mock("@/lib/api", () => ({
  updateSchedule: vi.fn(),
  updateEmailNotifications: vi.fn(),
  triggerScan: vi.fn(),
  getJobStatus: vi.fn(),
  searchChannels: vi.fn(),
  addChannel: vi.fn(),
  deleteChannel: vi.fn(),
  getSuggestions: vi.fn(),
}));

const mockUpdateSchedule = api.updateSchedule as ReturnType<typeof vi.fn>;
const mockUpdateEmailNotifications = api.updateEmailNotifications as ReturnType<typeof vi.fn>;
const mockTriggerScan = api.triggerScan as ReturnType<typeof vi.fn>;

beforeEach(() => {
  vi.clearAllMocks();
  mockUpdateSchedule.mockResolvedValue(undefined);
  mockUpdateEmailNotifications.mockResolvedValue({});
  mockTriggerScan.mockResolvedValue({});
  (api.getJobStatus as ReturnType<typeof vi.fn>).mockResolvedValue({ stage: null, total: null, done: null, error: null });
  (api.searchChannels as ReturnType<typeof vi.fn>).mockResolvedValue([]);
  (api.getSuggestions as ReturnType<typeof vi.fn>).mockResolvedValue([
    { youtube_channel_id: "UCabc", name: "Athlean-X", description: "Strength training", thumbnail_url: null },
    { youtube_channel_id: "UCdef", name: "Jeff Nippard", description: "Science-based", thumbnail_url: null },
    { youtube_channel_id: "UCghi", name: "Heather Robertson", description: "Workouts", thumbnail_url: null },
  ]);
});

// Helper: click "Next →" button (used across steps)
function clickNext() {
  fireEvent.click(screen.getByRole("button", { name: /Next →/i }));
}

describe("OnboardingPage - Step 1 (Life Stage)", () => {
  it("renders life stage heading", () => {
    render(<OnboardingPage />);
    expect(screen.getByText(/First, tell us a bit about yourself/i)).toBeInTheDocument();
  });

  it("renders all 4 life stage options", () => {
    render(<OnboardingPage />);
    expect(screen.getByText("Just starting out")).toBeInTheDocument();
    expect(screen.getByText("Active adult")).toBeInTheDocument();
    expect(screen.getByText("55 and thriving")).toBeInTheDocument();
    expect(screen.getByText("Training seriously")).toBeInTheDocument();
  });

  it("Next button is disabled until a life stage is selected", () => {
    render(<OnboardingPage />);
    expect(screen.getByRole("button", { name: /Next →/i })).toBeDisabled();
  });

  it("selecting a life stage then clicking Next advances to step 2", () => {
    render(<OnboardingPage />);
    fireEvent.click(screen.getByText("Active adult"));
    clickNext();
    expect(screen.getByText(/What's your main goal/i)).toBeInTheDocument();
  });
});

describe("OnboardingPage - Step 2 (Goal)", () => {
  it("shows adult goals after selecting 'Active adult' and clicking Next", () => {
    render(<OnboardingPage />);
    fireEvent.click(screen.getByText("Active adult"));
    clickNext();
    expect(screen.getByText("Build muscle")).toBeInTheDocument();
    expect(screen.getByText("Lose fat")).toBeInTheDocument();
    expect(screen.getByText("Improve cardio")).toBeInTheDocument();
    expect(screen.getByText("Stay consistent")).toBeInTheDocument();
  });

  it("shows senior goals after selecting '55 and thriving' and clicking Next", () => {
    render(<OnboardingPage />);
    fireEvent.click(screen.getByText("55 and thriving"));
    clickNext();
    expect(screen.getByText("Stay active & healthy")).toBeInTheDocument();
    expect(screen.getByText("Improve flexibility")).toBeInTheDocument();
    expect(screen.getByText("Build strength safely")).toBeInTheDocument();
  });

  it("shows athlete goals after selecting 'Training seriously' and clicking Next", () => {
    render(<OnboardingPage />);
    fireEvent.click(screen.getByText("Training seriously"));
    clickNext();
    expect(screen.getByText("Strength & hypertrophy")).toBeInTheDocument();
    expect(screen.getByText("Endurance")).toBeInTheDocument();
    expect(screen.getByText("Athletic performance")).toBeInTheDocument();
    expect(screen.getByText("Cut weight")).toBeInTheDocument();
  });

  it("Next button is disabled until a goal is selected", () => {
    render(<OnboardingPage />);
    fireEvent.click(screen.getByText("Active adult"));
    clickNext();
    expect(screen.getByRole("button", { name: /Next →/i })).toBeDisabled();
  });

  it("selecting a goal then clicking Next advances to step 3", () => {
    render(<OnboardingPage />);
    fireEvent.click(screen.getByText("Active adult"));
    clickNext();
    fireEvent.click(screen.getByText("Build muscle"));
    clickNext();
    expect(screen.getByText(/How many days a week can you train/i)).toBeInTheDocument();
  });

  it("Back button returns to step 1", () => {
    render(<OnboardingPage />);
    fireEvent.click(screen.getByText("Active adult"));
    clickNext();
    fireEvent.click(screen.getByRole("button", { name: /← Back/i }));
    expect(screen.getByText(/First, tell us a bit about yourself/i)).toBeInTheDocument();
  });
});

describe("OnboardingPage - Step 3 (Training Days)", () => {
  function goToStep3(profile = "Active adult", goal = "Build muscle") {
    render(<OnboardingPage />);
    fireEvent.click(screen.getByText(profile));
    clickNext();
    fireEvent.click(screen.getByText(goal));
    clickNext();
  }

  it("renders day buttons 2–6 for adult", () => {
    goToStep3();
    [2, 3, 4, 5, 6].forEach((d) => {
      expect(screen.getByRole("button", { name: String(d) })).toBeInTheDocument();
    });
  });

  it("senior profile shows max 5 day buttons (no 6)", () => {
    render(<OnboardingPage />);
    fireEvent.click(screen.getByText("55 and thriving"));
    clickNext();
    fireEvent.click(screen.getByText("Stay active & healthy"));
    clickNext();
    expect(screen.queryByRole("button", { name: "6" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "5" })).toBeInTheDocument();
  });

  it("clicking a day button then Next advances to step 4", () => {
    goToStep3();
    fireEvent.click(screen.getByRole("button", { name: "4" }));
    clickNext();
    expect(screen.getByText(/How long per session/i)).toBeInTheDocument();
  });

  it("adult default training days is 4 (highlighted)", () => {
    goToStep3();
    const btn4 = screen.getByRole("button", { name: "4" });
    expect(btn4.className).toMatch(/bg-white/);
  });
});

describe("OnboardingPage - Step 4 (Session Length)", () => {
  function goToStep4(profile = "Active adult", goal = "Build muscle", days = "4") {
    render(<OnboardingPage />);
    fireEvent.click(screen.getByText(profile));
    clickNext();
    fireEvent.click(screen.getByText(goal));
    clickNext();
    fireEvent.click(screen.getByRole("button", { name: days }));
    clickNext();
  }

  it("renders all session length options", () => {
    goToStep4();
    expect(screen.getByText("15–20 min")).toBeInTheDocument();
    expect(screen.getByText("25–35 min")).toBeInTheDocument();
    expect(screen.getByText("40–60 min")).toBeInTheDocument();
    expect(screen.getByText("No preference")).toBeInTheDocument();
  });

  it("selecting session length then clicking Next advances to step 5", () => {
    goToStep4();
    fireEvent.click(screen.getByText("25–35 min"));
    clickNext();
    expect(screen.getByText(/Here's your personalised plan/i)).toBeInTheDocument();
  });

  it("shows affirming copy for senior profile", () => {
    render(<OnboardingPage />);
    fireEvent.click(screen.getByText("55 and thriving"));
    clickNext();
    fireEvent.click(screen.getByText("Stay active & healthy"));
    clickNext();
    fireEvent.click(screen.getByRole("button", { name: "3" }));
    clickNext();
    expect(screen.getByText(/Short sessions are just as effective/i)).toBeInTheDocument();
  });

  it("shows affirming copy for beginner profile", () => {
    render(<OnboardingPage />);
    fireEvent.click(screen.getByText("Just starting out"));
    clickNext();
    fireEvent.click(screen.getByText("Build a habit"));
    clickNext();
    fireEvent.click(screen.getByRole("button", { name: "3" }));
    clickNext();
    expect(screen.getByText(/Short sessions are just as effective/i)).toBeInTheDocument();
  });
});

describe("OnboardingPage - Step 5 (Schedule Preview)", () => {
  function goToStep5(profile = "Active adult", goal = "Build muscle", days = "4", duration = "25–35 min") {
    render(<OnboardingPage />);
    fireEvent.click(screen.getByText(profile));
    clickNext();
    fireEvent.click(screen.getByText(goal));
    clickNext();
    fireEvent.click(screen.getByRole("button", { name: days }));
    clickNext();
    fireEvent.click(screen.getByText(duration));
    clickNext();
  }

  it("shows schedule preview heading", () => {
    goToStep5();
    expect(screen.getByText(/Here's your personalised plan/i)).toBeInTheDocument();
  });

  it("shows 'Looks good →' and 'Customise' buttons", () => {
    goToStep5();
    expect(screen.getByRole("button", { name: /Looks good/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Customise/i })).toBeInTheDocument();
  });

  it("senior profile shows 'Recovery day' not 'Rest day'", () => {
    render(<OnboardingPage />);
    fireEvent.click(screen.getByText("55 and thriving"));
    clickNext();
    fireEvent.click(screen.getByText("Stay active & healthy"));
    clickNext();
    fireEvent.click(screen.getByRole("button", { name: "3" }));
    clickNext();
    fireEvent.click(screen.getByText("15–20 min"));
    clickNext();
    expect(screen.getAllByText("Recovery day").length).toBeGreaterThan(0);
    expect(screen.queryByText("Rest day")).not.toBeInTheDocument();
  });

  it("non-senior profile shows 'Rest day' not 'Recovery day'", () => {
    goToStep5();
    expect(screen.getAllByText("Rest day").length).toBeGreaterThan(0);
    expect(screen.queryByText("Recovery day")).not.toBeInTheDocument();
  });

  it("'Customise' button shows ScheduleEditor", () => {
    goToStep5();
    fireEvent.click(screen.getByRole("button", { name: /Customise/i }));
    // ScheduleEditor renders day names with capitalize CSS; text content is lowercase
    expect(screen.getByText("monday")).toBeInTheDocument();
  });

  it("'Looks good →' saves schedule and advances to step 6 (email notifications)", async () => {
    goToStep5();
    fireEvent.click(screen.getByRole("button", { name: /Looks good/i }));
    await waitFor(() => {
      expect(mockUpdateSchedule).toHaveBeenCalledOnce();
      expect(screen.getByText(/Get your weekly plan by email/i)).toBeInTheDocument();
    });
  });

  it("'Looks good →' passes profile and goal to updateSchedule", async () => {
    goToStep5("Active adult", "Build muscle", "4", "25–35 min");
    fireEvent.click(screen.getByRole("button", { name: /Looks good/i }));
    await waitFor(() => {
      expect(mockUpdateSchedule).toHaveBeenCalledWith(
        expect.any(Array),
        "adult",
        "Build muscle",
      );
    });
  });
});

describe("OnboardingPage - Step 6 (Email Notifications)", () => {
  async function goToStep6(profile = "Active adult", goal = "Build muscle") {
    render(<OnboardingPage />);
    fireEvent.click(screen.getByText(profile));
    clickNext();
    fireEvent.click(screen.getByText(goal));
    clickNext();
    fireEvent.click(screen.getByRole("button", { name: "4" }));
    clickNext();
    fireEvent.click(screen.getByText("25–35 min"));
    clickNext();
    fireEvent.click(screen.getByRole("button", { name: /Looks good/i }));
    await waitFor(() => screen.getByText(/Get your weekly plan by email/i));
  }

  it("shows email notification heading", async () => {
    await goToStep6();
    expect(screen.getByText(/Get your weekly plan by email/i)).toBeInTheDocument();
  });

  it("'Yes' option is selected by default", async () => {
    await goToStep6();
    const yesCard = screen.getByText("Yes, email me my weekly plan").closest("button");
    expect(yesCard?.className).toMatch(/border-zinc-900|border-white/);
  });

  it("clicking 'No thanks' selects it", async () => {
    await goToStep6();
    fireEvent.click(screen.getByText("No thanks"));
    const noCard = screen.getByText("No thanks").closest("button");
    expect(noCard?.className).toMatch(/border-zinc-900|border-white/);
  });

  it("clicking Next calls updateEmailNotifications with true (default)", async () => {
    await goToStep6();
    clickNext();
    await waitFor(() => {
      expect(mockUpdateEmailNotifications).toHaveBeenCalledWith(true);
    });
  });

  it("opting out calls updateEmailNotifications with false", async () => {
    await goToStep6();
    fireEvent.click(screen.getByText("No thanks"));
    clickNext();
    await waitFor(() => {
      expect(mockUpdateEmailNotifications).toHaveBeenCalledWith(false);
    });
  });

  it("clicking Next advances to channels step", async () => {
    await goToStep6();
    clickNext();
    await waitFor(() => {
      expect(screen.getByText(/Add your favourite channels/i)).toBeInTheDocument();
    });
  });

  it("Back button returns to schedule preview", async () => {
    await goToStep6();
    fireEvent.click(screen.getByRole("button", { name: /← Back/i }));
    expect(screen.getByText(/Here's your personalised plan/i)).toBeInTheDocument();
  });
});

describe("OnboardingPage - Step 7 (Channels)", () => {
  async function goToStep7(profile = "Active adult", goal = "Build muscle") {
    render(<OnboardingPage />);
    fireEvent.click(screen.getByText(profile));
    clickNext();
    fireEvent.click(screen.getByText(goal));
    clickNext();
    fireEvent.click(screen.getByRole("button", { name: "4" }));
    clickNext();
    fireEvent.click(screen.getByText("25–35 min"));
    clickNext();
    fireEvent.click(screen.getByRole("button", { name: /Looks good/i }));
    await waitFor(() => screen.getByText(/Get your weekly plan by email/i));
    clickNext();
    await waitFor(() => screen.getByText(/Add your favourite channels/i));
  }

  it("shows channel manager heading", async () => {
    await goToStep7();
    expect(screen.getByText(/Add your favourite channels/i)).toBeInTheDocument();
  });

  it("Continue button is disabled with 0 channels", async () => {
    await goToStep7();
    expect(screen.getByRole("button", { name: /Continue/i })).toBeDisabled();
  });

  it("shows adult suggestions as cards after fetch resolves", async () => {
    await goToStep7();
    await waitFor(() => expect(screen.getByText("Athlean-X")).toBeInTheDocument());
    expect(api.getSuggestions).toHaveBeenCalledWith("adult");
  });

  it("shows senior subheading for senior profile", async () => {
    render(<OnboardingPage />);
    fireEvent.click(screen.getByText("55 and thriving"));
    clickNext();
    fireEvent.click(screen.getByText("Stay active & healthy"));
    clickNext();
    fireEvent.click(screen.getByRole("button", { name: "3" }));
    clickNext();
    fireEvent.click(screen.getByText("15–20 min"));
    clickNext();
    fireEvent.click(screen.getByRole("button", { name: /Looks good/i }));
    await waitFor(() => screen.getByText(/Get your weekly plan by email/i));
    clickNext();
    await waitFor(() => screen.getByText(/Add your favourite channels/i));
    expect(screen.getByText(/gentle movement/i)).toBeInTheDocument();
  });
});

describe("OnboardingPage - Step 8 (Progress)", () => {
  async function goToStep8() {
    const mockAddChannel = api.addChannel as ReturnType<typeof vi.fn>;
    mockAddChannel.mockResolvedValue({
      id: "ch1", name: "Athlean-X", youtube_url: "https://youtube.com/channel/UCabc",
      youtube_channel_id: "UCabc", thumbnail_url: null, added_at: "2024-01-01",
    });

    render(<OnboardingPage />);
    fireEvent.click(screen.getByText("Active adult"));
    clickNext();
    fireEvent.click(screen.getByText("Build muscle"));
    clickNext();
    fireEvent.click(screen.getByRole("button", { name: "4" }));
    clickNext();
    fireEvent.click(screen.getByText("25–35 min"));
    clickNext();
    fireEvent.click(screen.getByRole("button", { name: /Looks good/i }));
    await waitFor(() => screen.getByText(/Get your weekly plan by email/i));
    // Accept default (Yes) and continue
    clickNext();
    await waitFor(() => screen.getByText(/Add your favourite channels/i));

    // Add a channel via suggestion card then continue
    await waitFor(() => screen.getByText("Athlean-X"));
    fireEvent.click(screen.getAllByRole("button", { name: /\+ Add/i })[0]);
    await waitFor(() => screen.getByRole("button", { name: /Continue →/i }));
    fireEvent.click(screen.getByRole("button", { name: /Continue →/i }));
    await waitFor(() => screen.getByText(/Setting up your plan/i));
  }

  it("shows 'Go to dashboard' escape hatch on step 8", async () => {
    await goToStep8();
    expect(screen.getByRole("button", { name: /Go to dashboard/i })).toBeInTheDocument();
  });

  it("shows 'preparing X / total' for negative classify progress", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      (api.getJobStatus as ReturnType<typeof vi.fn>).mockResolvedValue({
        stage: "classifying", total: 43, done: -40, error: null,
      });
      await goToStep8();
      // Advance past the 3s poll interval so pollStatus fires
      await vi.advanceTimersByTimeAsync(3100);
      await waitFor(() =>
        expect(screen.getByText(/preparing 40 \/ 43/i)).toBeInTheDocument()
      );
    } finally {
      vi.useRealTimers();
    }
  });
});

describe("OnboardingPage - Step Indicator", () => {
  it("shows 'Profile' as active on step 1", () => {
    render(<OnboardingPage />);
    const profileEl = screen.getByText("Profile");
    expect(profileEl.className).toMatch(/text-white/);
  });

  it("shows 'Channels' as active on step 7", async () => {
    render(<OnboardingPage />);
    fireEvent.click(screen.getByText("Active adult"));
    clickNext();
    fireEvent.click(screen.getByText("Build muscle"));
    clickNext();
    fireEvent.click(screen.getByRole("button", { name: "4" }));
    clickNext();
    fireEvent.click(screen.getByText("25–35 min"));
    clickNext();
    fireEvent.click(screen.getByRole("button", { name: /Looks good/i }));
    await waitFor(() => screen.getByText(/Get your weekly plan by email/i));
    clickNext();
    await waitFor(() => screen.getByText(/Add your favourite channels/i));
    const channelsEl = screen.getByText("Channels");
    expect(channelsEl.className).toMatch(/text-white/);
  });
});
