"use client";

import { useState, useMemo, useCallback, useEffect } from "react";
import dynamic from "next/dynamic";
import { useTranslations } from "next-intl";
import { useSession } from "next-auth/react";
import { Plus, Filter } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  ResizablePanelGroup,
  ResizablePanel,
  ResizableHandle,
} from "@/components/ui/resizable";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Skeleton } from "@/components/ui/skeleton";
import { useIsMobile } from "@/hooks/use-mobile";
import { useVehiclePositions } from "@/hooks/use-vehicle-positions";
import { RouteFilters } from "@/components/routes/route-filters";
import { RouteTable } from "@/components/routes/route-table";
import { RouteDetail } from "@/components/routes/route-detail";
import { RouteForm } from "@/components/routes/route-form";
import { DeleteRouteDialog } from "@/components/routes/delete-route-dialog";
import {
  fetchRoutes,
  fetchAgencies,
  createRoute,
  updateRoute,
  deleteRoute,
} from "@/lib/schedules-sdk";
import { toHexColor } from "@/lib/color-utils";
import type { Route, RouteCreate, RouteUpdate } from "@/types/route";
import type { Agency } from "@/types/schedule";

const PAGE_SIZE = 20;

function MapSkeleton() {
  return (
    <div className="flex h-full w-full items-center justify-center bg-surface">
      <div className="flex flex-col items-center gap-2">
        <Skeleton className="h-8 w-32" />
        <Skeleton className="h-4 w-24" />
      </div>
    </div>
  );
}

const RouteMap = dynamic(
  () => import("@/components/routes/route-map").then((m) => ({ default: m.RouteMap })),
  { ssr: false, loading: () => <MapSkeleton /> },
);

