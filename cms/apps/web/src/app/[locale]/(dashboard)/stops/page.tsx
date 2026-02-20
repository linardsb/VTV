"use client";

import { useState, useEffect, useMemo, useCallback } from "react";
import dynamic from "next/dynamic";
import { useTranslations } from "next-intl";
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
  createStop,
  updateStop,
  deleteStop,
} from "@/lib/stops-client";
import type { Stop, StopCreate, StopUpdate } from "@/types/stop";

// Simulated role — in production, read from session
const USER_ROLE: string = "admin";
const IS_READ_ONLY = USER_ROLE === "viewer";

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

  // Data state
  const [stops, setStops] = useState<Stop[]>([]);
  const [totalItems, setTotalItems] = useState(0);
  const [page, setPage] = useState(1);
  const [isLoading, setIsLoading] = useState(true);

  // Filter state
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [locationTypeFilter, setLocationTypeFilter] = useState("all");
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

  // Debounced search
  const [debouncedSearch, setDebouncedSearch] = useState("");

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(search);
      setPage(1);
    }, 300);
    return () => clearTimeout(timer);
  }, [search]);

  // Derived: active_only param from statusFilter
  const activeOnlyParam = useMemo(() => {
    if (statusFilter === "active") return true;
    if (statusFilter === "inactive") return false;
    return undefined;
  }, [statusFilter]);

  // Fetch stops
  const loadStops = useCallback(async () => {
    setIsLoading(true);
    try {
      const result = await fetchStops({
        page,
        page_size: PAGE_SIZE,
        search: debouncedSearch || undefined,
        active_only: activeOnlyParam,
      });
      setStops(result.items);
      setTotalItems(result.total);
    } catch {
      setStops([]);
      setTotalItems(0);
    } finally {
      setIsLoading(false);
    }
  }, [page, debouncedSearch, activeOnlyParam]);

  useEffect(() => {
    void loadStops();
  }, [loadStops]);

  // Client-side location type filter
  const displayStops = useMemo(() => {
    if (locationTypeFilter === "all") return stops;
    const typeNum = Number(locationTypeFilter);
    return stops.filter((s) => s.location_type === typeNum);
  }, [stops, locationTypeFilter]);

  // Selected stop ID for map sync
  const selectedStopId = selectedStop?.id ?? null;

  // Handlers
  const handleSelectStop = useCallback((stop: Stop) => {
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
    setDetailOpen(false);
    setFormKey((k) => k + 1);
    setFormOpen(true);
  }, [selectedStop]);

  const handleEditFromTable = useCallback((stop: Stop) => {
    setSelectedStop(stop);
    setFormMode("edit");
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
        void loadStops();
      } catch {
        toast.error(
          formMode === "create" ? t("toast.createError") : t("toast.updateError"),
        );
      }
    },
    [formMode, selectedStop, t, loadStops],
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
    } catch {
      toast.error(t("toast.deleteError"));
    }
  }, [deleteTarget, selectedStop, t, loadStops]);

  const handlePageChange = useCallback((newPage: number) => {
    setPage(newPage);
  }, []);

  // Map click-to-place: set coords and open form
  const handleMapClick = useCallback(
    (lat: number, lon: number) => {
      setDefaultCoords({ lat, lon });
      setPlacementMode(false);
      setFormKey((k) => k + 1);
      setFormOpen(true);
    },
    [],
  );

  // Drag-to-reposition: update stop coordinates via API
  const handleStopMoved = useCallback(
    async (stopId: number, lat: number, lon: number) => {
      try {
        await updateStop(stopId, { stop_lat: lat, stop_lon: lon });
        toast.success(t("toast.moved"));
        void loadStops();
      } catch {
        toast.error(t("toast.updateError"));
        void loadStops(); // reload to revert marker position
      }
    },
    [t, loadStops],
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
          <StopFilters
            search={search}
            onSearchChange={setSearch}
            statusFilter={statusFilter}
            onStatusFilterChange={setStatusFilter}
            locationTypeFilter={locationTypeFilter}
            onLocationTypeFilterChange={setLocationTypeFilter}
            resultCount={displayStops.length}
            asSheet
            sheetOpen={filterSheetOpen}
            onSheetOpenChange={setFilterSheetOpen}
          />

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
              <StopTable
                stops={displayStops}
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
              <StopMap
                stops={displayStops}
                selectedStopId={selectedStopId}
                onSelectStop={handleSelectStop}
                editable={!IS_READ_ONLY}
                onStopMoved={handleStopMoved}
                placementMode={placementMode}
                onMapClick={handleMapClick}
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
              <StopFilters
                search={search}
                onSearchChange={setSearch}
                statusFilter={statusFilter}
                onStatusFilterChange={setStatusFilter}
                locationTypeFilter={locationTypeFilter}
                onLocationTypeFilterChange={setLocationTypeFilter}
                resultCount={displayStops.length}
              />
              <StopTable
                stops={displayStops}
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
          </ResizablePanel>
          <ResizableHandle withHandle />
          <ResizablePanel defaultSize={40} minSize={25}>
            <StopMap
              stops={displayStops}
              selectedStopId={selectedStopId}
              onSelectStop={handleSelectStop}
              editable={!IS_READ_ONLY}
              onStopMoved={handleStopMoved}
              placementMode={placementMode}
              onMapClick={handleMapClick}
            />
          </ResizablePanel>
        </ResizablePanelGroup>
      )}

      {/* Detail Sheet */}
      <StopDetail
        stop={selectedStop}
        open={detailOpen}
        onOpenChange={(open) => {
          setDetailOpen(open);
          if (!open) setSelectedStop(null);
        }}
        onEdit={handleEdit}
        onDelete={handleDeleteFromDetail}
        isReadOnly={IS_READ_ONLY}
      />

      {/* Form Sheet */}
      <StopForm
        key={formKey}
        mode={formMode}
        stop={selectedStop}
        open={formOpen}
        onOpenChange={(open) => {
          setFormOpen(open);
          if (!open) {
            setPlacementMode(false);
            setDefaultCoords(null);
          }
        }}
        onSubmit={handleFormSubmit}
        defaultCoords={defaultCoords}
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
