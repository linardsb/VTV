/**
 * Shared event subtype detection and color mapping.
 * Detects vacation, sick day, training, and shift from event titles (lv + en keywords).
 */

const VACATION_KEYWORDS = ["atvaļinājums", "vacation", "leave"];
const SICK_KEYWORDS = ["slimības", "sick"];
const TRAINING_KEYWORDS = ["apmācība", "training"];

export type EventSubtype = "vacation" | "sick" | "training" | "shift";

export function detectEventSubtype(title: string, category: string): EventSubtype {
  const lower = title.toLowerCase();
  if (VACATION_KEYWORDS.some((kw) => lower.includes(kw))) return "vacation";
  if (SICK_KEYWORDS.some((kw) => lower.includes(kw))) return "sick";
  if (TRAINING_KEYWORDS.some((kw) => lower.includes(kw))) return "training";
  if (category === "driver-shift") return "shift";
  return "shift";
}

/** Border-left + background styles for calendar event cards */
export const subtypeCardStyles: Record<EventSubtype, string> = {
  vacation: "bg-event-vacation/10 border-l-2 border-l-event-vacation",
  sick: "bg-event-sick/10 border-l-2 border-l-event-sick",
  training: "bg-event-training/10 border-l-2 border-l-event-training",
  shift: "bg-event-shift/10 border-l-2 border-l-event-shift",
};

/** Category-based card styles (non-driver events) */
export const categoryCardStyles: Record<string, string> = {
  maintenance: "bg-category-maintenance/10 border-l-2 border-l-category-maintenance",
  "route-change": "bg-category-route-change/10 border-l-2 border-l-category-route-change",
  "driver-shift": "bg-category-driver-shift/10 border-l-2 border-l-category-driver-shift",
  "service-alert": "bg-category-service-alert/10 border-l-2 border-l-category-service-alert",
};

/** Dot color for month/three-month views */
export const subtypeDotColors: Record<EventSubtype, string> = {
  vacation: "bg-event-vacation",
  sick: "bg-event-sick",
  training: "bg-event-training",
  shift: "bg-event-shift",
};

/** Category-based dot colors (non-driver events) */
export const categoryDotColors: Record<string, string> = {
  maintenance: "bg-category-maintenance",
  "route-change": "bg-category-route-change",
  "driver-shift": "bg-category-driver-shift",
  "service-alert": "bg-category-service-alert",
};

/** Get card style for any event (detects subtype for driver events) */
export function getEventCardStyle(title: string, category: string): string {
  if (category === "driver-shift" || category === "maintenance") {
    const subtype = detectEventSubtype(title, category);
    if (subtype !== "shift" || category === "driver-shift") {
      return subtypeCardStyles[subtype];
    }
  }
  return categoryCardStyles[category] ?? categoryCardStyles["driver-shift"];
}

/** Get dot color for any event (detects subtype for driver events) */
export function getEventDotColor(title: string, category: string): string {
  if (category === "driver-shift" || category === "maintenance") {
    const subtype = detectEventSubtype(title, category);
    if (subtype !== "shift" || category === "driver-shift") {
      return subtypeDotColors[subtype];
    }
  }
  return categoryDotColors[category] ?? categoryDotColors["driver-shift"];
}
