import { describe, it, expect } from "vitest";
import { buildSchedule } from "./scheduleTemplates";

describe("buildSchedule", () => {
  // ─── Difficulty mapping ────────────────────────────────────────────────────

  it("senior profile → beginner difficulty", () => {
    const slots = buildSchedule("senior", "Stay active & healthy", 3, "short");
    const activeDays = slots.filter((s) => s.workout_type !== null);
    expect(activeDays.every((s) => s.difficulty === "beginner")).toBe(true);
  });

  it("beginner profile → beginner difficulty", () => {
    const slots = buildSchedule("beginner", "Build a habit", 3, "short");
    const activeDays = slots.filter((s) => s.workout_type !== null);
    expect(activeDays.every((s) => s.difficulty === "beginner")).toBe(true);
  });

  it("adult profile → intermediate difficulty", () => {
    const slots = buildSchedule("adult", "Build muscle", 4, "medium");
    const activeDays = slots.filter((s) => s.workout_type !== null);
    expect(activeDays.every((s) => s.difficulty === "intermediate")).toBe(true);
  });

  it("athlete profile → advanced difficulty", () => {
    const slots = buildSchedule("athlete", "Strength & hypertrophy", 5, "long");
    const activeDays = slots.filter((s) => s.workout_type !== null);
    expect(activeDays.every((s) => s.difficulty === "advanced")).toBe(true);
  });

  // ─── Duration mapping ──────────────────────────────────────────────────────

  it("short duration → 15–20 min", () => {
    const slots = buildSchedule("beginner", "Build a habit", 3, "short");
    const active = slots.filter((s) => s.workout_type !== null);
    expect(active.every((s) => s.duration_min === 15 && s.duration_max === 20)).toBe(true);
  });

  it("medium duration → 25–35 min", () => {
    const slots = buildSchedule("adult", "Stay consistent", 4, "medium");
    const active = slots.filter((s) => s.workout_type !== null);
    expect(active.every((s) => s.duration_min === 25 && s.duration_max === 35)).toBe(true);
  });

  it("long duration → 40–60 min", () => {
    const slots = buildSchedule("athlete", "Endurance", 5, "long");
    const active = slots.filter((s) => s.workout_type !== null);
    expect(active.every((s) => s.duration_min === 40 && s.duration_max === 60)).toBe(true);
  });

  it("any duration → 20–60 min", () => {
    const slots = buildSchedule("adult", "Stay consistent", 3, "any");
    const active = slots.filter((s) => s.workout_type !== null);
    expect(active.every((s) => s.duration_min === 20 && s.duration_max === 60)).toBe(true);
  });

  // ─── Day counts ────────────────────────────────────────────────────────────

  it("always returns 7 slots", () => {
    expect(buildSchedule("adult", "Build muscle", 4, "medium")).toHaveLength(7);
  });

  it("2 training days → 2 active, 5 rest", () => {
    const slots = buildSchedule("beginner", "Build a habit", 2, "short");
    expect(slots.filter((s) => s.workout_type !== null)).toHaveLength(2);
    expect(slots.filter((s) => s.workout_type === null)).toHaveLength(5);
  });

  it("3 training days → 3 active, 4 rest", () => {
    const slots = buildSchedule("senior", "Stay active & healthy", 3, "short");
    expect(slots.filter((s) => s.workout_type !== null)).toHaveLength(3);
    expect(slots.filter((s) => s.workout_type === null)).toHaveLength(4);
  });

  it("4 training days → 4 active, 3 rest", () => {
    const slots = buildSchedule("adult", "Lose fat", 4, "medium");
    expect(slots.filter((s) => s.workout_type !== null)).toHaveLength(4);
  });

  it("5 training days → 5 active, 2 rest", () => {
    const slots = buildSchedule("athlete", "Endurance", 5, "long");
    expect(slots.filter((s) => s.workout_type !== null)).toHaveLength(5);
  });

  it("6 training days → 6 active, 1 rest", () => {
    const slots = buildSchedule("adult", "Build muscle", 6, "long");
    expect(slots.filter((s) => s.workout_type !== null)).toHaveLength(6);
  });

  // ─── Rest days have null fields ────────────────────────────────────────────

  it("rest days have null workout_type, body_focus, duration", () => {
    const slots = buildSchedule("senior", "Stay active & healthy", 3, "short");
    const rest = slots.filter((s) => s.workout_type === null);
    rest.forEach((s) => {
      expect(s.body_focus).toBeNull();
      expect(s.duration_min).toBeNull();
      expect(s.duration_max).toBeNull();
    });
  });

  // ─── Profile-specific slot types ──────────────────────────────────────────

  it("senior profile uses mobility, cardio, strength slots", () => {
    const slots = buildSchedule("senior", "Stay active & healthy", 3, "short");
    const types = slots.filter((s) => s.workout_type !== null).map((s) => s.workout_type);
    expect(types).toContain("mobility");
    expect(types).toContain("cardio");
    expect(types).toContain("strength");
  });

  it("beginner profile includes cardio and strength", () => {
    const slots = buildSchedule("beginner", "Build a habit", 3, "short");
    const types = slots.filter((s) => s.workout_type !== null).map((s) => s.workout_type);
    expect(types).toContain("cardio");
    expect(types).toContain("strength");
  });

  it("adult Build muscle → includes strength slots", () => {
    const slots = buildSchedule("adult", "Build muscle", 4, "medium");
    const types = slots.filter((s) => s.workout_type !== null).map((s) => s.workout_type);
    expect(types.filter((t) => t === "strength").length).toBeGreaterThanOrEqual(2);
  });

  it("adult Lose fat → includes hiit and cardio", () => {
    const slots = buildSchedule("adult", "Lose fat", 4, "medium");
    const types = slots.filter((s) => s.workout_type !== null).map((s) => s.workout_type);
    expect(types).toContain("hiit");
    expect(types).toContain("cardio");
  });

  it("adult Improve cardio → includes hiit and cardio", () => {
    const slots = buildSchedule("adult", "Improve cardio", 4, "medium");
    const types = slots.filter((s) => s.workout_type !== null).map((s) => s.workout_type);
    expect(types).toContain("hiit");
    expect(types).toContain("cardio");
  });

  it("athlete Endurance → includes strength and hiit", () => {
    const slots = buildSchedule("athlete", "Endurance", 5, "long");
    const types = slots.filter((s) => s.workout_type !== null).map((s) => s.workout_type);
    expect(types).toContain("strength");
    expect(types).toContain("hiit");
  });

  it("athlete Strength & hypertrophy → strength-heavy", () => {
    const slots = buildSchedule("athlete", "Strength & hypertrophy", 5, "long");
    const types = slots.filter((s) => s.workout_type !== null).map((s) => s.workout_type);
    expect(types.filter((t) => t === "strength").length).toBeGreaterThanOrEqual(3);
  });

  it("athlete Cut weight → includes hiit and cardio", () => {
    const slots = buildSchedule("athlete", "Cut weight", 4, "long");
    const types = slots.filter((s) => s.workout_type !== null).map((s) => s.workout_type);
    expect(types).toContain("hiit");
    expect(types).toContain("cardio");
  });

  // ─── Every slot has all required fields ───────────────────────────────────

  it("all slots have a day name", () => {
    const slots = buildSchedule("adult", "Build muscle", 4, "medium");
    const days = slots.map((s) => s.day);
    expect(days).toEqual(["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]);
  });
});