export default function RoutesPage() {
  const t = useTranslations("routes");
  const isMobile = useIsMobile();
  const { data: session, status } = useSession();
  const userRole = session?.user?.role ?? "viewer";
  const IS_READ_ONLY = userRole === "viewer" || userRole === "dispatcher";

  // Data state
  const [routes, setRoutes] = useState<Route[]>([]);
  const [allRoutes, setAllRoutes] = useState<Route[]>([]);
  const [agencies, setAgencies] = useState<Agency[]>([]);
  const [totalItems, setTotalItems] = useState(0);
  const [page, setPage] = useState(1);
  const [isLoading, setIsLoading] = useState(true);

  // UI state — selectedRouteId declared early for selectedGtfsRouteId dependency
  const [selectedRouteId, setSelectedRouteId] = useState<number | null>(null);

  // Build route color lookup for live vehicle markers: gtfs_route_id → #hex
  const routeColorMap = useMemo(() => {
    const map: Record<string, string> = {};
    for (const r of allRoutes) {
      if (r.route_color) {
        map[r.gtfs_route_id] = toHexColor(r.route_color);
      }
    }
    return map;
  }, [allRoutes]);

  // Selected route → GTFS ID for map highlight + WS route filter
  const selectedGtfsRouteId = useMemo(() => {
    if (!selectedRouteId) return null;
    const r = routes.find((route) => route.id === selectedRouteId);
    return r?.gtfs_route_id ?? null;
  }, [routes, selectedRouteId]);

  // Live vehicle positions via WebSocket (falls back to HTTP polling)
  const { vehicles: liveVehicles, connectionMode } = useVehiclePositions({
    colorMap: routeColorMap,
    routeFilter: selectedGtfsRouteId,
  });

  // Filter state
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState<number | null>(null);
  const [statusFilter, setStatusFilter] = useState<"all" | "active" | "inactive">("all");
  const [agencyFilter, setAgencyFilter] = useState<number | null>(null);
  const [filterSheetOpen, setFilterSheetOpen] = useState(false);

  // Debounced search
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(search);
      setPage(1);
    }, 300);
    return () => clearTimeout(timer);
  }, [search]);

  // Filter live vehicles by transport type
  const filteredVehicles = useMemo(() => {
    if (typeFilter === null) return liveVehicles;
    return liveVehicles.filter((v) => v.routeType === typeFilter);
  }, [liveVehicles, typeFilter]);

  // UI state
  const [detailOpen, setDetailOpen] = useState(false);
  const [formOpen, setFormOpen] = useState(false);
  const [formMode, setFormMode] = useState<"create" | "edit">("create");
  const [formKey, setFormKey] = useState(0);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<Route | null>(null);

  // Derived
  const selectedRoute = useMemo(
    () => routes.find((r) => r.id === selectedRouteId) ?? null,
    [routes, selectedRouteId],
  );


  // Load agencies on mount
  const loadAgencies = useCallback(async () => {
    try {
      const data = await fetchAgencies();
      setAgencies(data);
    } catch (e) {
      console.warn("[routes] Failed to load agencies:", e);
    }
  }, []);

  // Fetch paginated routes for the table
  const loadRoutes = useCallback(async () => {
    setIsLoading(true);
    try {
      const result = await fetchRoutes({
        page,
        page_size: PAGE_SIZE,
        search: debouncedSearch || undefined,
        route_type: typeFilter ?? undefined,
        agency_id: agencyFilter ?? undefined,
        is_active: statusFilter === "all" ? undefined : statusFilter === "active",
      });
      setRoutes(result.items);
      setTotalItems(result.total);
    } catch (e) {
      console.warn("[routes] Failed to load routes:", e);
      setRoutes([]);
      setTotalItems(0);
    } finally {
      setIsLoading(false);
    }
  }, [page, debouncedSearch, typeFilter, agencyFilter, statusFilter]);

  // Fetch all routes for color map (needed for vehicle markers)
  const loadAllRoutes = useCallback(async () => {
    try {
      const first = await fetchRoutes({ page: 1, page_size: 100 });
      const totalPages = Math.ceil(first.total / 100);
      if (totalPages <= 1) {
        setAllRoutes(first.items);
        return;
      }
      const collected = [...first.items];
      for (let p = 2; p <= totalPages; p++) {
        const result = await fetchRoutes({ page: p, page_size: 100 });
        collected.push(...result.items);
      }
      setAllRoutes(collected);
    } catch (e) {
      console.warn("[routes] Failed to load all routes:", e);
      setAllRoutes([]);
    }
  }, []);

  useEffect(() => {
    if (status !== "authenticated") return;
    void loadAgencies();
    void loadAllRoutes();
  }, [loadAgencies, loadAllRoutes, status]);

  useEffect(() => {
    if (status !== "authenticated") return;
    void loadRoutes();
  }, [loadRoutes, status]);

  // Handlers
  const handleSelectRoute = useCallback(
    (routeId: number) => {
      setSelectedRouteId(routeId);
      setDetailOpen(true);
    },
    [],
  );

  const handleCreate = useCallback(() => {
    setFormMode("create");
    setSelectedRouteId(null);
    setFormKey((k) => k + 1);
    setFormOpen(true);
  }, []);

  const handleEdit = useCallback((route: Route) => {
    setFormMode("edit");
    setSelectedRouteId(route.id);
    setDetailOpen(false);
    setFormKey((k) => k + 1);
    setFormOpen(true);
  }, []);

  const handleDeleteRequest = useCallback((route: Route) => {
    setDeleteTarget(route);
    setDeleteOpen(true);
  }, []);

  const handleDeleteConfirm = useCallback(async (routeId: number) => {
    try {
      await deleteRoute(routeId);
      toast.success(t("toast.deleted"));
      if (selectedRouteId === routeId) {
        setSelectedRouteId(null);
        setDetailOpen(false);
      }
      void loadRoutes();
      void loadAllRoutes();
    } catch {
      toast.error(t("toast.deleteError"));
    }
  }, [selectedRouteId, t, loadRoutes, loadAllRoutes]);

  const handleFormSubmit = useCallback(
    async (data: RouteCreate | RouteUpdate) => {
      try {
        if (formMode === "create") {
          await createRoute(data as RouteCreate);
          toast.success(t("toast.created"));
        } else if (selectedRouteId) {
          await updateRoute(selectedRouteId, data as RouteUpdate);
          toast.success(t("toast.updated"));
        }
        setFormOpen(false);
        void loadRoutes();
        void loadAllRoutes();
      } catch {
        toast.error(
          formMode === "create" ? t("toast.createError") : t("toast.updateError"),
        );
      }
    },
    [formMode, selectedRouteId, t, loadRoutes, loadAllRoutes],
  );

  const handlePageChange = useCallback((newPage: number) => {
    setPage(newPage);
  }, []);

  return (
    <div className="flex flex-col gap-(--spacing-grid) md:h-[calc(100vh-var(--spacing-page)*2)]">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-heading text-heading font-semibold text-foreground">
            {t("title")}
          </h1>
          <p className="hidden sm:block text-sm text-foreground-muted">{t("description")}</p>
        </div>
        <div className="flex items-center gap-(--spacing-inline)">
          {isMobile && (
            <Button
              variant="outline"
              size="sm"
              className="cursor-pointer"
              onClick={() => setFilterSheetOpen(true)}
              aria-label={t("mobile.showFilters")}
            >
              <Filter className="mr-1 size-4" aria-hidden="true" />
              {t("mobile.showFilters")}
            </Button>
          )}
          {!IS_READ_ONLY && (
            <Button className="cursor-pointer" onClick={handleCreate}>
              <Plus className="mr-2 size-4" aria-hidden="true" />
              {t("actions.create")}
            </Button>
          )}
        </div>
      </div>

      {/* Layout: Mobile (tabs) vs Desktop (resizable panels) */}
      {isMobile === undefined ? (
        <div className="flex min-h-0 flex-1 items-center justify-center">
          <Skeleton className="h-full w-full rounded-lg" />
        </div>
      ) : isMobile ? (
        <>
          {/* Mobile filter sheet */}
          <RouteFilters
            search={search}
            onSearchChange={setSearch}
            typeFilter={typeFilter}
            onTypeFilterChange={(type) => { setTypeFilter(type); setPage(1); }}
            statusFilter={statusFilter}
            onStatusFilterChange={(status) => { setStatusFilter(status); setPage(1); }}
            agencyFilter={agencyFilter}
            onAgencyFilterChange={(id) => { setAgencyFilter(id); setPage(1); }}
            agencies={agencies}
            resultCount={totalItems}
            asSheet
            sheetOpen={filterSheetOpen}
            onSheetOpenChange={setFilterSheetOpen}
          />

          {/* Mobile tabs: Table | Map */}
          <Tabs defaultValue="table" className="flex min-h-[50vh] flex-1 flex-col md:min-h-0">
            <TabsList className="w-full">
              <TabsTrigger value="table" className="flex-1 cursor-pointer">
                {t("mobile.tableTab")}
              </TabsTrigger>
              <TabsTrigger value="map" className="flex-1 cursor-pointer">
                {t("mobile.mapTab")}
              </TabsTrigger>
            </TabsList>
            <TabsContent value="table" className="flex-1 overflow-hidden rounded-lg border border-border mt-(--spacing-tight)">
              <RouteTable
                routes={routes}
                selectedRouteId={selectedRouteId}
                onSelectRoute={handleSelectRoute}
                onEditRoute={handleEdit}
                onDeleteRoute={handleDeleteRequest}
                isReadOnly={IS_READ_ONLY}
                agencies={agencies}
                total={totalItems}
                page={page}
                pageSize={PAGE_SIZE}
                onPageChange={handlePageChange}
                isLoading={isLoading}
              />
            </TabsContent>
            <TabsContent value="map" className="min-h-[50vh] flex-1 overflow-hidden rounded-lg border border-border mt-(--spacing-tight)">
              <RouteMap
                buses={filteredVehicles}
                selectedRouteId={selectedGtfsRouteId}
                onSelectRoute={(gtfsId) => {
                  const route = allRoutes.find((r) => r.gtfs_route_id === gtfsId);
                  if (route) handleSelectRoute(route.id);
                }}
                connectionMode={connectionMode}
              />
            </TabsContent>
          </Tabs>
        </>
      ) : (
        <ResizablePanelGroup
          orientation="horizontal"
          className="min-h-0 flex-1 overflow-hidden rounded-lg border border-border"
        >
          <ResizablePanel defaultSize={60} minSize={40}>
            <div className="flex h-full">
              <RouteFilters
                search={search}
                onSearchChange={setSearch}
                typeFilter={typeFilter}
                onTypeFilterChange={(type) => { setTypeFilter(type); setPage(1); }}
                statusFilter={statusFilter}
                onStatusFilterChange={(status) => { setStatusFilter(status); setPage(1); }}
                agencyFilter={agencyFilter}
                onAgencyFilterChange={(id) => { setAgencyFilter(id); setPage(1); }}
                agencies={agencies}
                resultCount={totalItems}
              />
              <RouteTable
                routes={routes}
                selectedRouteId={selectedRouteId}
                onSelectRoute={handleSelectRoute}
                onEditRoute={handleEdit}
                onDeleteRoute={handleDeleteRequest}
                isReadOnly={IS_READ_ONLY}
                agencies={agencies}
                total={totalItems}
                page={page}
                pageSize={PAGE_SIZE}
                onPageChange={handlePageChange}
                isLoading={isLoading}
              />
            </div>
          </ResizablePanel>
          <ResizableHandle withHandle />
          <ResizablePanel defaultSize={40} minSize={25}>
            <RouteMap
              buses={filteredVehicles}
              selectedRouteId={selectedGtfsRouteId}
              onSelectRoute={(gtfsId) => {
                const route = allRoutes.find((r) => r.gtfs_route_id === gtfsId);
                if (route) handleSelectRoute(route.id);
              }}
              connectionMode={connectionMode}
            />
          </ResizablePanel>
        </ResizablePanelGroup>
      )}

      {/* Right: Detail Sheet (overlay) */}
      <RouteDetail
        route={selectedRoute}
        isOpen={detailOpen}
        onClose={() => { setDetailOpen(false); setSelectedRouteId(null); }}
        onEdit={handleEdit}
        onDelete={handleDeleteRequest}
        isReadOnly={IS_READ_ONLY}
        agencies={agencies}
      />

      {/* Form Sheet */}
      <RouteForm
        key={formKey}
        mode={formMode}
        route={selectedRoute}
        agencies={agencies}
        isOpen={formOpen}
        onClose={() => setFormOpen(false)}
        onSubmit={handleFormSubmit}
      />

      {/* Delete Dialog */}
      <DeleteRouteDialog
        route={deleteTarget}
        isOpen={deleteOpen}
        onClose={() => setDeleteOpen(false)}
        onConfirm={handleDeleteConfirm}
      />
    </div>
  );
}
