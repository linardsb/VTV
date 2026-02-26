"use client";

import { useState, useCallback, useEffect, useMemo } from "react";
import { useTranslations } from "next-intl";
import { useSession } from "next-auth/react";
import { useSearchParams, usePathname, useRouter } from "next/navigation";
import { Plus } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  fetchRoutes,
  fetchCalendars,
  fetchTrips,
  createCalendar,
  updateCalendar,
  deleteCalendar as deleteCalendarApi,
  createTrip,
  updateTrip,
  deleteTrip as deleteTripApi,
} from "@/lib/schedules-sdk";
import { CalendarTable } from "@/components/schedules/calendar-table";
import { CalendarForm } from "@/components/schedules/calendar-form";
import { CalendarDialog } from "@/components/schedules/calendar-dialog";
import { CalendarSearch } from "@/components/schedules/calendar-search";
import { DeleteCalendarDialog } from "@/components/schedules/delete-calendar-dialog";
import { TripTable } from "@/components/schedules/trip-table";
import { TripFilters } from "@/components/schedules/trip-filters";
import { TripSearch } from "@/components/schedules/trip-search";
import { TripForm } from "@/components/schedules/trip-form";
import { TripDetail } from "@/components/schedules/trip-detail";
import { DeleteTripDialog } from "@/components/schedules/delete-trip-dialog";
import { GTFSImport } from "@/components/schedules/gtfs-import";
import type { Calendar, CalendarCreate, CalendarUpdate, CalendarException, Trip, TripCreate, TripUpdate } from "@/types/schedule";
import type { Route } from "@/types/route";

const PAGE_SIZE = 20;

