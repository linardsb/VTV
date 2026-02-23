/**
 * VTV Events API Client
 *
 * Connects to the FastAPI events endpoints for operational event management.
 */

import type {
  OperationalEvent,
  EventCreate,
  EventUpdate,
  PaginatedEvents,
} from "@/types/event";
import { authFetch } from "@/lib/auth-fetch";

const BASE_URL =
  process.env.NEXT_PUBLIC_AGENT_URL ?? "http://localhost:8123";
const API_PREFIX = "/api/v1/events";

/** Error thrown when the events API returns a non-OK response. */
export class EventsApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "EventsApiError";
    this.status = status;
  }
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const detail = await response.text().catch(() => "Unknown error");
    throw new EventsApiError(response.status, detail);
  }
  return response.json() as Promise<T>;
}

/** Fetch paginated events with optional date range filter. */
export async function fetchEvents(params: {
  page?: number;
  page_size?: number;
  start_date?: string;
  end_date?: string;
}): Promise<PaginatedEvents> {
  const searchParams = new URLSearchParams();
  if (params.page !== undefined) searchParams.set("page", String(params.page));
  if (params.page_size !== undefined)
    searchParams.set("page_size", String(params.page_size));
  if (params.start_date) searchParams.set("start_date", params.start_date);
  if (params.end_date) searchParams.set("end_date", params.end_date);

  const response = await authFetch(
    `${BASE_URL}${API_PREFIX}/?${searchParams.toString()}`,
  );
  return handleResponse<PaginatedEvents>(response);
}

/** Fetch a single event by ID. */
export async function fetchEvent(id: number): Promise<OperationalEvent> {
  const response = await authFetch(`${BASE_URL}${API_PREFIX}/${id}`);
  return handleResponse<OperationalEvent>(response);
}

/** Create a new event. */
export async function createEvent(
  data: EventCreate,
): Promise<OperationalEvent> {
  const response = await authFetch(`${BASE_URL}${API_PREFIX}/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  return handleResponse<OperationalEvent>(response);
}

/** Update an existing event. */
export async function updateEvent(
  id: number,
  data: EventUpdate,
): Promise<OperationalEvent> {
  const response = await authFetch(`${BASE_URL}${API_PREFIX}/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  return handleResponse<OperationalEvent>(response);
}

/** Delete an event. */
export async function deleteEvent(id: number): Promise<void> {
  const response = await authFetch(`${BASE_URL}${API_PREFIX}/${id}`, {
    method: "DELETE",
  });
  if (!response.ok) {
    const detail = await response.text().catch(() => "Unknown error");
    throw new EventsApiError(response.status, detail);
  }
}
