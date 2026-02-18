"use client";

import { useState, useMemo, useCallback } from "react";
import dynamic from "next/dynamic";
import { useTranslations } from "next-intl";
import { Plus, Filter } from "lucide-react";
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
import { MOCK_ROUTES } from "@/lib/mock-routes-data";
import type { Route, RouteFormData, RouteType } from "@/types/route";

// Simulated role — in production, read from session
const USER_ROLE: string = "admin";
const IS_READ_ONLY = USER_ROLE === "viewer" || USER_ROLE === "dispatcher";

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

  // Data state
  const [routes, setRoutes] = useState<Route[]>(MOCK_ROUTES);

  // Build route color lookup for live vehicle markers
  const routeColorMap = useMemo(() => {
    const map: Record<string, string> = {};
    for (const r of routes) {
      map[r.id] = r.color;
    }
    return map;
  }, [routes]);

  // Live vehicle positions from backend (polls every 15s)
  const { vehicles: liveVehicles } = useVehiclePositions({
    colorMap: routeColorMap,
  });

  // Filter state
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState<RouteType | null>(null);
  const [statusFilter, setStatusFilter] = useState<"all" | "active" | "inactive">("all");
  const [filterSheetOpen, setFilterSheetOpen] = useState(false);

  // Filter live vehicles by transport type when a type filter is active
  const filteredVehicles = useMemo(() => {
    if (typeFilter === null) return liveVehicles;
    return liveVehicles.filter((v) => v.routeType === typeFilter);
  }, [liveVehicles, typeFilter]);

  // UI state
  const [selectedRouteId, setSelectedRouteId] = useState<string | null>(null);
  const [detailOpen, setDetailOpen] = useState(false);
  const [formOpen, setFormOpen] = useState(false);
  const [formMode, setFormMode] = useState<"create" | "edit">("create");
  const [formInitialData, setFormInitialData] = useState<RouteFormData | undefined>();
  const [formKey, setFormKey] = useState(0);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<Route | null>(null);

  // Derived
  const selectedRoute = useMemo(
    () => routes.find((r) => r.id === selectedRouteId) ?? null,
    [routes, selectedRouteId],
  );

  const filtered = useMemo(() => {
    return routes.filter((route) => {
      // Search filter
      if (search) {
        const q = search.toLowerCase();
        const matchesSearch =
          route.shortName.toLowerCase().includes(q) ||
          route.longName.toLowerCase().includes(q) ||
          route.description.toLowerCase().includes(q);
        if (!matchesSearch) return false;
      }
      // Type filter
      if (typeFilter !== null && route.type !== typeFilter) return false;
      // Status filter
      if (statusFilter === "active" && !route.isActive) return false;
      if (statusFilter === "inactive" && route.isActive) return false;
      return true;
    });
  }, [routes, search, typeFilter, statusFilter]);

  // Handlers
  const handleSelectRoute = useCallback(
    (routeId: string) => {
      setSelectedRouteId(routeId);
      setDetailOpen(true);
    },
    [],
  );

  const handleCreate = useCallback(() => {
    setFormMode("create");
    setFormInitialData(undefined);
    setFormKey((k) => k + 1);
    setFormOpen(true);
  }, []);

  const handleEdit = useCallback((route: Route) => {
    setFormMode("edit");
    setFormInitialData({
      shortName: route.shortName,
      longName: route.longName,
      type: route.type,
      agencyId: route.agencyId,
      color: route.color,
      textColor: route.textColor,
      description: route.description,
      isActive: route.isActive,
    });
    setSelectedRouteId(route.id);
    setDetailOpen(false);
    setFormKey((k) => k + 1);
    setFormOpen(true);
  }, []);

  const handleDuplicate = useCallback(
    (route: Route) => {
      const now = new Date().toISOString();
      const newRoute: Route = {
        ...route,
        id: `route-dup-${Date.now()}`,
        shortName: `${route.shortName}-copy`,
        createdAt: now,
        updatedAt: now,
      };
      setRoutes((prev) => [...prev, newRoute]);
    },
    [],
  );

  const handleDeleteRequest = useCallback((route: Route) => {
    setDeleteTarget(route);
    setDeleteOpen(true);
  }, []);

  const handleDeleteConfirm = useCallback((routeId: string) => {
    setRoutes((prev) => prev.filter((r) => r.id !== routeId));
    if (selectedRouteId === routeId) {
      setSelectedRouteId(null);
      setDetailOpen(false);
    }
  }, [selectedRouteId]);

  const handleFormSubmit = useCallback(
    (data: RouteFormData) => {
      if (formMode === "create") {
        const now = new Date().toISOString();
        const newRoute: Route = {
          ...data,
          id: `route-new-${Date.now()}`,
          createdAt: now,
          updatedAt: now,
        };
        setRoutes((prev) => [...prev, newRoute]);
      } else if (selectedRouteId) {
        setRoutes((prev) =>
          prev.map((r) =>
            r.id === selectedRouteId
              ? { ...r, ...data, updatedAt: new Date().toISOString() }
              : r,
          ),
        );
      }
    },
    [formMode, selectedRouteId],
  );

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
      {isMobile ? (
        <>
          {/* Mobile filter sheet */}
          <RouteFilters
            search={search}
            onSearchChange={setSearch}
            typeFilter={typeFilter}
            onTypeFilterChange={setTypeFilter}
            statusFilter={statusFilter}
            onStatusFilterChange={setStatusFilter}
            resultCount={filtered.length}
            asSheet
            sheetOpen={filterSheetOpen}
            onSheetOpenChange={setFilterSheetOpen}
          />

          {/* Mobile tabs: Table | Map */}
          <Tabs defaultValue="table" className="flex min-h-0 flex-1 flex-col">
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
                routes={filtered}
                selectedRouteId={selectedRouteId}
                onSelectRoute={handleSelectRoute}
                onEditRoute={handleEdit}
                onDeleteRoute={handleDeleteRequest}
                onDuplicateRoute={handleDuplicate}
                isReadOnly={IS_READ_ONLY}
              />
            </TabsContent>
            <TabsContent value="map" className="min-h-[50vh] flex-1 overflow-hidden rounded-lg border border-border mt-(--spacing-tight)">
              <RouteMap
                buses={filteredVehicles}
                selectedRouteId={selectedRouteId}
                onSelectRoute={handleSelectRoute}
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
                onTypeFilterChange={setTypeFilter}
                statusFilter={statusFilter}
                onStatusFilterChange={setStatusFilter}
                resultCount={filtered.length}
              />
              <RouteTable
                routes={filtered}
                selectedRouteId={selectedRouteId}
                onSelectRoute={handleSelectRoute}
                onEditRoute={handleEdit}
                onDeleteRoute={handleDeleteRequest}
                onDuplicateRoute={handleDuplicate}
                isReadOnly={IS_READ_ONLY}
              />
            </div>
          </ResizablePanel>
          <ResizableHandle withHandle />
          <ResizablePanel defaultSize={40} minSize={25}>
            <RouteMap
              buses={filteredVehicles}
              selectedRouteId={selectedRouteId}
              onSelectRoute={handleSelectRoute}
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
      />

      {/* Form Sheet */}
      <RouteForm
        key={formKey}
        mode={formMode}
        initialData={formInitialData}
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
