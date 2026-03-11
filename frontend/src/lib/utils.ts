export const DAY_LABELS: Record<string, string> = {
  monday: "Mon",
  tuesday: "Tue",
  wednesday: "Wed",
  thursday: "Thu",
  friday: "Fri",
  saturday: "Sat",
  sunday: "Sun",
};

export function formatDuration(min: number | null, max: number | null): string {
  if (min === null || max === null) return "";
  if (min === max) return `${min} min`;
  return `${min}–${max} min`;
}
