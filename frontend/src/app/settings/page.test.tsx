import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import SettingsPage from "./page";
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
// Capture onChannelsChange so tests can simulate channel add/remove
let channelManagerOnChange: (ch: { id: string; name: string }[]) => void = () => {};
vi.mock("@/components/ChannelManager", () => ({
  default: ({ onChannelsChange }: { onChannelsChange: (ch: { id: string; name: string }[]) => void }) => {
    channelManagerOnChange = onChannelsChange;
    return <div data-testid="channel-manager" />;
  },
}));
vi.mock("@/components/ScheduleEditor", () => ({
  default: () => <div data-testid="schedule-editor" />,
}));

vi.mock("@/lib/api", () => ({
  getMe: vi.fn(),
  getChannels: vi.fn(),
  getSchedule: vi.fn(),
  getSuggestions: vi.fn(),
  patchMe: vi.fn(),
  deleteMe: vi.fn(),
  updateSchedule: vi.fn(),
  updateEmailNotifications: vi.fn(),
  generatePlan: vi.fn(),
  logout: vi.fn(),
}));

const mockGetMe = api.getMe as ReturnType<typeof vi.fn>;
const mockGetChannels = api.getChannels as ReturnType<typeof vi.fn>;
const mockGetSchedule = api.getSchedule as ReturnType<typeof vi.fn>;
const mockPatchMe = api.patchMe as ReturnType<typeof vi.fn>;
const mockDeleteMe = api.deleteMe as ReturnType<typeof vi.fn>;
const mockUpdateSchedule = api.updateSchedule as ReturnType<typeof vi.fn>;
const mockUpdateEmailNotifications = api.updateEmailNotifications as ReturnType<typeof vi.fn>;
const mockLogout = api.logout as ReturnType<typeof vi.fn>;

const mockGeneratePlan = api.generatePlan as ReturnType<typeof vi.fn>;

const mockUser = {
  id: 1,
  display_name: "Harshit",
  email: "harshit@example.com",
  youtube_connected: false,
  credentials_valid: true,
  is_admin: false,
  email_notifications: true,
};

const mockSchedule = {
  schedule: [
    { day: "monday", workout_type: "strength", body_focus: "upper", difficulty: "any", duration_min: 30, duration_max: 45 },
    { day: "tuesday", workout_type: null, body_focus: null, difficulty: "any", duration_min: null, duration_max: null },
    { day: "wednesday", workout_type: "hiit", body_focus: "full", difficulty: "any", duration_min: 30, duration_max: 45 },
    { day: "thursday", workout_type: null, body_focus: null, difficulty: "any", duration_min: null, duration_max: null },
    { day: "friday", workout_type: "cardio", body_focus: "full", difficulty: "any", duration_min: 30, duration_max: 45 },
    { day: "saturday", workout_type: null, body_focus: null, difficulty: "any", duration_min: null, duration_max: null },
    { day: "sunday", workout_type: null, body_focus: null, difficulty: "any", duration_min: null, duration_max: null },
  ],
};

beforeEach(() => {
  vi.clearAllMocks();
  mockGetMe.mockResolvedValue(mockUser);
  mockGetChannels.mockResolvedValue([]);
  mockGetSchedule.mockResolvedValue(mockSchedule);
  mockPatchMe.mockResolvedValue({ ...mockUser, display_name: "Updated" });
  mockDeleteMe.mockResolvedValue(undefined);
  mockUpdateSchedule.mockResolvedValue(undefined);
  mockUpdateEmailNotifications.mockResolvedValue({ ...mockUser, email_notifications: false });
  mockGeneratePlan.mockResolvedValue({});
  mockLogout.mockResolvedValue(undefined);
  (api.getSuggestions as ReturnType<typeof vi.fn>).mockResolvedValue([]);
});

