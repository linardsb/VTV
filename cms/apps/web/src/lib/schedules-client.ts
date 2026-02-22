/**
 * VTV Schedules API Client
 *
 * Connects to the FastAPI schedule endpoints for managing
 * agencies, routes, calendars, trips, and GTFS import.
 */

import type {
  Agency,
  AgencyCreate,
  Calendar,
  CalendarCreate,
  CalendarUpdate,
  CalendarException,
  CalendarExceptionCreate,
  Trip,
  TripCreate,
  TripUpdate,
  TripDetail,
  StopTime,
  StopTimeCreate,
  GTFSImportResponse,
  ValidationResult,
  PaginatedResponse,
} from "@/types/schedule";
import type { Route, RouteCreate, RouteUpdate } from "@/types/route";

const BASE_URL =
  process.env.NEXT_PUBLIC_AGENT_URL ?? "http://localhost:8123";
const API_PREFIX = "/api/v1/schedules";

/** Error thrown when the schedules API returns a non-OK response. */
export class SchedulesApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "SchedulesApiError";
    this.status = status;
  }
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const detail = await response.text().catch(() => "Unknown error");
    throw new SchedulesApiError(response.status, detail);
  }
  return response.json() as Promise<T>;
}

// ---------------------------------------------------------------------------
// Agencies
// ---------------------------------------------------------------------------

/** Fetch all agencies. */
export async function fetchAgencies(): Promise<Agency[]> {
  const response = await fetch(`${BASE_URL}${API_PREFIX}/agencies`);
  return handleResponse<Agency[]>(response);
}

