"use client";

import { useState, useEffect, useMemo, useCallback } from "react";
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
import { StopFilters } from "@/components/stops/stop-filters";
import { StopTable } from "@/components/stops/stop-table";
import { StopDetail } from "@/components/stops/stop-detail";
import { StopForm } from "@/components/stops/stop-form";
import { DeleteStopDialog } from "@/components/stops/delete-stop-dialog";
import {
  fetchStops,
  fetchAllStopsForMap,
  fetchTerminalStopIds,
  createStop,
  updateStop,
  deleteStop,
} from "@/lib/stops-sdk";
import type { Stop, StopCreate, StopUpdate } from "@/types/stop";

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

const StopMap = dynamic(
  () => import("@/components/stops/stop-map").then((m) => ({ default: m.StopMap })),
  { ssr: false, loading: () => <MapSkeleton /> },
);

export default function StopsPage() {
  const t = useTranslations("stops");
  const isMobile = useIsMobile();
  const { data: session, status } = useSession();
  const userRole = session?.user?.role ?? "viewer";
  const IS_READ_ONLY = userRole === "viewer";

  // Data state — table (paginated) and map (all stops)
  const [stops, setStops] = useState<Stop[]>([]);
  const [allStops, setAllStops] = useState<Stop[]>([]);
  const [terminalStopIds, setTerminalStopIds] = useState<Set<number>>(new Set());
  const [totalItems, setTotalItems] = useState(0);
  const [page, setPage] = useState(1);
  const [isLoading, setIsLoading] = useState(true);

  // Filter state
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [locationTypeFilter, setLocationTypeFilterRaw] = useState("all");
  const [filterSheetOpen, setFilterSheetOpen] = useState(false);

  // UI state
  const [selectedStop, setSelectedStop] = useState<Stop | null>(null);
  const [detailOpen, setDetailOpen] = useState(false);
  const [formOpen, setFormOpen] = useState(false);
  const [formMode, setFormMode] = useState<"create" | "edit">("create");
  const [formKey, setFormKey] = useState(0);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<Stop | null>(null);
  const [placementMode, setPlacementMode] = useState(false);
  const [defaultCoords, setDefaultCoords] = useState<{ lat: number; lon: number } | null>(null);

  // Editing state — map-form coordinate sync
  const [editingStopId, setEditingStopId] = useState<number | null>(null);
  const [editingCoords, setEditingCoords] = useState<{ lat: number; lon: number } | null>(null);

  // Popup trigger — incremented when table row is clicked to tell map to open the popup
  const [popupTrigger, setPopupTrigger] = useState(0);

  // Debounced search
  // Wrap filter setters to reset page on filter change
  const setLocationTypeFilter = useCallback((value: string) => {
    setLocationTypeFilterRaw(value);
    setPage(1);
  }, []);

  const [debouncedSearch, setDebouncedSearch] = useState("");

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(search);
      setPage(1);
    }, 300);
    return () => clearTimeout(timer);
  }, [search]);

  // Derived: active_only param from statusFilter
  // "all" sends false to override backend default (active_only=True)
  const activeOnlyParam = useMemo(() => {
    if (statusFilter === "active") return true;
    return false;
  }, [statusFilter]);

  // Derived: location_type param from locationTypeFilter
  // "terminal" is a frontend-only filter — don't send it to the paginated list API
  const locationTypeParam = useMemo(() => {
    if (locationTypeFilter === "all" || locationTypeFilter === "terminal") return undefined;
    return Number(locationTypeFilter);
  }, [locationTypeFilter]);

  // Fetch paginated stops for the table
  const loadStops = useCallback(async () => {
    setIsLoading(true);
    try {
      const result = await fetchStops({
        page,
        page_size: PAGE_SIZE,
        search: debouncedSearch || undefined,
        active_only: activeOnlyParam,
        location_type: locationTypeParam,
      });
      setStops(result.items);
      setTotalItems(result.total);
    } catch (e) {
      console.warn("[stops] Failed to load stops:", e);
      setStops([]);
      setTotalItems(0);
    } finally {
      setIsLoading(false);
    }
  }, [page, debouncedSearch, activeOnlyParam, locationTypeParam]);

  // Fetch all stops for the map (single unpaginated request)
  const loadAllStops = useCallback(async () => {
    try {
      const stops = await fetchAllStopsForMap();
      setAllStops(stops);
    } catch (e) {
      console.warn("[stops] Failed to load all stops:", e);
      setAllStops([]);
    }
  }, []);

  // Fetch terminal stop IDs (last stop of each trip)
  const loadTerminalStopIds = useCallback(async () => {
    try {
      const ids = await fetchTerminalStopIds();
      setTerminalStopIds(new Set(ids));
    } catch (e) {
      console.warn("[stops] Failed to load terminal stop IDs:", e);
      setTerminalStopIds(new Set());
    }
  }, []);

  useEffect(() => {
    if (status !== "authenticated") return;
    void loadStops();
  }, [loadStops, status]);

  useEffect(() => {
    if (status !== "authenticated") return;
    void loadAllStops();
    void loadTerminalStopIds();
  }, [loadAllStops, loadTerminalStopIds, status]);

  // Selected stop ID for map sync
  const selectedStopId = selectedStop?.id ?? null;

  // Handlers
  const handleSelectStop = useCallback((stop: Stop) => {
    setSelectedStop(stop);
    setDetailOpen(true);
    setPopupTrigger((n) => n + 1);
  }, []);

  // Called from popup "Details" button — opens the detail Sheet
  const handleViewDetail = useCallback((stop: Stop) => {
    setSelectedStop(stop);
    setDetailOpen(true);
  }, []);

  const handleCreate = useCallback(() => {
    setFormMode("create");
    setSelectedStop(null);
    setDefaultCoords(null);
    setPlacementMode(true);
  }, []);

  const handleEdit = useCallback(() => {
    if (!selectedStop) return;
    setFormMode("edit");
    setEditingStopId(selectedStop.id);
    setEditingCoords(
      selectedStop.stop_lat !== null && selectedStop.stop_lon !== null
        ? { lat: selectedStop.stop_lat, lon: selectedStop.stop_lon }
        : null,
    );
    setDetailOpen(false);
    setFormKey((k) => k + 1);
    setFormOpen(true);
  }, [selectedStop]);

  const handleEditFromTable = useCallback((stop: Stop) => {
    setSelectedStop(stop);
    setFormMode("edit");
    setEditingStopId(stop.id);
    setEditingCoords(
      stop.stop_lat !== null && stop.stop_lon !== null
        ? { lat: stop.stop_lat, lon: stop.stop_lon }
        : null,
    );
    setDetailOpen(false);
    setFormKey((k) => k + 1);
    setFormOpen(true);
  }, []);

  const handleDeleteRequest = useCallback((stop: Stop) => {
    setDeleteTarget(stop);
    setDeleteOpen(true);
  }, []);

  const handleDeleteFromDetail = useCallback(() => {
    if (!selectedStop) return;
    setDeleteTarget(selectedStop);
    setDetailOpen(false);
    setDeleteOpen(true);
  }, [selectedStop]);

  const handleFormSubmit = useCallback(
    async (data: StopCreate | StopUpdate) => {
      try {
        if (formMode === "create") {
          await createStop(data as StopCreate);
          toast.success(t("toast.created"));
        } else if (selectedStop) {
          await updateStop(selectedStop.id, data as StopUpdate);
          toast.success(t("toast.updated"));
        }
        setFormOpen(false);
        setEditingStopId(null);
        setEditingCoords(null);
        void loadStops();
        void loadAllStops();
      } catch {
        toast.error(
          formMode === "create" ? t("toast.createError") : t("toast.updateError"),
        );
      }
    },
    [formMode, selectedStop, t, loadStops, loadAllStops],
  );

  const handleDeleteConfirm = useCallback(async () => {
    if (!deleteTarget) return;
    try {
      await deleteStop(deleteTarget.id);
      toast.success(t("toast.deleted"));
      if (selectedStop?.id === deleteTarget.id) {
        setSelectedStop(null);
        setDetailOpen(false);
      }
      void loadStops();
      void loadAllStops();
    } catch {
      toast.error(t("toast.deleteError"));
    }
  }, [deleteTarget, selectedStop, t, loadStops, loadAllStops]);

  const handlePageChange = useCallback((newPage: number) => {
    setPage(newPage);
  }, []);

  // Map click-to-place: set coords and open form
  const handleMapClick = useCallback(
    (lat: number, lon: number) => {
      setDefaultCoords({ lat, lon });
      setEditingCoords({ lat, lon });
      setEditingStopId(null);
      setPlacementMode(false);
      setFormKey((k) => k + 1);
      setFormOpen(true);
    },
    [],
  );

  // Map editing marker dragged — update form coords (NOT the API)
  const handleEditingCoordsChange = useCallback(
    (lat: number, lon: number) => {
      setEditingCoords({ lat, lon });
    },
    [],
  );

  // Form coordinate fields changed — update map marker
  const handleFormCoordsChange = useCallback(
    (lat: number, lon: number) => {
      setEditingCoords({ lat, lon });
    },
    [],
  );

  // Clear editing state when form closes
  const handleFormOpenChange = useCallback(
    (open: boolean) => {
      setFormOpen(open);
      if (!open) {
        setPlacementMode(false);
        setDefaultCoords(null);
        setEditingStopId(null);
        setEditingCoords(null);
        setDetailOpen(false);
      }
    },
    [],
  );

  // Shared StopMap props — map shows ALL stops, not just the current page
  const mapProps = {
    stops: allStops,
    selectedStopId,
    onSelectStop: handleSelectStop,
    onViewDetail: handleViewDetail,
    onEditStop: IS_READ_ONLY ? undefined : handleEditFromTable,
    placementMode,
    onMapClick: handleMapClick,
    editingStopId,
    editingCoords,
    onEditingCoordsChange: handleEditingCoordsChange,
    locationTypeFilter,
    terminalStopIds,
    popupTrigger,
  };

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
          <StopFilters
            search={search}
            onSearchChange={setSearch}
            statusFilter={statusFilter}
            onStatusFilterChange={setStatusFilter}
            locationTypeFilter={locationTypeFilter}
            onLocationTypeFilterChange={setLocationTypeFilter}
            resultCount={stops.length}
            asSheet
            sheetOpen={filterSheetOpen}
            onSheetOpenChange={setFilterSheetOpen}
          />

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
              <StopTable
                stops={stops}
                total={totalItems}
                page={page}
                pageSize={PAGE_SIZE}
                onPageChange={handlePageChange}
                selectedStopId={selectedStopId}
                onSelectStop={handleSelectStop}
                onEditStop={handleEditFromTable}
                onDeleteStop={handleDeleteRequest}
                isReadOnly={IS_READ_ONLY}
                isLoading={isLoading}
              />
            </TabsContent>
            <TabsContent value="map" className="min-h-[50vh] flex-1 overflow-hidden rounded-lg border border-border mt-(--spacing-tight)">
              <StopMap {...mapProps} />
            </TabsContent>
          </Tabs>

          {/* Mobile: Form as Sheet overlay */}
          <StopForm
            key={formKey}
            mode={formMode}
            stop={selectedStop}
            open={formOpen}
            onOpenChange={handleFormOpenChange}
            onSubmit={handleFormSubmit}
            defaultCoords={defaultCoords}
            onCoordsChange={handleFormCoordsChange}
            externalCoords={editingCoords}
          />
        </>
      ) : (
        <>
          {/* Desktop: Resizable panels — no key change to keep Leaflet map alive */}
          <ResizablePanelGroup
            orientation="horizontal"
            className="min-h-0 flex-1 overflow-hidden rounded-lg border border-border"
          >
            <ResizablePanel defaultSize={55} minSize={25}>
              {formOpen ? (
                <StopForm
                  key={formKey}
                  mode={formMode}
                  stop={selectedStop}
                  open={formOpen}
                  onOpenChange={handleFormOpenChange}
                  onSubmit={handleFormSubmit}
                  defaultCoords={defaultCoords}
                  onCoordsChange={handleFormCoordsChange}
                  externalCoords={editingCoords}
                  inline
                />
              ) : (
                <div className="flex h-full">
                  <StopFilters
                    search={search}
                    onSearchChange={setSearch}
                    statusFilter={statusFilter}
                    onStatusFilterChange={setStatusFilter}
                    locationTypeFilter={locationTypeFilter}
                    onLocationTypeFilterChange={setLocationTypeFilter}
                    resultCount={stops.length}
                  />
                  <StopTable
                    stops={stops}
                    total={totalItems}
                    page={page}
                    pageSize={PAGE_SIZE}
                    onPageChange={handlePageChange}
                    selectedStopId={selectedStopId}
                    onSelectStop={handleSelectStop}
                    onEditStop={handleEditFromTable}
                    onDeleteStop={handleDeleteRequest}
                    isReadOnly={IS_READ_ONLY}
                    isLoading={isLoading}
                  />
                </div>
              )}
            </ResizablePanel>
            <ResizableHandle withHandle />
            <ResizablePanel defaultSize={45} minSize={25}>
              <StopMap {...mapProps} />
            </ResizablePanel>
          </ResizablePanelGroup>
        </>
      )}

      {/* Detail Sheet — hidden when edit form is open to prevent overlap */}
      <StopDetail
        stop={selectedStop}
        open={detailOpen && !formOpen}
        onOpenChange={(open) => {
          setDetailOpen(open);
          if (!open) setSelectedStop(null);
        }}
        onEdit={handleEdit}
        onDelete={handleDeleteFromDetail}
        isReadOnly={IS_READ_ONLY}
      />

      {/* Delete Dialog */}
      <DeleteStopDialog
        stop={deleteTarget}
        open={deleteOpen}
        onOpenChange={setDeleteOpen}
        onConfirm={handleDeleteConfirm}
      />
    </div>
  );
}