export default function SchedulesPage() {
  const t = useTranslations("schedules");
  const { data: session, status } = useSession();
  const searchParams = useSearchParams();
  const pathname = usePathname();
  const router = useRouter();
  const userRole = session?.user?.role ?? "viewer";
  const IS_READ_ONLY = userRole === "viewer";

  // Tab state synced with URL
  const [activeTab, setActiveTab] = useState(searchParams.get("tab") ?? "calendars");

  // Search & filter state
  const [calendarSearch, setCalendarSearch] = useState("");
  const [activeTodayFilter, setActiveTodayFilter] = useState(false);
  const [tripSearch, setTripSearch] = useState("");

  // Shared lookup data
  const [allRoutes, setAllRoutes] = useState<Route[]>([]);
  const [allCalendars, setAllCalendars] = useState<Calendar[]>([]);

  // Calendar state
  const [calendars, setCalendars] = useState<Calendar[]>([]);
  const [calendarTotal, setCalendarTotal] = useState(0);
  const [calendarPage, setCalendarPage] = useState(1);
  const [isCalendarLoading, setIsCalendarLoading] = useState(true);
  const [selectedCalendar, setSelectedCalendar] = useState<Calendar | null>(null);
  const [calendarExceptions, setCalendarExceptions] = useState<CalendarException[]>([]);
  const [calendarDialogOpen, setCalendarDialogOpen] = useState(false);
  const [calendarCreateOpen, setCalendarCreateOpen] = useState(false);
  const [calendarCreateKey, setCalendarCreateKey] = useState(0);
  const [calendarDeleteOpen, setCalendarDeleteOpen] = useState(false);
  const [calendarDeleteTarget, setCalendarDeleteTarget] = useState<Calendar | null>(null);

  // Trip state
  const [trips, setTrips] = useState<Trip[]>([]);
  const [tripTotal, setTripTotal] = useState(0);
  const [tripPage, setTripPage] = useState(1);
  const [isTripLoading, setIsTripLoading] = useState(true);
  const [routeFilter, setRouteFilter] = useState<number | null>(null);
  const [calendarFilter, setCalendarFilter] = useState<number | null>(null);
  const [directionFilter, setDirectionFilter] = useState<number | null>(null);
  const [selectedTrip, setSelectedTrip] = useState<Trip | null>(null);
  const [tripDetailOpen, setTripDetailOpen] = useState(false);
  const [tripFormOpen, setTripFormOpen] = useState(false);
  const [tripFormMode, setTripFormMode] = useState<"create" | "edit">("create");
  const [tripFormKey, setTripFormKey] = useState(0);
  const [tripDeleteOpen, setTripDeleteOpen] = useState(false);
  const [tripDeleteTarget, setTripDeleteTarget] = useState<Trip | null>(null);

  // Load shared lookups
  const loadLookups = useCallback(async () => {
    try {
      const [routeData, calendarData] = await Promise.all([
        fetchRoutes({ page: 1, page_size: 100 }),
        fetchCalendars({ page: 1, page_size: 100 }),
      ]);
      setAllRoutes(routeData.items);
      setAllCalendars(calendarData.items);
    } catch (e) {
      console.warn("[schedules] Failed to load lookups:", e);
    }
  }, []);

  // Load calendars
  const loadCalendars = useCallback(async () => {
    setIsCalendarLoading(true);
    try {
      const result = await fetchCalendars({
        page: calendarPage,
        page_size: PAGE_SIZE,
        active_on: activeTodayFilter ? new Date().toISOString().split("T")[0] : undefined,
      });
      setCalendars(result.items);
      setCalendarTotal(result.total);
    } catch (e) {
      console.warn("[schedules] Failed to load calendars:", e);
      setCalendars([]);
      setCalendarTotal(0);
    } finally {
      setIsCalendarLoading(false);
    }
  }, [calendarPage, activeTodayFilter]);

  // Load trips
  const loadTrips = useCallback(async () => {
    setIsTripLoading(true);
    try {
      const result = await fetchTrips({
        page: tripPage,
        page_size: PAGE_SIZE,
        route_id: routeFilter ?? undefined,
        calendar_id: calendarFilter ?? undefined,
        direction_id: directionFilter ?? undefined,
      });
      setTrips(result.items);
      setTripTotal(result.total);
    } catch (e) {
      console.warn("[schedules] Failed to load trips:", e);
      setTrips([]);
      setTripTotal(0);
    } finally {
      setIsTripLoading(false);
    }
  }, [tripPage, routeFilter, calendarFilter, directionFilter]);

  useEffect(() => { if (status !== "authenticated") return; void loadLookups(); }, [loadLookups, status]);
  useEffect(() => { if (status !== "authenticated") return; void loadCalendars(); }, [loadCalendars, status]);
  useEffect(() => { if (status !== "authenticated") return; void loadTrips(); }, [loadTrips, status]);

  // Client-side search filtering
  const filteredCalendars = useMemo(() => {
    if (!calendarSearch.trim()) return calendars;
    const q = calendarSearch.toLowerCase();
    return calendars.filter((c) => c.gtfs_service_id.toLowerCase().includes(q));
  }, [calendars, calendarSearch]);

  const filteredTrips = useMemo(() => {
    if (!tripSearch.trim()) return trips;
    const q = tripSearch.toLowerCase();
    return trips.filter((trip) =>
      trip.gtfs_trip_id.toLowerCase().includes(q) ||
      (trip.trip_headsign?.toLowerCase().includes(q) ?? false)
    );
  }, [trips, tripSearch]);

  // Tab URL sync
  function handleTabChange(tab: string) {
    setActiveTab(tab);
    const params = new URLSearchParams(searchParams.toString());
    if (tab === "calendars") { params.delete("tab"); } else { params.set("tab", tab); }
    const qs = params.toString();
    router.replace(`${pathname}${qs ? `?${qs}` : ""}`, { scroll: false });
  }

  // Active today filter toggle (resets page)
  function handleActiveTodayChange(active: boolean) {
    setActiveTodayFilter(active);
    setCalendarPage(1);
  }

  // Calendar handlers
  const handleCalendarSelect = useCallback((cal: Calendar) => {
    setSelectedCalendar(cal);
    setCalendarDialogOpen(true);
    // TODO: load exceptions from detail endpoint if we had a dedicated one
    setCalendarExceptions([]);
  }, []);

  const handleCalendarCreate = useCallback(() => {
    setCalendarCreateKey((k) => k + 1);
    setCalendarCreateOpen(true);
  }, []);

  const handleCalendarCreateSubmit = useCallback(async (data: CalendarCreate | CalendarUpdate) => {
    try {
      await createCalendar(data as CalendarCreate);
      toast.success(t("calendars.created"));
      setCalendarCreateOpen(false);
      void loadCalendars();
      void loadLookups();
    } catch {
      toast.error(t("calendars.saveError"));
    }
  }, [t, loadCalendars, loadLookups]);

  const handleCalendarDialogSubmit = useCallback(async (data: CalendarUpdate) => {
    if (!selectedCalendar) return;
    try {
      await updateCalendar(selectedCalendar.id, data);
      toast.success(t("calendars.updated"));
      // Refresh the selected calendar in-place so the dialog shows updated data
      const refreshed = await fetchCalendars({ page: calendarPage, page_size: PAGE_SIZE, active_on: activeTodayFilter ? new Date().toISOString().split("T")[0] : undefined });
      setCalendars(refreshed.items);
      setCalendarTotal(refreshed.total);
      const updated = refreshed.items.find((c) => c.id === selectedCalendar.id);
      if (updated) setSelectedCalendar(updated);
      void loadLookups();
    } catch {
      toast.error(t("calendars.saveError"));
    }
  }, [selectedCalendar, t, calendarPage, activeTodayFilter, loadLookups]);

  const handleCalendarDeleteRequest = useCallback((cal: Calendar) => {
    setCalendarDeleteTarget(cal);
    setCalendarDeleteOpen(true);
  }, []);

  const handleCalendarDeleteConfirm = useCallback(async (calId: number) => {
    try {
      await deleteCalendarApi(calId);
      toast.success(t("calendars.deleted"));
      if (selectedCalendar?.id === calId) {
        setSelectedCalendar(null);
        setCalendarDialogOpen(false);
      }
      void loadCalendars();
      void loadLookups();
    } catch {
      toast.error(t("calendars.deleteError"));
    }
  }, [selectedCalendar, t, loadCalendars, loadLookups]);

  // Trip handlers
  const handleTripSelect = useCallback((trip: Trip) => {
    setSelectedTrip(trip);
    setTripDetailOpen(true);
  }, []);

  const handleTripCreate = useCallback(() => {
    setTripFormMode("create");
    setSelectedTrip(null);
    setTripFormKey((k) => k + 1);
    setTripFormOpen(true);
  }, []);

  const handleTripEdit = useCallback((trip: Trip) => {
    setTripFormMode("edit");
    setSelectedTrip(trip);
    setTripDetailOpen(false);
    setTripFormKey((k) => k + 1);
    setTripFormOpen(true);
  }, []);

  const handleTripFormSubmit = useCallback(async (data: TripCreate | TripUpdate) => {
    try {
      if (tripFormMode === "create") {
        await createTrip(data as TripCreate);
        toast.success(t("trips.created"));
      } else if (selectedTrip) {
        await updateTrip(selectedTrip.id, data as TripUpdate);
        toast.success(t("trips.updated"));
      }
      setTripFormOpen(false);
      void loadTrips();
    } catch {
      toast.error(t("trips.saveError"));
    }
  }, [tripFormMode, selectedTrip, t, loadTrips]);

  const handleTripDeleteRequest = useCallback((trip: Trip) => {
    setTripDeleteTarget(trip);
    setTripDeleteOpen(true);
  }, []);

  const handleTripDeleteConfirm = useCallback(async (tripId: number) => {
    try {
      await deleteTripApi(tripId);
      toast.success(t("trips.deleted"));
      if (selectedTrip?.id === tripId) {
        setSelectedTrip(null);
        setTripDetailOpen(false);
      }
      void loadTrips();
    } catch {
      toast.error(t("trips.deleteError"));
    }
  }, [selectedTrip, t, loadTrips]);

  // Import handler
  const handleImportComplete = useCallback(() => {
    void loadLookups();
    void loadCalendars();
    void loadTrips();
  }, [loadLookups, loadCalendars, loadTrips]);

  return (
    <div className="flex h-[calc(100vh-var(--spacing-page)*2)] flex-col gap-(--spacing-grid)">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-heading text-heading font-semibold text-foreground">
            {t("title")}
          </h1>
          <p className="hidden sm:block text-sm text-foreground-muted">{t("description")}</p>
        </div>
      </div>

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={handleTabChange} className="flex min-h-0 flex-1 flex-col">
        <TabsList>
          <TabsTrigger value="calendars" className="cursor-pointer">{t("tabs.calendars")}</TabsTrigger>
          <TabsTrigger value="trips" className="cursor-pointer">{t("tabs.trips")}</TabsTrigger>
          <TabsTrigger value="import" className="cursor-pointer">{t("tabs.import")}</TabsTrigger>
        </TabsList>

        {/* Calendars Tab */}
        <TabsContent value="calendars" className="flex-1 overflow-hidden rounded-lg border border-border mt-(--spacing-tight)">
          <div className="flex h-full flex-col">
            <div className="flex items-center justify-between border-b border-border px-(--spacing-card) py-(--spacing-tight)">
              <CalendarSearch
                searchQuery={calendarSearch}
                onSearchChange={setCalendarSearch}
                activeTodayFilter={activeTodayFilter}
                onActiveTodayChange={handleActiveTodayChange}
              />
              {!IS_READ_ONLY && (
                <Button size="sm" className="cursor-pointer" onClick={handleCalendarCreate}>
                  <Plus className="mr-1 size-4" aria-hidden="true" />
                  {t("calendars.create")}
                </Button>
              )}
            </div>
            <CalendarTable
              calendars={filteredCalendars}
              total={calendarTotal}
              page={calendarPage}
              pageSize={PAGE_SIZE}
              onPageChange={setCalendarPage}
              onSelect={handleCalendarSelect}
              onEdit={handleCalendarSelect}
              onDelete={handleCalendarDeleteRequest}
              isReadOnly={IS_READ_ONLY}
              isLoading={isCalendarLoading}
            />
          </div>
        </TabsContent>

        {/* Trips Tab */}
        <TabsContent value="trips" className="flex-1 overflow-hidden rounded-lg border border-border mt-(--spacing-tight)">
          <div className="flex h-full flex-col">
            <div className="flex items-center justify-between border-b border-border px-(--spacing-card) py-(--spacing-tight)">
              <div className="flex items-center gap-(--spacing-inline) flex-wrap">
                <TripSearch value={tripSearch} onChange={setTripSearch} />
                <TripFilters
                  routes={allRoutes}
                  calendars={allCalendars}
                  routeFilter={routeFilter}
                  onRouteFilterChange={(id) => { setRouteFilter(id); setTripPage(1); }}
                  calendarFilter={calendarFilter}
                  onCalendarFilterChange={(id) => { setCalendarFilter(id); setTripPage(1); }}
                  directionFilter={directionFilter}
                  onDirectionFilterChange={(d) => { setDirectionFilter(d); setTripPage(1); }}
                />
              </div>
              {!IS_READ_ONLY && (
                <Button size="sm" className="cursor-pointer" onClick={handleTripCreate}>
                  <Plus className="mr-1 size-4" aria-hidden="true" />
                  {t("trips.create")}
                </Button>
              )}
            </div>
            <TripTable
              trips={filteredTrips}
              routes={allRoutes}
              calendars={allCalendars}
              total={tripTotal}
              page={tripPage}
              pageSize={PAGE_SIZE}
              onPageChange={setTripPage}
              onSelect={handleTripSelect}
              onEdit={handleTripEdit}
              onDelete={handleTripDeleteRequest}
              isReadOnly={IS_READ_ONLY}
              isLoading={isTripLoading}
            />
          </div>
        </TabsContent>

        {/* Import Tab */}
        <TabsContent value="import" className="flex-1 overflow-auto rounded-lg border border-border mt-(--spacing-tight)">
          <GTFSImport onImportComplete={handleImportComplete} />
        </TabsContent>
      </Tabs>

      {/* Calendar overlays */}
      <CalendarDialog
        calendar={selectedCalendar}
        exceptions={calendarExceptions}
        isOpen={calendarDialogOpen}
        onClose={() => { setCalendarDialogOpen(false); setSelectedCalendar(null); }}
        onSubmit={handleCalendarDialogSubmit}
        onDelete={handleCalendarDeleteRequest}
        onExceptionsChange={() => { /* reload exceptions */ }}
        isReadOnly={IS_READ_ONLY}
      />
      <CalendarForm
        key={`cal-${calendarCreateKey}`}
        mode="create"
        isOpen={calendarCreateOpen}
        onClose={() => setCalendarCreateOpen(false)}
        onSubmit={handleCalendarCreateSubmit}
      />
      <DeleteCalendarDialog
        calendar={calendarDeleteTarget}
        isOpen={calendarDeleteOpen}
        onClose={() => setCalendarDeleteOpen(false)}
        onConfirm={handleCalendarDeleteConfirm}
      />

      {/* Trip overlays */}
      <TripDetail
        trip={selectedTrip}
        routes={allRoutes}
        calendars={allCalendars}
        isOpen={tripDetailOpen}
        onClose={() => { setTripDetailOpen(false); setSelectedTrip(null); }}
        onEdit={handleTripEdit}
        onDelete={handleTripDeleteRequest}
        isReadOnly={IS_READ_ONLY}
      />
      <TripForm
        key={`trip-${tripFormKey}`}
        mode={tripFormMode}
        trip={selectedTrip}
        routes={allRoutes}
        calendars={allCalendars}
        isOpen={tripFormOpen}
        onClose={() => setTripFormOpen(false)}
        onSubmit={handleTripFormSubmit}
      />
      <DeleteTripDialog
        trip={tripDeleteTarget}
        isOpen={tripDeleteOpen}
        onClose={() => setTripDeleteOpen(false)}
        onConfirm={handleTripDeleteConfirm}
      />
    </div>
  );
}