/** Create a new agency. */
export async function createAgency(data: AgencyCreate): Promise<Agency> {
  const response = await fetch(`${BASE_URL}${API_PREFIX}/agencies`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  return handleResponse<Agency>(response);
}

// ---------------------------------------------------------------------------
// Routes
// ---------------------------------------------------------------------------

/** Fetch paginated routes with optional filters. */
export async function fetchRoutes(params: {
  page?: number;
  page_size?: number;
  search?: string;
  route_type?: number;
  agency_id?: number;
  is_active?: boolean;
}): Promise<PaginatedResponse<Route>> {
  const searchParams = new URLSearchParams();
  if (params.page !== undefined) searchParams.set("page", String(params.page));
  if (params.page_size !== undefined)
    searchParams.set("page_size", String(params.page_size));
  if (params.search) searchParams.set("search", params.search);
  if (params.route_type !== undefined)
    searchParams.set("route_type", String(params.route_type));
  if (params.agency_id !== undefined)
    searchParams.set("agency_id", String(params.agency_id));
  if (params.is_active !== undefined)
    searchParams.set("is_active", String(params.is_active));

  const response = await fetch(
    `${BASE_URL}${API_PREFIX}/routes?${searchParams.toString()}`,
  );
  return handleResponse<PaginatedResponse<Route>>(response);
}

/** Fetch a single route by ID. */
export async function fetchRoute(id: number): Promise<Route> {
  const response = await fetch(`${BASE_URL}${API_PREFIX}/routes/${id}`);
  return handleResponse<Route>(response);
}

/** Create a new route. */
export async function createRoute(data: RouteCreate): Promise<Route> {
  const response = await fetch(`${BASE_URL}${API_PREFIX}/routes`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  return handleResponse<Route>(response);
}

/** Update an existing route. */
export async function updateRoute(
  id: number,
  data: RouteUpdate,
): Promise<Route> {
  const response = await fetch(`${BASE_URL}${API_PREFIX}/routes/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  return handleResponse<Route>(response);
}

/** Delete a route. */
export async function deleteRoute(id: number): Promise<void> {
  const response = await fetch(`${BASE_URL}${API_PREFIX}/routes/${id}`, {
    method: "DELETE",
  });
  if (!response.ok) {
    const detail = await response.text().catch(() => "Unknown error");
    throw new SchedulesApiError(response.status, detail);
  }
}

// ---------------------------------------------------------------------------
// Calendars
// ---------------------------------------------------------------------------

/** Fetch paginated calendars with optional filters. */
export async function fetchCalendars(params: {
  page?: number;
  page_size?: number;
  active_on?: string;
}): Promise<PaginatedResponse<Calendar>> {
  const searchParams = new URLSearchParams();
  if (params.page !== undefined) searchParams.set("page", String(params.page));
  if (params.page_size !== undefined)
    searchParams.set("page_size", String(params.page_size));
  if (params.active_on) searchParams.set("active_on", params.active_on);

  const response = await fetch(
    `${BASE_URL}${API_PREFIX}/calendars?${searchParams.toString()}`,
  );
  return handleResponse<PaginatedResponse<Calendar>>(response);
}

/** Fetch a single calendar by ID. */
export async function fetchCalendar(id: number): Promise<Calendar> {
  const response = await fetch(`${BASE_URL}${API_PREFIX}/calendars/${id}`);
  return handleResponse<Calendar>(response);
}

/** Create a new calendar. */
export async function createCalendar(data: CalendarCreate): Promise<Calendar> {
  const response = await fetch(`${BASE_URL}${API_PREFIX}/calendars`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  return handleResponse<Calendar>(response);
}

/** Update an existing calendar. */
export async function updateCalendar(
  id: number,
  data: CalendarUpdate,
): Promise<Calendar> {
  const response = await fetch(`${BASE_URL}${API_PREFIX}/calendars/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  return handleResponse<Calendar>(response);
}

/** Delete a calendar. */
export async function deleteCalendar(id: number): Promise<void> {
  const response = await fetch(`${BASE_URL}${API_PREFIX}/calendars/${id}`, {
    method: "DELETE",
  });
  if (!response.ok) {
    const detail = await response.text().catch(() => "Unknown error");
    throw new SchedulesApiError(response.status, detail);
  }
}

/** Add a calendar exception. */
export async function addCalendarException(
  calendarId: number,
  data: CalendarExceptionCreate,
): Promise<CalendarException> {
  const response = await fetch(
    `${BASE_URL}${API_PREFIX}/calendars/${calendarId}/exceptions`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    },
  );
  return handleResponse<CalendarException>(response);
}

/** Delete a calendar exception. */
export async function deleteCalendarException(
  exceptionId: number,
): Promise<void> {
  const response = await fetch(
    `${BASE_URL}${API_PREFIX}/calendar-exceptions/${exceptionId}`,
    { method: "DELETE" },
  );
  if (!response.ok) {
    const detail = await response.text().catch(() => "Unknown error");
    throw new SchedulesApiError(response.status, detail);
  }
}

// ---------------------------------------------------------------------------
// Trips
// ---------------------------------------------------------------------------

/** Fetch paginated trips with optional filters. */
export async function fetchTrips(params: {
  page?: number;
  page_size?: number;
  route_id?: number;
  calendar_id?: number;
  direction_id?: number;
}): Promise<PaginatedResponse<Trip>> {
  const searchParams = new URLSearchParams();
  if (params.page !== undefined) searchParams.set("page", String(params.page));
  if (params.page_size !== undefined)
    searchParams.set("page_size", String(params.page_size));
  if (params.route_id !== undefined)
    searchParams.set("route_id", String(params.route_id));
  if (params.calendar_id !== undefined)
    searchParams.set("calendar_id", String(params.calendar_id));
  if (params.direction_id !== undefined)
    searchParams.set("direction_id", String(params.direction_id));

  const response = await fetch(
    `${BASE_URL}${API_PREFIX}/trips?${searchParams.toString()}`,
  );
  return handleResponse<PaginatedResponse<Trip>>(response);
}

/** Fetch a single trip with stop times. */
export async function fetchTrip(id: number): Promise<TripDetail> {
  const response = await fetch(`${BASE_URL}${API_PREFIX}/trips/${id}`);
  return handleResponse<TripDetail>(response);
}

/** Create a new trip. */
export async function createTrip(data: TripCreate): Promise<Trip> {
  const response = await fetch(`${BASE_URL}${API_PREFIX}/trips`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  return handleResponse<Trip>(response);
}

/** Update an existing trip. */
export async function updateTrip(
  id: number,
  data: TripUpdate,
): Promise<Trip> {
  const response = await fetch(`${BASE_URL}${API_PREFIX}/trips/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  return handleResponse<Trip>(response);
}

/** Delete a trip. */
export async function deleteTrip(id: number): Promise<void> {
  const response = await fetch(`${BASE_URL}${API_PREFIX}/trips/${id}`, {
    method: "DELETE",
  });
  if (!response.ok) {
    const detail = await response.text().catch(() => "Unknown error");
    throw new SchedulesApiError(response.status, detail);
  }
}

/** Replace all stop times for a trip. */
export async function replaceStopTimes(
  tripId: number,
  stopTimes: StopTimeCreate[],
): Promise<StopTime[]> {
  const response = await fetch(
    `${BASE_URL}${API_PREFIX}/trips/${tripId}/stop-times`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ stop_times: stopTimes }),
    },
  );
  return handleResponse<StopTime[]>(response);
}

// ---------------------------------------------------------------------------
// GTFS Import & Validation
// ---------------------------------------------------------------------------

/** Import a GTFS ZIP file. */
export async function importGTFS(file: File): Promise<GTFSImportResponse> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(`${BASE_URL}${API_PREFIX}/import`, {
    method: "POST",
    body: formData,
  });
  return handleResponse<GTFSImportResponse>(response);
}

/** Validate the current schedule data. */
export async function validateSchedule(): Promise<ValidationResult> {
  const response = await fetch(`${BASE_URL}${API_PREFIX}/validate`, {
    method: "POST",
  });
  return handleResponse<ValidationResult>(response);
}
