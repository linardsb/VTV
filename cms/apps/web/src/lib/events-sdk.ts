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
  driver_id?: number;
}): Promise<PaginatedEvents> {
  const { data, error, response } = await listEventsApiV1EventsGet({
    query: {
      page: params.page,
      page_size: params.page_size,
      start_date: params.start_date ?? null,
      end_date: params.end_date ?? null,
      driver_id: params.driver_id ?? null,
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

/** Update an existing event. Only sends provided fields (PATCH semantics). */
export async function updateEvent(
  id: number,
  eventData: EventUpdate,
): Promise<OperationalEvent> {
  // Only include fields that were actually provided to preserve PATCH semantics.
  // Sending null for unset fields causes the backend to overwrite them with null.
  const body: Record<string, unknown> = {};
  if (eventData.title !== undefined) body.title = eventData.title;
  if (eventData.description !== undefined) body.description = eventData.description;
  if (eventData.start_datetime !== undefined) body.start_datetime = eventData.start_datetime;
  if (eventData.end_datetime !== undefined) body.end_datetime = eventData.end_datetime;
  if (eventData.priority !== undefined) body.priority = eventData.priority;
  if (eventData.category !== undefined) body.category = eventData.category;
  if (eventData.goals !== undefined) body.goals = eventData.goals;
  if (eventData.driver_id !== undefined) body.driver_id = eventData.driver_id;

  const { data, error, response } = await updateEventApiV1EventsEventIdPatch({
    path: { event_id: id },
    body: body as EventUpdate,
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
