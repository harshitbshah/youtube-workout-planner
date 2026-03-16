import { type LifeStage } from "./scheduleTemplates";

// ─── Equipment ────────────────────────────────────────────────────────────────

export const EQUIPMENT_OPTIONS = [
  { id: "mat",              label: "Yoga / exercise mat" },
  { id: "dumbbells",        label: "Dumbbells" },
  { id: "resistance_bands", label: "Resistance bands" },
  { id: "kettlebell",       label: "Kettlebell" },
  { id: "barbell",          label: "Barbell" },
  { id: "pull_up_bar",      label: "Pull-up bar" },
  { id: "reformer",         label: "Pilates reformer" },
] as const;

// ─── Goals ────────────────────────────────────────────────────────────────────

export type GoalGroup = { group: string; options: string[] };

/**
 * Goals organised into display groups, used by the onboarding wizard.
 * The flat list (used by Settings) can be derived: GOALS[stage].flatMap(g => g.options)
 */
export const GOALS: Record<LifeStage, GoalGroup[]> = {
  beginner: [
    { group: "General",     options: ["Build a habit", "Lose weight", "Feel more energetic"] },
    { group: "Mind & Body", options: ["Yoga & mindfulness", "Dance fitness"] },
  ],
  adult: [
    { group: "Strength & Performance", options: ["Build muscle", "Stay consistent"] },
    { group: "Cardio & Dance",         options: ["Lose fat", "Improve cardio", "Dance fitness"] },
    { group: "Mind & Body",            options: ["Yoga & mindfulness", "Pilates & core"] },
  ],
  senior: [
    { group: "General",     options: ["Stay active & healthy", "Build strength safely"] },
    { group: "Mind & Body", options: ["Improve flexibility", "Yoga & mindfulness", "Pilates & core"] },
    { group: "Fun",         options: ["Dance fitness"] },
  ],
  athlete: [
    { group: "Strength & Performance", options: ["Strength & hypertrophy", "Endurance", "Athletic performance", "Cut weight"] },
    { group: "Recovery & Mobility",    options: ["Yoga & mindfulness", "Pilates & core"] },
  ],
};
