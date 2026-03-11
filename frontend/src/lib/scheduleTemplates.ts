import type { ScheduleSlot } from "./api";

export type LifeStage = "beginner" | "adult" | "senior" | "athlete";
export type SessionLength = "short" | "medium" | "long" | "any";

const DURATION_MAP: Record<SessionLength, { min: number; max: number }> = {
  short:  { min: 15, max: 20 },
  medium: { min: 25, max: 35 },
  long:   { min: 40, max: 60 },
  any:    { min: 20, max: 60 },
};

const DIFFICULTY_MAP: Record<LifeStage, string> = {
  beginner: "beginner",
  adult:    "intermediate",
  senior:   "beginner",
  athlete:  "advanced",
};

const ALL_DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"];

type SlotType = { workout_type: string; body_focus: string };

// Returns indices (0=Mon..6=Sun) of active training days
function getActiveDays(count: number): number[] {
  switch (count) {
    case 2: return [0, 3];             // Mon, Thu
    case 3: return [0, 2, 4];         // Mon, Wed, Fri
    case 4: return [0, 1, 3, 4];      // Mon, Tue, Thu, Fri
    case 5: return [0, 1, 2, 4, 5];   // Mon, Tue, Wed, Fri, Sat
    case 6: return [0, 1, 2, 3, 4, 5]; // Mon–Sat
    default: return [0, 2, 4];
  }
}

function makeSlots(
  activeDays: number[],
  slotTypes: SlotType[],
  difficulty: string,
  duration: { min: number; max: number },
): ScheduleSlot[] {
  return ALL_DAYS.map((day, i) => {
    const activeIndex = activeDays.indexOf(i);
    if (activeIndex === -1) {
      return { day, workout_type: null, body_focus: null, duration_min: null, duration_max: null, difficulty: "any" };
    }
    const slot = slotTypes[activeIndex % slotTypes.length];
    return {
      day,
      workout_type: slot.workout_type,
      body_focus: slot.body_focus,
      duration_min: duration.min,
      duration_max: duration.max,
      difficulty,
    };
  });
}

export function buildSchedule(
  profile: LifeStage,
  goal: string,
  days: number,
  duration: SessionLength,
): ScheduleSlot[] {
  const dur = DURATION_MAP[duration];
  const diff = DIFFICULTY_MAP[profile];
  const activeDays = getActiveDays(days);

  if (profile === "senior") {
    return makeSlots(activeDays, [
      { workout_type: "mobility", body_focus: "full" },
      { workout_type: "cardio",   body_focus: "full" },
      { workout_type: "strength", body_focus: "full" },
    ], diff, dur);
  }

  if (profile === "beginner") {
    return makeSlots(activeDays, [
      { workout_type: "cardio",   body_focus: "full" },
      { workout_type: "strength", body_focus: "full" },
      { workout_type: "mobility", body_focus: "full" },
    ], diff, dur);
  }

  if (profile === "adult") {
    if (goal === "Build muscle") {
      return makeSlots(activeDays, [
        { workout_type: "strength", body_focus: "upper" },
        { workout_type: "hiit",     body_focus: "full" },
        { workout_type: "strength", body_focus: "lower" },
        { workout_type: "strength", body_focus: "full" },
        { workout_type: "cardio",   body_focus: "full" },
        { workout_type: "strength", body_focus: "full" },
      ].slice(0, activeDays.length), diff, dur);
    }
    if (goal === "Lose fat" || goal === "Improve cardio") {
      return makeSlots(activeDays, [
        { workout_type: "hiit",   body_focus: "full" },
        { workout_type: "cardio", body_focus: "full" },
        { workout_type: "hiit",   body_focus: "core" },
        { workout_type: "cardio", body_focus: "full" },
        { workout_type: "hiit",   body_focus: "full" },
        { workout_type: "cardio", body_focus: "full" },
      ].slice(0, activeDays.length), diff, dur);
    }
    // Stay consistent / Feel more energetic
    return makeSlots(activeDays, [
      { workout_type: "cardio",   body_focus: "full" },
      { workout_type: "strength", body_focus: "full" },
      { workout_type: "mobility", body_focus: "full" },
      { workout_type: "cardio",   body_focus: "full" },
      { workout_type: "hiit",     body_focus: "full" },
      { workout_type: "mobility", body_focus: "full" },
    ].slice(0, activeDays.length), diff, dur);
  }

  if (profile === "athlete") {
    if (goal === "Endurance" || goal === "Athletic performance") {
      return makeSlots(activeDays, [
        { workout_type: "strength", body_focus: "upper" },
        { workout_type: "hiit",     body_focus: "full" },
        { workout_type: "strength", body_focus: "lower" },
        { workout_type: "strength", body_focus: "full" },
        { workout_type: "hiit",     body_focus: "core" },
        { workout_type: "cardio",   body_focus: "full" },
      ].slice(0, activeDays.length), diff, dur);
    }
    if (goal === "Strength & hypertrophy") {
      return makeSlots(activeDays, [
        { workout_type: "strength", body_focus: "upper" },
        { workout_type: "hiit",     body_focus: "full" },
        { workout_type: "strength", body_focus: "lower" },
        { workout_type: "strength", body_focus: "full" },
        { workout_type: "cardio",   body_focus: "full" },
        { workout_type: "strength", body_focus: "full" },
      ].slice(0, activeDays.length), diff, dur);
    }
    // Cut weight
    return makeSlots(activeDays, [
      { workout_type: "hiit",   body_focus: "full" },
      { workout_type: "cardio", body_focus: "full" },
      { workout_type: "hiit",   body_focus: "core" },
      { workout_type: "cardio", body_focus: "full" },
      { workout_type: "hiit",   body_focus: "full" },
      { workout_type: "cardio", body_focus: "full" },
    ].slice(0, activeDays.length), diff, dur);
  }

  // Fallback
  return makeSlots(activeDays, [
    { workout_type: "cardio",   body_focus: "full" },
    { workout_type: "strength", body_focus: "full" },
    { workout_type: "mobility", body_focus: "full" },
  ], diff, dur);
}
