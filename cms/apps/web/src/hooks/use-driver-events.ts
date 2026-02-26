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
    driver_id: event.driver_id,
  };
}

interface DriverEventsResult {
  items: OperationalEvent[];
  total: number;
}

/**
 * Fetch all events for a specific driver on a given date.
 * Returns empty array when driverId is null (disabled).
 */
export function useDriverEvents(driverId: number | null, date: Date | null) {
  const { status } = useSession();

  const startOfDay = useMemo(() => {
    if (!date) return null;
    const d = new Date(date);
    d.setHours(0, 0, 0, 0);
    return d;
  }, [date]);

  const endOfDay = useMemo(() => {
    if (!date) return null;
    const d = new Date(date);
    d.setHours(23, 59, 59, 999);
    return d;
  }, [date]);

  const swrKey =
    status === "authenticated" && driverId && startOfDay && endOfDay
      ? `driver-events:${String(driverId)}:${startOfDay.toISOString()}`
      : null;

  const { data, isLoading, mutate } = useSWR<DriverEventsResult>(
    swrKey,
    async () =>
      fetchEvents({
        driver_id: driverId!,
        page_size: 100,
        start_date: startOfDay!.toISOString(),
        end_date: endOfDay!.toISOString(),
      }),
    {
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
