"use client";

import { type ScheduleSlot } from "@/lib/api";

const DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"];

const DEFAULT_SLOTS: Record<string, Partial<ScheduleSlot>> = {
  monday:    { workout_type: "strength", body_focus: "upper", duration_min: 30, duration_max: 45 },
  tuesday:   { workout_type: "hiit",     body_focus: "full",  duration_min: 30, duration_max: 45 },
  wednesday: { workout_type: "strength", body_focus: "lower", duration_min: 30, duration_max: 45 },
  thursday:  { workout_type: "hiit",     body_focus: "core",  duration_min: 15, duration_max: 45 },
  friday:    { workout_type: "strength", body_focus: "full",  duration_min: 30, duration_max: 45 },
  saturday:  { workout_type: "cardio",   body_focus: "full",  duration_min: 30, duration_max: 45 },
  sunday:    { workout_type: null,       body_focus: null,    duration_min: null, duration_max: null },
};

const WORKOUT_TYPES = ["strength", "hiit", "cardio", "mobility", "yoga", "pilates", "dance"];
const BODY_FOCUS_OPTIONS = ["full", "upper", "lower", "core"];

const BODY_FOCUS_FOR_TYPE: Record<string, string[]> = {
  strength: ["full", "upper", "lower", "core"],
  hiit:     ["full", "core"],
  cardio:   ["full"],
  mobility: ["full", "upper", "lower", "core"],
  yoga:     ["full", "upper", "lower", "core"],
  pilates:  ["full", "core", "lower"],
  dance:    ["full"],
};
const DIFFICULTY_OPTIONS = ["any", "beginner", "intermediate", "advanced"];

interface Props {
  schedule: ScheduleSlot[];
  onScheduleChange: (schedule: ScheduleSlot[]) => void;
}

export default function ScheduleEditor({ schedule, onScheduleChange }: Props) {
  function updateDay(day: string, patch: Partial<ScheduleSlot>) {
    onScheduleChange(schedule.map((s) => (s.day === day ? { ...s, ...patch } : s)));
  }

  function handleWorkoutTypeChange(day: string, newType: string) {
    const slot = schedule.find((s) => s.day === day);
    const allowed = BODY_FOCUS_FOR_TYPE[newType] ?? BODY_FOCUS_OPTIONS;
    const currentFocus = slot?.body_focus ?? "";
    const needsReset = currentFocus && !allowed.includes(currentFocus);
    updateDay(day, {
      workout_type: newType,
      ...(needsReset ? { body_focus: null } : {}),
    });
  }

  function toggleRest(day: string, makeRest: boolean) {
    if (makeRest) {
      updateDay(day, { workout_type: null, body_focus: null, duration_min: null, duration_max: null });
    } else {
      updateDay(day, {
        workout_type: DEFAULT_SLOTS[day]?.workout_type ?? "strength",
        body_focus: DEFAULT_SLOTS[day]?.body_focus ?? "full",
        duration_min: DEFAULT_SLOTS[day]?.duration_min ?? 30,
        duration_max: DEFAULT_SLOTS[day]?.duration_max ?? 45,
      });
    }
  }

  return (
    <div className="space-y-2">
      {DAYS.map((day) => {
        const slot = schedule.find((s) => s.day === day);
        if (!slot) return null;
        const isRest = slot.workout_type === null;

        return (
          <div
            key={day}
            className={`rounded-lg border px-4 py-3 transition-colors ${
              isRest ? "border-zinc-200 dark:border-zinc-800 bg-zinc-50/50 dark:bg-zinc-900/50" : "border-zinc-200 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-900"
            }`}
          >
            <div className="flex items-center gap-4 flex-wrap">
              <span className="w-24 text-sm font-medium text-zinc-900 dark:text-white capitalize shrink-0">{day}</span>

              <button
                onClick={() => toggleRest(day, !isRest)}
                className={`text-xs px-2.5 py-1 rounded-full border transition shrink-0 ${
                  isRest
                    ? "border-zinc-300 dark:border-zinc-600 text-zinc-600 dark:text-zinc-400 bg-zinc-100 dark:bg-zinc-800"
                    : "border-zinc-200 dark:border-zinc-700 text-zinc-500 hover:border-zinc-400 dark:hover:border-zinc-500 hover:text-zinc-600 dark:hover:text-zinc-400"
                }`}
              >
                {isRest ? "Rest" : "Set rest"}
              </button>

              {!isRest && (
                <div className="flex flex-wrap gap-2 flex-1">
                  <select
                    value={slot.workout_type ?? ""}
                    onChange={(e) => handleWorkoutTypeChange(day, e.target.value)}
                    className="rounded-md bg-white dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 px-2 py-1 text-xs text-zinc-900 dark:text-white focus:outline-none focus:border-zinc-500"
                  >
                    {WORKOUT_TYPES.map((t) => (
                      <option key={t} value={t}>{t}</option>
                    ))}
                  </select>

                  <select
                    value={slot.body_focus ?? ""}
                    onChange={(e) => updateDay(day, { body_focus: e.target.value || null })}
                    className="rounded-md bg-white dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 px-2 py-1 text-xs text-zinc-900 dark:text-white focus:outline-none focus:border-zinc-500"
                  >
                    <option value="">any focus</option>
                    {(BODY_FOCUS_FOR_TYPE[slot.workout_type ?? ""] ?? BODY_FOCUS_OPTIONS).map((f) => (
                      <option key={f} value={f}>{f}</option>
                    ))}
                  </select>

                  <select
                    value={slot.difficulty}
                    onChange={(e) => updateDay(day, { difficulty: e.target.value })}
                    className="rounded-md bg-white dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 px-2 py-1 text-xs text-zinc-900 dark:text-white focus:outline-none focus:border-zinc-500"
                  >
                    {DIFFICULTY_OPTIONS.map((d) => (
                      <option key={d} value={d}>{d}</option>
                    ))}
                  </select>

                  <div className="flex items-center gap-1 text-xs text-zinc-600 dark:text-zinc-400">
                    <input
                      type="number"
                      min={5}
                      max={120}
                      value={slot.duration_min ?? ""}
                      onChange={(e) => updateDay(day, { duration_min: Number(e.target.value) || null })}
                      className="w-12 rounded-md bg-white dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 px-2 py-1 text-xs text-zinc-900 dark:text-white text-center focus:outline-none focus:border-zinc-500"
                    />
                    <span>–</span>
                    <input
                      type="number"
                      min={5}
                      max={120}
                      value={slot.duration_max ?? ""}
                      onChange={(e) => updateDay(day, { duration_max: Number(e.target.value) || null })}
                      className="w-12 rounded-md bg-white dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 px-2 py-1 text-xs text-zinc-900 dark:text-white text-center focus:outline-none focus:border-zinc-500"
                    />
                    <span>min</span>
                  </div>
                </div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

export { DEFAULT_SLOTS };
