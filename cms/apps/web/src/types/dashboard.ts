import type { EventGoals } from "./event";

export type CalendarViewMode = "year" | "3month" | "month" | "week";

export type EventPriority = "high" | "medium" | "low";

export type EventCategory =
  | "maintenance"
  | "route-change"
  | "driver-shift"
  | "service-alert";

export interface CalendarEvent {
  id: string;
  title: string;
  start: Date;
  end: Date;
  priority: EventPriority;
  category: EventCategory;
  description?: string;
  goals?: EventGoals | null;
  driver_id?: number | null;
}

export interface MetricData {
  title: string;
  value: string;
  delta?: string;
  deltaType?: "positive" | "negative" | "neutral";
  subtitle: string;
}
