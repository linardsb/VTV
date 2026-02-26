/**
 * Schedules API client powered by @vtv/sdk.
 *
 * Drop-in replacement for schedules-client.ts — same function signatures,
 * backed by the generated SDK instead of hand-written fetch calls.
 * Covers agencies, routes, calendars, trips, and GTFS import/validate.
 */

import "@/lib/sdk";
import {
  // Agencies
  listAgenciesApiV1SchedulesAgenciesGet,
  createAgencyApiV1SchedulesAgenciesPost,
  // Routes
  listRoutesApiV1SchedulesRoutesGet,
  getRouteApiV1SchedulesRoutesRouteIdGet,
  createRouteApiV1SchedulesRoutesPost,
  updateRouteApiV1SchedulesRoutesRouteIdPatch,
  deleteRouteApiV1SchedulesRoutesRouteIdDelete,
  // Calendars
  listCalendarsApiV1SchedulesCalendarsGet,
  getCalendarApiV1SchedulesCalendarsCalendarIdGet,
  createCalendarApiV1SchedulesCalendarsPost,
  updateCalendarApiV1SchedulesCalendarsCalendarIdPatch,
  deleteCalendarApiV1SchedulesCalendarsCalendarIdDelete,
  addCalendarExceptionApiV1SchedulesCalendarsCalendarIdExceptionsPost,
  removeCalendarExceptionApiV1SchedulesCalendarExceptionsExceptionIdDelete,
  // Trips
  listTripsApiV1SchedulesTripsGet,
  getTripApiV1SchedulesTripsTripIdGet,
  createTripApiV1SchedulesTripsPost,
  updateTripApiV1SchedulesTripsTripIdPatch,
  deleteTripApiV1SchedulesTripsTripIdDelete,
  replaceStopTimesApiV1SchedulesTripsTripIdStopTimesPut,
  // Import / Validate
  importGtfsApiV1SchedulesImportPost,
  validateScheduleApiV1SchedulesValidatePost,
} from "@vtv/sdk";
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

/** Error thrown when the schedules API returns a non-OK response. */
export class SchedulesApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "SchedulesApiError";
    this.status = status;
  }
}

// ---------------------------------------------------------------------------
// Agencies
// ---------------------------------------------------------------------------

/** Fetch all agencies. */
export async function fetchAgencies(): Promise<Agency[]> {
  const { data, error, response } =
    await listAgenciesApiV1SchedulesAgenciesGet();
  if (error || !data) {
    throw new SchedulesApiError(
      response.status,
      typeof error === "string" ? error : "Failed to fetch agencies",
    );
  }
  return data as unknown as Agency[];
}

/** Create a new agency. */
export async function createAgency(agencyData: AgencyCreate): Promise<Agency> {
  const { data, error, response } =
    await createAgencyApiV1SchedulesAgenciesPost({
      body: agencyData,
    });
  if (error || !data) {
    throw new SchedulesApiError(
      response.status,
      typeof error === "string" ? error : "Failed to create agency",
    );
  }
  return data as unknown as Agency;
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
  const { data, error, response } = await listRoutesApiV1SchedulesRoutesGet({
    query: {
      page: params.page,
      page_size: params.page_size,
      search: params.search ?? null,
      route_type: params.route_type ?? null,
      agency_id: params.agency_id ?? null,
      is_active: params.is_active ?? null,
    },
  });
  if (error || !data) {
    throw new SchedulesApiError(
      response.status,
      typeof error === "string" ? error : "Failed to fetch routes",
    );
  }
  return data as unknown as PaginatedResponse<Route>;
}

/** Fetch a single route by ID. */
export async function fetchRoute(id: number): Promise<Route> {
  const { data, error, response } =
    await getRouteApiV1SchedulesRoutesRouteIdGet({
      path: { route_id: id },
    });
  if (error || !data) {
    throw new SchedulesApiError(
      response.status,
      typeof error === "string" ? error : "Failed to fetch route",
    );
  }
  return data as unknown as Route;
}

