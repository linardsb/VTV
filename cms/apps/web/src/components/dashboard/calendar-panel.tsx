"use client";

import { useEffect, useMemo, type RefObject } from "react";
import { CalendarGrid } from "./calendar-grid";
import { useCalendarEvents } from "@/hooks/use-calendar-events";
import type { CalendarEvent } from "@/types/dashboard";

interface CalendarPanelProps {
  onDayDrop?: (date: Date, driverJson: string) => void;
  refetchRef?: RefObject<(() => Promise<void>) | null>;
  onEventClick?: (event: CalendarEvent) => void;
}

/**
 * Client-side wrapper that fetches real operational events from the API
 * and passes them to the CalendarGrid component.
 */
export function CalendarPanel({ onDayDrop, refetchRef, onEventClick }: CalendarPanelProps) {
  // Fetch events for a wide window (3 months back, 3 months forward)
  const dateRange = useMemo(() => {
    const now = new Date();
    const start = new Date(now);
    start.setMonth(start.getMonth() - 3);
    const end = new Date(now);
    end.setMonth(end.getMonth() + 3);
    return { start, end };
  }, []);

  const { events, refetch } = useCalendarEvents(dateRange.start, dateRange.end);

  // Expose refetch to parent via ref (not a state update — safe in useEffect)
  useEffect(() => {
    if (refetchRef) {
      refetchRef.current = refetch;
    }
  }, [refetch, refetchRef]);

  return <CalendarGrid events={events} onDayDrop={onDayDrop} onEventClick={onEventClick} />;
}
