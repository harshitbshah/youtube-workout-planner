import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import FeedbackWidget from "./FeedbackWidget";
import * as api from "@/lib/api";

vi.mock("@/lib/api", () => ({
  submitFeedback: vi.fn(),
}));

const mockSubmitFeedback = api.submitFeedback as ReturnType<typeof vi.fn>;

beforeEach(() => {
  vi.clearAllMocks();
  mockSubmitFeedback.mockResolvedValue(undefined);
});

describe("FeedbackWidget - floating button", () => {
  it("renders the Feedback button", () => {
    render(<FeedbackWidget />);
    expect(screen.getByRole("button", { name: /Feedback/i })).toBeInTheDocument();
  });

  it("modal is not visible initially", () => {
    render(<FeedbackWidget />);
    expect(screen.queryByText(/Share feedback or get help/i)).not.toBeInTheDocument();
  });
});

describe("FeedbackWidget - modal open/close", () => {
  it("opens modal when Feedback button is clicked", () => {
    render(<FeedbackWidget />);
    fireEvent.click(screen.getByRole("button", { name: /Feedback/i }));
    expect(screen.getByText(/Share feedback or get help/i)).toBeInTheDocument();
  });

  it("closes modal when ✕ is clicked", () => {
    render(<FeedbackWidget />);
    fireEvent.click(screen.getByRole("button", { name: /Feedback/i }));
    fireEvent.click(screen.getByRole("button", { name: "✕" }));
    expect(screen.queryByText(/Share feedback or get help/i)).not.toBeInTheDocument();
  });

  it("resets state when modal is closed and reopened", () => {
    render(<FeedbackWidget />);
    fireEvent.click(screen.getByRole("button", { name: /Feedback/i }));
    const textarea = screen.getByPlaceholderText(/Tell us what's on your mind/i);
    fireEvent.change(textarea, { target: { value: "some message" } });
    fireEvent.click(screen.getByRole("button", { name: "✕" }));
    fireEvent.click(screen.getByRole("button", { name: /Feedback/i }));
    expect(screen.getByPlaceholderText(/Tell us what's on your mind/i)).toHaveValue("");
  });
});

describe("FeedbackWidget - category selection", () => {
  it("renders all three category buttons", () => {
    render(<FeedbackWidget />);
    fireEvent.click(screen.getByRole("button", { name: /Feedback/i }));
    expect(screen.getByText(/General feedback/i)).toBeInTheDocument();
    expect(screen.getByText(/I need help/i)).toBeInTheDocument();
    expect(screen.getByText(/Found a bug/i)).toBeInTheDocument();
  });

  it("switches category when a different button is clicked", () => {
    render(<FeedbackWidget />);
    fireEvent.click(screen.getByRole("button", { name: /Feedback/i }));
    fireEvent.click(screen.getByText(/Found a bug/i));
    // Clicking the bug category should not crash and should remain in the modal
    expect(screen.getByText(/Share feedback or get help/i)).toBeInTheDocument();
  });
});

describe("FeedbackWidget - submit", () => {
  it("Send button is disabled when message is empty", () => {
    render(<FeedbackWidget />);
    fireEvent.click(screen.getByRole("button", { name: /Feedback/i }));
    expect(screen.getByRole("button", { name: /^Send$/i })).toBeDisabled();
  });

  it("Send button is enabled when message has content", () => {
    render(<FeedbackWidget />);
    fireEvent.click(screen.getByRole("button", { name: /Feedback/i }));
    fireEvent.change(screen.getByPlaceholderText(/Tell us what's on your mind/i), {
      target: { value: "Great app!" },
    });
    expect(screen.getByRole("button", { name: /^Send$/i })).not.toBeDisabled();
  });

  it("calls submitFeedback with category and message on submit", async () => {
    render(<FeedbackWidget />);
    fireEvent.click(screen.getByRole("button", { name: /Feedback/i }));
    fireEvent.change(screen.getByPlaceholderText(/Tell us what's on your mind/i), {
      target: { value: "Great app!" },
    });
    fireEvent.click(screen.getByRole("button", { name: /^Send$/i }));
    await waitFor(() =>
      expect(mockSubmitFeedback).toHaveBeenCalledWith("feedback", "Great app!")
    );
  });

  it("shows success state after successful submit", async () => {
    render(<FeedbackWidget />);
    fireEvent.click(screen.getByRole("button", { name: /Feedback/i }));
    fireEvent.change(screen.getByPlaceholderText(/Tell us what's on your mind/i), {
      target: { value: "Nice!" },
    });
    fireEvent.click(screen.getByRole("button", { name: /^Send$/i }));
    await waitFor(() =>
      expect(screen.getByText(/Thanks for the feedback/i)).toBeInTheDocument()
    );
  });

  it("shows error message when submit fails", async () => {
    mockSubmitFeedback.mockRejectedValue(new Error("Network error"));
    render(<FeedbackWidget />);
    fireEvent.click(screen.getByRole("button", { name: /Feedback/i }));
    fireEvent.change(screen.getByPlaceholderText(/Tell us what's on your mind/i), {
      target: { value: "Bug report" },
    });
    fireEvent.click(screen.getByRole("button", { name: /^Send$/i }));
    await waitFor(() =>
      expect(screen.getByText(/Something went wrong/i)).toBeInTheDocument()
    );
  });

  it("does not call submitFeedback when message is only whitespace", () => {
    render(<FeedbackWidget />);
    fireEvent.click(screen.getByRole("button", { name: /Feedback/i }));
    fireEvent.change(screen.getByPlaceholderText(/Tell us what's on your mind/i), {
      target: { value: "   " },
    });
    // Send button should still be disabled for whitespace-only input
    expect(screen.getByRole("button", { name: /^Send$/i })).toBeDisabled();
  });
});