describe("SettingsPage - initial render", () => {
  it("renders the Settings heading", async () => {
    render(<SettingsPage />);
    await waitFor(() => expect(screen.getByText("Settings")).toBeInTheDocument());
  });

  it("shows user email as read-only", async () => {
    render(<SettingsPage />);
    await waitFor(() => expect(screen.getByText("harshit@example.com")).toBeInTheDocument());
  });

  it("populates display name input with current name", async () => {
    render(<SettingsPage />);
    await waitFor(() =>
      expect(screen.getByDisplayValue("Harshit")).toBeInTheDocument()
    );
  });

  it("renders ChannelManager", async () => {
    render(<SettingsPage />);
    await waitFor(() => expect(screen.getByTestId("channel-manager")).toBeInTheDocument());
  });

  it("renders ScheduleEditor", async () => {
    render(<SettingsPage />);
    await waitFor(() => expect(screen.getByTestId("schedule-editor")).toBeInTheDocument());
  });
});

describe("SettingsPage - display name", () => {
  it("Save button is disabled when name matches current value", async () => {
    render(<SettingsPage />);
    await waitFor(() => screen.getByDisplayValue("Harshit"));
    expect(screen.getByRole("button", { name: /^Save$/i })).toBeDisabled();
  });

  it("Save button enables when name is changed", async () => {
    render(<SettingsPage />);
    await waitFor(() => screen.getByDisplayValue("Harshit"));
    fireEvent.change(screen.getByDisplayValue("Harshit"), { target: { value: "Harshit S" } });
    expect(screen.getByRole("button", { name: /^Save$/i })).not.toBeDisabled();
  });

  it("calls patchMe and shows success on save", async () => {
    render(<SettingsPage />);
    await waitFor(() => screen.getByDisplayValue("Harshit"));
    fireEvent.change(screen.getByDisplayValue("Harshit"), { target: { value: "Harshit S" } });
    fireEvent.click(screen.getByRole("button", { name: /^Save$/i }));
    await waitFor(() => expect(mockPatchMe).toHaveBeenCalledWith("Harshit S"));
    await waitFor(() =>
      expect(screen.getByText(/Display name updated/i)).toBeInTheDocument()
    );
  });

  it("shows error message when patchMe fails", async () => {
    mockPatchMe.mockRejectedValue(new Error("Server error"));
    render(<SettingsPage />);
    await waitFor(() => screen.getByDisplayValue("Harshit"));
    fireEvent.change(screen.getByDisplayValue("Harshit"), { target: { value: "New Name" } });
    fireEvent.click(screen.getByRole("button", { name: /^Save$/i }));
    await waitFor(() =>
      expect(screen.getByText(/Failed to update name/i)).toBeInTheDocument()
    );
  });
});

describe("SettingsPage - schedule", () => {
  it("calls updateSchedule when 'Save schedule' is clicked", async () => {
    render(<SettingsPage />);
    await waitFor(() => screen.getByRole("button", { name: /Save schedule/i }));
    fireEvent.click(screen.getByRole("button", { name: /Save schedule/i }));
    await waitFor(() => expect(mockUpdateSchedule).toHaveBeenCalledOnce());
  });

  it("shows success message after schedule save", async () => {
    render(<SettingsPage />);
    await waitFor(() => screen.getByRole("button", { name: /Save schedule/i }));
    fireEvent.click(screen.getByRole("button", { name: /Save schedule/i }));
    await waitFor(() =>
      expect(screen.getByText(/Schedule saved/i)).toBeInTheDocument()
    );
  });

  it("shows error message when updateSchedule fails", async () => {
    mockUpdateSchedule.mockRejectedValue(new Error("Server error"));
    render(<SettingsPage />);
    await waitFor(() => screen.getByRole("button", { name: /Save schedule/i }));
    fireEvent.click(screen.getByRole("button", { name: /Save schedule/i }));
    await waitFor(() =>
      expect(screen.getByText(/Failed to save/i)).toBeInTheDocument()
    );
  });
});

