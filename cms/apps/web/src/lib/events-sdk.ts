/**
 * Events API client powered by @vtv/sdk.
 *
 * Drop-in replacement for events-client.ts — same function signatures,
 * backed by the generated SDK instead of hand-written fetch calls.
 */

import "@/lib/sdk";
import {
  listEventsApiV1EventsGet,
  createEventApiV1EventsPost,
  getEventApiV1EventsEventIdGet,
  updateEventApiV1EventsEventIdPatch,
  deleteEventApiV1EventsEventIdDelete,
} from "@vtv/sdk";
import type {
  OperationalEvent,
  EventCreate,
  EventUpdate,
  PaginatedEvents,
} from "@/types/event";

/** Error thrown when the events API returns a non-OK response. */
export class EventsApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "EventsApiError";
    this.status = status;
  }
}

/** Fetch paginated events with optional date range filter. */
export async function fetchEvents(params: {
  page?: number;
  page_size?: number;
  start_date?: string;
  end_date?: string;
}): Promise<PaginatedEvents> {
  const { data, error, response } = await listEventsApiV1EventsGet({
    query: {
      page: params.page,
      page_size: params.page_size,
      start_date: params.start_date ?? null,
      end_date: params.end_date ?? null,
    },
  });
  if (error || !data) {
    throw new EventsApiError(
      response.status,
      typeof error === "string" ? error : "Failed to fetch events",
    );
  }
  // Generated type is structurally compatible with PaginatedEvents
  // (items: EventResponse[] ≈ OperationalEvent[], plus pagination fields)
  return data as unknown as PaginatedEvents;
}

/** Fetch a single event by ID. */
export async function fetchEvent(id: number): Promise<OperationalEvent> {
  const { data, error, response } = await getEventApiV1EventsEventIdGet({
    path: { event_id: id },
  });
  if (error || !data) {
    throw new EventsApiError(
      response.status,
      typeof error === "string" ? error : "Failed to fetch event",
    );
  }
  return data as unknown as OperationalEvent;
}

/** Create a new event. */
export async function createEvent(
  eventData: EventCreate,
): Promise<OperationalEvent> {
  const { data, error, response } = await createEventApiV1EventsPost({
    body: eventData,
  });
  if (error || !data) {
    throw new EventsApiError(
      response.status,
      typeof error === "string" ? error : "Failed to create event",
    );
  }
  return data as unknown as OperationalEvent;
}

/** Update an existing event. */
export async function updateEvent(
  id: number,
  eventData: EventUpdate,
): Promise<OperationalEvent> {
  const { data, error, response } = await updateEventApiV1EventsEventIdPatch({
    path: { event_id: id },
    body: {
      title: eventData.title ?? null,
      description: eventData.description ?? null,
      start_datetime: eventData.start_datetime ?? null,
      end_datetime: eventData.end_datetime ?? null,
      priority: eventData.priority ?? null,
      category: eventData.category ?? null,
      goals: eventData.goals ?? null,
    },
  });
  if (error || !data) {
    throw new EventsApiError(
      response.status,
      typeof error === "string" ? error : "Failed to update event",
    );
  }
  return data as unknown as OperationalEvent;
}

/** Delete an event. */
export async function deleteEvent(id: number): Promise<void> {
  const { error, response } = await deleteEventApiV1EventsEventIdDelete({
    path: { event_id: id },
  });
  if (error) {
    throw new EventsApiError(
      response.status,
      typeof error === "string" ? error : "Failed to delete event",
    );
  }
}
