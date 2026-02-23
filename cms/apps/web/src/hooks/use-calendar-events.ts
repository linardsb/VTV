"use client";

import { useState, useEffect, useCallback } from "react";
import type { CalendarEvent } from "@/types/dashboard";
import type { OperationalEvent } from "@/types/event";
import { fetchEvents } from "@/lib/events-client";

function toCalendarEvent(event: OperationalEvent): CalendarEvent {
  return {
    id: String(event.id),
    title: event.title,
    start: new Date(event.start_datetime),
    end: new Date(event.end_datetime),
    priority: event.priority,
    category: event.category,
    description: event.description ?? undefined,
  };
}

/**
 * Hook to fetch operational events from the API and transform them
 * into CalendarEvent[] for the calendar grid.
 *
 * Polls every 60 seconds. Falls back to empty array on error.
 */
export function useCalendarEvents(startDate: Date, endDate: Date) {
  const [events, setEvents] = useState<CalendarEvent[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      const result = await fetchEvents({
        page_size: 200,
        start_date: startDate.toISOString(),
        end_date: endDate.toISOString(),
      });
      setEvents(result.items.map(toCalendarEvent));
    } catch {
      // Silently fall back to empty on error — dashboard stays functional
    } finally {
      setIsLoading(false);
    }
  }, [startDate, endDate]);

  useEffect(() => {
    void load();
    const interval = setInterval(() => void load(), 60_000);
    return () => clearInterval(interval);
  }, [load]);

  return { events, isLoading };
}
