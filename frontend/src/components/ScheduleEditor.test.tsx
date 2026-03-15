import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import ScheduleEditor, { DEFAULT_SLOTS } from "./ScheduleEditor";
import type { ScheduleSlot } from "@/lib/api";

function makeSchedule(overrides: Partial<ScheduleSlot>[] = []): ScheduleSlot[] {
  const days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"];
  return days.map((day, i) => ({
    day,
    workout_type: DEFAULT_SLOTS[day]?.workout_type ?? null,
    body_focus: DEFAULT_SLOTS[day]?.body_focus ?? null,
    difficulty: "any",
    duration_min: DEFAULT_SLOTS[day]?.duration_min ?? null,
    duration_max: DEFAULT_SLOTS[day]?.duration_max ?? null,
    ...overrides[i],
  }));
}

describe("ScheduleEditor - rendering", () => {
  it("renders all 7 days", () => {
    const onChange = vi.fn();
    render(<ScheduleEditor schedule={makeSchedule()} onScheduleChange={onChange} />);
    const days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"];
    for (const day of days) {
      expect(screen.getByText(new RegExp(day, "i"))).toBeInTheDocument();
    }
  });

  it("shows 'Rest' badge for rest days (workout_type null)", () => {
    const schedule = makeSchedule();
    // sunday defaults to rest
    const onChange = vi.fn();
    render(<ScheduleEditor schedule={schedule} onScheduleChange={onChange} />);
    // Sunday row should show "Rest" button (active rest state)
    const restButtons = screen.getAllByRole("button", { name: /^Rest$/i });
    expect(restButtons.length).toBeGreaterThan(0);
  });

  it("shows 'Set rest' button for active workout days", () => {
    const onChange = vi.fn();
    render(<ScheduleEditor schedule={makeSchedule()} onScheduleChange={onChange} />);
    const setRestButtons = screen.getAllByRole("button", { name: /Set rest/i });
    // 6 active days (mon–sat), 1 rest day (sun)
    expect(setRestButtons).toHaveLength(6);
  });
});

describe("ScheduleEditor - toggle rest", () => {
  it("calls onScheduleChange with null workout_type when 'Set rest' is clicked", () => {
    const onChange = vi.fn();
    render(<ScheduleEditor schedule={makeSchedule()} onScheduleChange={onChange} />);
    const [firstSetRest] = screen.getAllByRole("button", { name: /Set rest/i });
    fireEvent.click(firstSetRest);
    const updated: ScheduleSlot[] = onChange.mock.calls[0][0];
    const monday = updated.find((s) => s.day === "monday");
    expect(monday?.workout_type).toBeNull();
    expect(monday?.body_focus).toBeNull();
    expect(monday?.duration_min).toBeNull();
    expect(monday?.duration_max).toBeNull();
  });

  it("restores default values when 'Rest' is clicked to make a day active again", () => {
    // Start with all rest days
    const allRest = makeSchedule().map((s) => ({
      ...s,
      workout_type: null,
      body_focus: null,
      duration_min: null,
      duration_max: null,
    }));
    const onChange = vi.fn();
    render(<ScheduleEditor schedule={allRest} onScheduleChange={onChange} />);
    const [firstRest] = screen.getAllByRole("button", { name: /^Rest$/i });
    fireEvent.click(firstRest);
    const updated: ScheduleSlot[] = onChange.mock.calls[0][0];
    const monday = updated.find((s) => s.day === "monday");
    expect(monday?.workout_type).toBe(DEFAULT_SLOTS["monday"].workout_type);
    expect(monday?.body_focus).toBe(DEFAULT_SLOTS["monday"].body_focus);
    expect(monday?.duration_min).toBe(DEFAULT_SLOTS["monday"].duration_min);
    expect(monday?.duration_max).toBe(DEFAULT_SLOTS["monday"].duration_max);
  });
});

describe("ScheduleEditor - dropdowns", () => {
  it("calls onScheduleChange with updated workout_type when select changes", () => {
    const onChange = vi.fn();
    render(<ScheduleEditor schedule={makeSchedule()} onScheduleChange={onChange} />);
    // First workout_type select is for monday
    const [firstTypeSelect] = screen.getAllByDisplayValue("strength");
    fireEvent.change(firstTypeSelect, { target: { value: "cardio" } });
    const updated: ScheduleSlot[] = onChange.mock.calls[0][0];
    expect(updated.find((s) => s.day === "monday")?.workout_type).toBe("cardio");
  });

  it("calls onScheduleChange with updated body_focus when select changes", () => {
    const onChange = vi.fn();
    render(<ScheduleEditor schedule={makeSchedule()} onScheduleChange={onChange} />);
    const [firstFocusSelect] = screen.getAllByDisplayValue("upper");
    fireEvent.change(firstFocusSelect, { target: { value: "core" } });
    const updated: ScheduleSlot[] = onChange.mock.calls[0][0];
    expect(updated.find((s) => s.day === "monday")?.body_focus).toBe("core");
  });

  it("calls onScheduleChange with null body_focus when 'any focus' option selected", () => {
    const onChange = vi.fn();
    render(<ScheduleEditor schedule={makeSchedule()} onScheduleChange={onChange} />);
    const [firstFocusSelect] = screen.getAllByDisplayValue("upper");
    fireEvent.change(firstFocusSelect, { target: { value: "" } });
    const updated: ScheduleSlot[] = onChange.mock.calls[0][0];
    expect(updated.find((s) => s.day === "monday")?.body_focus).toBeNull();
  });
});

describe("ScheduleEditor - duration inputs", () => {
  it("calls onScheduleChange with updated duration_min", () => {
    const onChange = vi.fn();
    render(<ScheduleEditor schedule={makeSchedule()} onScheduleChange={onChange} />);
    // Monday duration_min defaults to 30
    const [firstMinInput] = screen.getAllByDisplayValue("30");
    fireEvent.change(firstMinInput, { target: { value: "20" } });
    const updated: ScheduleSlot[] = onChange.mock.calls[0][0];
    expect(updated.find((s) => s.day === "monday")?.duration_min).toBe(20);
  });

  it("calls onScheduleChange with updated duration_max", () => {
    const onChange = vi.fn();
    render(<ScheduleEditor schedule={makeSchedule()} onScheduleChange={onChange} />);
    // Monday duration_max defaults to 45
    const [firstMaxInput] = screen.getAllByDisplayValue("45");
    fireEvent.change(firstMaxInput, { target: { value: "60" } });
    const updated: ScheduleSlot[] = onChange.mock.calls[0][0];
    expect(updated.find((s) => s.day === "monday")?.duration_max).toBe(60);
  });
});
