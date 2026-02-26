"use client";

import { useMemo, useCallback } from "react";
import useSWR from "swr";
import { useSession } from "next-auth/react";
import type { CalendarEvent } from "@/types/dashboard";
import type { OperationalEvent } from "@/types/event";
import { fetchEvents } from "@/lib/events-sdk";

function toCalendarEvent(event: OperationalEvent): CalendarEvent {
  return {
    id: String(event.id),
    title: event.title,
    start: new Date(event.start_datetime),
    end: new Date(event.end_datetime),
    priority: event.priority,
    category: event.category,
    description: event.description ?? undefined,
    goals: event.goals ?? undefined,
  };
}

interface EventsApiResult {
  items: OperationalEvent[];
  total: number;
}

/**
 * Hook to fetch operational events from the API and transform them
 * into CalendarEvent[] for the calendar grid.
 *
 * Uses SWR with 60s refresh interval. Falls back to empty array on error.
 */
export function useCalendarEvents(startDate: Date, endDate: Date) {
  const { status } = useSession();

  // Stable SWR key based on date range; null disables fetching when unauthenticated
  const swrKey =
    status === "authenticated"
      ? `events:${startDate.toISOString()}:${endDate.toISOString()}`
      : null;

  const { data, isLoading, mutate } = useSWR<EventsApiResult>(
    swrKey,
    async () =>
      fetchEvents({
        page_size: 200,
        start_date: startDate.toISOString(),
        end_date: endDate.toISOString(),
      }),
    {
      refreshInterval: 60_000,
      fallbackData: { items: [], total: 0 },
    },
  );

  const events = useMemo(
    () => (data?.items ?? []).map(toCalendarEvent),
    [data],
  );

  const refetch = useCallback(async () => {
    await mutate();
  }, [mutate]);

  return { events, isLoading, refetch };
}