/** Create a new route. */
export async function createRoute(routeData: RouteCreate): Promise<Route> {
  const { data, error, response } = await createRouteApiV1SchedulesRoutesPost({
    body: routeData,
  });
  if (error || !data) {
    throw new SchedulesApiError(
      response.status,
      typeof error === "string" ? error : "Failed to create route",
    );
  }
  return data as unknown as Route;
}

/** Update an existing route. */
export async function updateRoute(
  id: number,
  routeData: RouteUpdate,
): Promise<Route> {
  const { data, error, response } =
    await updateRouteApiV1SchedulesRoutesRouteIdPatch({
      path: { route_id: id },
      body: routeData,
    });
  if (error || !data) {
    throw new SchedulesApiError(
      response.status,
      typeof error === "string" ? error : "Failed to update route",
    );
  }
  return data as unknown as Route;
}

/** Delete a route. */
export async function deleteRoute(id: number): Promise<void> {
  const { error, response } =
    await deleteRouteApiV1SchedulesRoutesRouteIdDelete({
      path: { route_id: id },
    });
  if (error) {
    throw new SchedulesApiError(
      response.status,
      typeof error === "string" ? error : "Failed to delete route",
    );
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
  const { data, error, response } =
    await listCalendarsApiV1SchedulesCalendarsGet({
      query: {
        page: params.page,
        page_size: params.page_size,
        active_on: params.active_on ?? null,
      },
    });
  if (error || !data) {
    throw new SchedulesApiError(
      response.status,
      typeof error === "string" ? error : "Failed to fetch calendars",
    );
  }
  return data as unknown as PaginatedResponse<Calendar>;
}

/** Fetch a single calendar by ID. */
export async function fetchCalendar(id: number): Promise<Calendar> {
  const { data, error, response } =
    await getCalendarApiV1SchedulesCalendarsCalendarIdGet({
      path: { calendar_id: id },
    });
  if (error || !data) {
    throw new SchedulesApiError(
      response.status,
      typeof error === "string" ? error : "Failed to fetch calendar",
    );
  }
  return data as unknown as Calendar;
}

/** Create a new calendar. */
export async function createCalendar(
  calendarData: CalendarCreate,
): Promise<Calendar> {
  const { data, error, response } =
    await createCalendarApiV1SchedulesCalendarsPost({
      body: calendarData,
    });
  if (error || !data) {
    throw new SchedulesApiError(
      response.status,
      typeof error === "string" ? error : "Failed to create calendar",
    );
  }
  return data as unknown as Calendar;
}

/** Update an existing calendar. */
export async function updateCalendar(
  id: number,
  calendarData: CalendarUpdate,
): Promise<Calendar> {
  const { data, error, response } =
    await updateCalendarApiV1SchedulesCalendarsCalendarIdPatch({
      path: { calendar_id: id },
      body: calendarData,
    });
  if (error || !data) {
    throw new SchedulesApiError(
      response.status,
      typeof error === "string" ? error : "Failed to update calendar",
    );
  }
  return data as unknown as Calendar;
}

/** Delete a calendar. */
export async function deleteCalendar(id: number): Promise<void> {
  const { error, response } =
    await deleteCalendarApiV1SchedulesCalendarsCalendarIdDelete({
      path: { calendar_id: id },
    });
  if (error) {
    throw new SchedulesApiError(
      response.status,
      typeof error === "string" ? error : "Failed to delete calendar",
    );
  }
}

/** Add a calendar exception. */
export async function addCalendarException(
  calendarId: number,
  exceptionData: CalendarExceptionCreate,
): Promise<CalendarException> {
  const { data, error, response } =
    await addCalendarExceptionApiV1SchedulesCalendarsCalendarIdExceptionsPost({
      path: { calendar_id: calendarId },
      body: exceptionData,
    });
  if (error || !data) {
    throw new SchedulesApiError(
      response.status,
      typeof error === "string" ? error : "Failed to add calendar exception",
    );
  }
  return data as unknown as CalendarException;
}

/** Delete a calendar exception. */
export async function deleteCalendarException(
  exceptionId: number,
): Promise<void> {
  const { error, response } =
    await removeCalendarExceptionApiV1SchedulesCalendarExceptionsExceptionIdDelete(
      {
        path: { exception_id: exceptionId },
      },
    );
  if (error) {
    throw new SchedulesApiError(
      response.status,
      typeof error === "string"
        ? error
        : "Failed to delete calendar exception",
    );
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
  const { data, error, response } = await listTripsApiV1SchedulesTripsGet({
    query: {
      page: params.page,
      page_size: params.page_size,
      route_id: params.route_id ?? null,
      calendar_id: params.calendar_id ?? null,
      direction_id: params.direction_id ?? null,
    },
  });
  if (error || !data) {
    throw new SchedulesApiError(
      response.status,
      typeof error === "string" ? error : "Failed to fetch trips",
    );
  }
  return data as unknown as PaginatedResponse<Trip>;
}

/** Fetch a single trip with stop times. */
export async function fetchTrip(id: number): Promise<TripDetail> {
  const { data, error, response } =
    await getTripApiV1SchedulesTripsTripIdGet({
      path: { trip_id: id },
    });
  if (error || !data) {
    throw new SchedulesApiError(
      response.status,
      typeof error === "string" ? error : "Failed to fetch trip",
    );
  }
  return data as unknown as TripDetail;
}

/** Create a new trip. */
export async function createTrip(tripData: TripCreate): Promise<Trip> {
  const { data, error, response } = await createTripApiV1SchedulesTripsPost({
    body: tripData,
  });
  if (error || !data) {
    throw new SchedulesApiError(
      response.status,
      typeof error === "string" ? error : "Failed to create trip",
    );
  }
  return data as unknown as Trip;
}

/** Update an existing trip. */
export async function updateTrip(
  id: number,
  tripData: TripUpdate,
): Promise<Trip> {
  const { data, error, response } =
    await updateTripApiV1SchedulesTripsTripIdPatch({
      path: { trip_id: id },
      body: tripData,
    });
  if (error || !data) {
    throw new SchedulesApiError(
      response.status,
      typeof error === "string" ? error : "Failed to update trip",
    );
  }
  return data as unknown as Trip;
}

/** Delete a trip. */
export async function deleteTrip(id: number): Promise<void> {
  const { error, response } = await deleteTripApiV1SchedulesTripsTripIdDelete({
    path: { trip_id: id },
  });
  if (error) {
    throw new SchedulesApiError(
      response.status,
      typeof error === "string" ? error : "Failed to delete trip",
    );
  }
}

/** Replace all stop times for a trip. */
export async function replaceStopTimes(
  tripId: number,
  stopTimes: StopTimeCreate[],
): Promise<StopTime[]> {
  const { data, error, response } =
    await replaceStopTimesApiV1SchedulesTripsTripIdStopTimesPut({
      path: { trip_id: tripId },
      body: { stop_times: stopTimes },
    });
  if (error || !data) {
    throw new SchedulesApiError(
      response.status,
      typeof error === "string" ? error : "Failed to replace stop times",
    );
  }
  return data as unknown as StopTime[];
}

// ---------------------------------------------------------------------------
// GTFS Import & Validation
// ---------------------------------------------------------------------------

/** Import a GTFS ZIP file. */
export async function importGTFS(file: File): Promise<GTFSImportResponse> {
  const { data, error, response } = await importGtfsApiV1SchedulesImportPost({
    body: { file },
  });
  if (error || !data) {
    throw new SchedulesApiError(
      response.status,
      typeof error === "string" ? error : "Failed to import GTFS",
    );
  }
  return data as unknown as GTFSImportResponse;
}

/** Validate the current schedule data. */
export async function validateSchedule(): Promise<ValidationResult> {
  const { data, error, response } =
    await validateScheduleApiV1SchedulesValidatePost();
  if (error || !data) {
    throw new SchedulesApiError(
      response.status,
      typeof error === "string" ? error : "Failed to validate schedule",
    );
  }
  return data as unknown as ValidationResult;
}
