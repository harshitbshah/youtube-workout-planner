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
  triggerScan: vi.fn(),
  getJobStatus: vi.fn(),
  searchChannels: vi.fn(),
  addChannel: vi.fn(),
  deleteChannel: vi.fn(),
}));

const mockUpdateSchedule = api.updateSchedule as ReturnType<typeof vi.fn>;
const mockTriggerScan = api.triggerScan as ReturnType<typeof vi.fn>;

beforeEach(() => {
  vi.clearAllMocks();
  mockUpdateSchedule.mockResolvedValue(undefined);
  mockTriggerScan.mockResolvedValue({});
  (api.getJobStatus as ReturnType<typeof vi.fn>).mockResolvedValue({ stage: null, total: null, done: null, error: null });
  (api.searchChannels as ReturnType<typeof vi.fn>).mockResolvedValue([]);
});

describe("OnboardingPage — Step 1 (Life Stage)", () => {
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

  it("clicking a life stage advances to step 2", () => {
    render(<OnboardingPage />);
    fireEvent.click(screen.getByText("Active adult"));
    expect(screen.getByText(/What's your main goal/i)).toBeInTheDocument();
  });
});

describe("OnboardingPage — Step 2 (Goal)", () => {
  it("shows adult goals after selecting 'Active adult'", () => {
    render(<OnboardingPage />);
    fireEvent.click(screen.getByText("Active adult"));
    expect(screen.getByText("Build muscle")).toBeInTheDocument();
    expect(screen.getByText("Lose fat")).toBeInTheDocument();
    expect(screen.getByText("Improve cardio")).toBeInTheDocument();
    expect(screen.getByText("Stay consistent")).toBeInTheDocument();
  });

  it("shows senior goals after selecting '55 and thriving'", () => {
    render(<OnboardingPage />);
    fireEvent.click(screen.getByText("55 and thriving"));
    expect(screen.getByText("Stay active & healthy")).toBeInTheDocument();
    expect(screen.getByText("Improve flexibility")).toBeInTheDocument();
    expect(screen.getByText("Build strength safely")).toBeInTheDocument();
  });

  it("shows athlete goals after selecting 'Training seriously'", () => {
    render(<OnboardingPage />);
    fireEvent.click(screen.getByText("Training seriously"));
    expect(screen.getByText("Strength & hypertrophy")).toBeInTheDocument();
    expect(screen.getByText("Endurance")).toBeInTheDocument();
    expect(screen.getByText("Athletic performance")).toBeInTheDocument();
    expect(screen.getByText("Cut weight")).toBeInTheDocument();
  });

  it("clicking a goal advances to step 3", () => {
    render(<OnboardingPage />);
    fireEvent.click(screen.getByText("Active adult"));
    fireEvent.click(screen.getByText("Build muscle"));
    expect(screen.getByText(/How many days a week can you train/i)).toBeInTheDocument();
  });

  it("Back button returns to step 1", () => {
    render(<OnboardingPage />);
    fireEvent.click(screen.getByText("Active adult"));
    fireEvent.click(screen.getByText("← Back"));
    expect(screen.getByText(/First, tell us a bit about yourself/i)).toBeInTheDocument();
  });
});

describe("OnboardingPage — Step 3 (Training Days)", () => {
  function goToStep3(profile = "Active adult", goal = "Build muscle") {
    render(<OnboardingPage />);
    fireEvent.click(screen.getByText(profile));
    fireEvent.click(screen.getByText(goal));
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
    fireEvent.click(screen.getByText("Stay active & healthy"));
    expect(screen.queryByRole("button", { name: "6" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "5" })).toBeInTheDocument();
  });

  it("clicking a day button advances to step 4", () => {
    goToStep3();
    fireEvent.click(screen.getByRole("button", { name: "4" }));
    expect(screen.getByText(/How long per session/i)).toBeInTheDocument();
  });

  it("adult default training days is 4", () => {
    goToStep3();
    const btn4 = screen.getByRole("button", { name: "4" });
    expect(btn4.className).toMatch(/bg-white/);
  });
});

describe("OnboardingPage — Step 4 (Session Length)", () => {
  function goToStep4(profile = "Active adult", goal = "Build muscle", days = "4") {
    render(<OnboardingPage />);
    fireEvent.click(screen.getByText(profile));
    fireEvent.click(screen.getByText(goal));
    fireEvent.click(screen.getByRole("button", { name: days }));
  }

  it("renders all session length options", () => {
    goToStep4();
    expect(screen.getByText("15–20 min")).toBeInTheDocument();
    expect(screen.getByText("25–35 min")).toBeInTheDocument();
    expect(screen.getByText("40–60 min")).toBeInTheDocument();
    expect(screen.getByText("No preference")).toBeInTheDocument();
  });

  it("selecting session length advances to step 5", () => {
    goToStep4();
    fireEvent.click(screen.getByText("25–35 min"));
    expect(screen.getByText(/Here's your personalised plan/i)).toBeInTheDocument();
  });

  it("shows affirming copy for senior profile", () => {
    render(<OnboardingPage />);
    fireEvent.click(screen.getByText("55 and thriving"));
    fireEvent.click(screen.getByText("Stay active & healthy"));
    fireEvent.click(screen.getByRole("button", { name: "3" }));
    expect(screen.getByText(/Short sessions are just as effective/i)).toBeInTheDocument();
  });

  it("shows affirming copy for beginner profile", () => {
    render(<OnboardingPage />);
    fireEvent.click(screen.getByText("Just starting out"));
    fireEvent.click(screen.getByText("Build a habit"));
    fireEvent.click(screen.getByRole("button", { name: "3" }));
    expect(screen.getByText(/Short sessions are just as effective/i)).toBeInTheDocument();
  });
});

describe("OnboardingPage — Step 5 (Schedule Preview)", () => {
  function goToStep5(profile = "Active adult", goal = "Build muscle", days = "4", duration = "25–35 min") {
    render(<OnboardingPage />);
    fireEvent.click(screen.getByText(profile));
    fireEvent.click(screen.getByText(goal));
    fireEvent.click(screen.getByRole("button", { name: days }));
    fireEvent.click(screen.getByText(duration));
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
    fireEvent.click(screen.getByText("Stay active & healthy"));
    fireEvent.click(screen.getByRole("button", { name: "3" }));
    fireEvent.click(screen.getByText("15–20 min"));
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

  it("'Looks good →' saves schedule and advances to step 6", async () => {
    goToStep5();
    fireEvent.click(screen.getByRole("button", { name: /Looks good/i }));
    await waitFor(() => {
      expect(mockUpdateSchedule).toHaveBeenCalledOnce();
      expect(screen.getByText(/Add your favourite channels/i)).toBeInTheDocument();
    });
  });
});

describe("OnboardingPage — Step 6 (Channels)", () => {
  async function goToStep6(profile = "Active adult", goal = "Build muscle") {
    render(<OnboardingPage />);
    fireEvent.click(screen.getByText(profile));
    fireEvent.click(screen.getByText(goal));
    fireEvent.click(screen.getByRole("button", { name: "4" }));
    fireEvent.click(screen.getByText("25–35 min"));
    fireEvent.click(screen.getByRole("button", { name: /Looks good/i }));
    await waitFor(() => screen.getByText(/Add your favourite channels/i));
  }

  it("shows channel manager heading", async () => {
    await goToStep6();
    expect(screen.getByText(/Add your favourite channels/i)).toBeInTheDocument();
  });

  it("Continue button is disabled with 0 channels", async () => {
    await goToStep6();
    expect(screen.getByRole("button", { name: /Continue/i })).toBeDisabled();
  });

  it("shows adult suggestions", async () => {
    await goToStep6();
    expect(screen.getByText("Athlean-X")).toBeInTheDocument();
  });

  it("shows senior subheading for senior profile", async () => {
    render(<OnboardingPage />);
    fireEvent.click(screen.getByText("55 and thriving"));
    fireEvent.click(screen.getByText("Stay active & healthy"));
    fireEvent.click(screen.getByRole("button", { name: "3" }));
    fireEvent.click(screen.getByText("15–20 min"));
    fireEvent.click(screen.getByRole("button", { name: /Looks good/i }));
    await waitFor(() => screen.getByText(/Add your favourite channels/i));
    expect(screen.getByText(/gentle movement/i)).toBeInTheDocument();
  });
});

describe("OnboardingPage — Step Indicator", () => {
  it("shows 'Profile' as active on step 1", () => {
    render(<OnboardingPage />);
    const profileEl = screen.getByText("Profile");
    expect(profileEl.className).toMatch(/text-white/);
  });

  it("shows 'Channels' as active on step 6", async () => {
    render(<OnboardingPage />);
    fireEvent.click(screen.getByText("Active adult"));
    fireEvent.click(screen.getByText("Build muscle"));
    fireEvent.click(screen.getByRole("button", { name: "4" }));
    fireEvent.click(screen.getByText("25–35 min"));
    fireEvent.click(screen.getByRole("button", { name: /Looks good/i }));
    await waitFor(() => screen.getByText(/Add your favourite channels/i));
    const channelsEl = screen.getByText("Channels");
    expect(channelsEl.className).toMatch(/text-white/);
  });
});