describe("SettingsPage - delete account", () => {
  it("shows 'Delete my account' button", async () => {
    render(<SettingsPage />);
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /Delete my account/i })).toBeInTheDocument()
    );
  });

  it("shows confirmation prompt after clicking delete", async () => {
    render(<SettingsPage />);
    await waitFor(() => screen.getByRole("button", { name: /Delete my account/i }));
    fireEvent.click(screen.getByRole("button", { name: /Delete my account/i }));
    expect(screen.getByText(/Are you sure/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Yes, delete my account/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Cancel/i })).toBeInTheDocument();
  });

  it("cancels deletion when Cancel is clicked", async () => {
    render(<SettingsPage />);
    await waitFor(() => screen.getByRole("button", { name: /Delete my account/i }));
    fireEvent.click(screen.getByRole("button", { name: /Delete my account/i }));
    fireEvent.click(screen.getByRole("button", { name: /Cancel/i }));
    expect(screen.queryByText(/Are you sure/i)).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Delete my account/i })).toBeInTheDocument();
  });

  it("calls deleteMe and logout on confirm", async () => {
    render(<SettingsPage />);
    await waitFor(() => screen.getByRole("button", { name: /Delete my account/i }));
    fireEvent.click(screen.getByRole("button", { name: /Delete my account/i }));
    fireEvent.click(screen.getByRole("button", { name: /Yes, delete my account/i }));
    await waitFor(() => expect(mockDeleteMe).toHaveBeenCalledOnce());
    await waitFor(() => expect(mockLogout).toHaveBeenCalledOnce());
  });
});

describe("SettingsPage - channel change regenerate banner", () => {
  const twoChannels = [
    { id: "ch1", name: "Jeff Nippard" },
    { id: "ch2", name: "Chloe Ting" },
  ];

  beforeEach(() => {
    mockGetChannels.mockResolvedValue(twoChannels);
  });

  it("banner not shown on initial render", async () => {
    render(<SettingsPage />);
    await waitFor(() => screen.getByTestId("channel-manager"));
    expect(screen.queryByText(/doesn't reflect your latest channel changes/i)).not.toBeInTheDocument();
  });

  it("shows regenerate banner when a channel is removed", async () => {
    render(<SettingsPage />);
    await waitFor(() => screen.getByTestId("channel-manager"));
    channelManagerOnChange([twoChannels[0]]);
    await waitFor(() =>
      expect(screen.getByText(/doesn't reflect your latest channel changes/i)).toBeInTheDocument()
    );
  });

  it("shows regenerate banner when a channel is added", async () => {
    render(<SettingsPage />);
    await waitFor(() => screen.getByTestId("channel-manager"));
    channelManagerOnChange([...twoChannels, { id: "ch3", name: "New Channel" }]);
    await waitFor(() =>
      expect(screen.getByText(/doesn't reflect your latest channel changes/i)).toBeInTheDocument()
    );
  });

  it("dismisses banner when Dismiss is clicked", async () => {
    render(<SettingsPage />);
    await waitFor(() => screen.getByTestId("channel-manager"));
    channelManagerOnChange([twoChannels[0]]);
    await waitFor(() => screen.getByText(/doesn't reflect your latest channel changes/i));
    fireEvent.click(screen.getByRole("button", { name: /Dismiss/i }));
    expect(screen.queryByText(/doesn't reflect your latest channel changes/i)).not.toBeInTheDocument();
  });

  it("calls generatePlan and hides banner on regenerate", async () => {
    render(<SettingsPage />);
    await waitFor(() => screen.getByTestId("channel-manager"));
    channelManagerOnChange([twoChannels[0]]);
    await waitFor(() => screen.getByRole("button", { name: /Regenerate now/i }));
    fireEvent.click(screen.getByRole("button", { name: /Regenerate now/i }));
    await waitFor(() => expect(mockGeneratePlan).toHaveBeenCalledOnce());
    await waitFor(() =>
      expect(screen.queryByText(/doesn't reflect your latest channel changes/i)).not.toBeInTheDocument()
    );
  });

  it("shows error message when generatePlan fails", async () => {
    mockGeneratePlan.mockRejectedValue(new Error("Server error"));
    render(<SettingsPage />);
    await waitFor(() => screen.getByTestId("channel-manager"));
    channelManagerOnChange([twoChannels[0]]);
    await waitFor(() => screen.getByRole("button", { name: /Regenerate now/i }));
    fireEvent.click(screen.getByRole("button", { name: /Regenerate now/i }));
    await waitFor(() =>
      expect(screen.getByText(/Failed to regenerate/i)).toBeInTheDocument()
    );
  });
});
