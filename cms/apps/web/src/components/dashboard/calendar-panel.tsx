"use client";

import { useMemo } from "react";
import { CalendarGrid } from "./calendar-grid";
import { useCalendarEvents } from "@/hooks/use-calendar-events";

/**
 * Client-side wrapper that fetches real operational events from the API
 * and passes them to the CalendarGrid component.
 */
export function CalendarPanel() {
  // Fetch events for a wide window (3 months back, 3 months forward)
  const dateRange = useMemo(() => {
    const now = new Date();
    const start = new Date(now);
    start.setMonth(start.getMonth() - 3);
    const end = new Date(now);
    end.setMonth(end.getMonth() + 3);
    return { start, end };
  }, []);

  const { events } = useCalendarEvents(dateRange.start, dateRange.end);

  return <CalendarGrid events={events} />;
}
