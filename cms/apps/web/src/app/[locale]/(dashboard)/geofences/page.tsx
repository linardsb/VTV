"use client";

import { useState, useCallback, useEffect } from "react";
import { useSession } from "next-auth/react";
import { useTranslations } from "next-intl";
import { Plus, Filter } from "lucide-react";
import { toast } from "sonner";
import dynamic from "next/dynamic";
import { useIsMobile } from "@/hooks/use-mobile";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { GeofencesTable } from "@/components/geofences/geofences-table";
import { GeofencesFilters } from "@/components/geofences/geofences-filters";
import { GeofenceForm } from "@/components/geofences/geofence-form";
import { GeofenceDetail } from "@/components/geofences/geofence-detail";
import { DeleteGeofenceDialog } from "@/components/geofences/delete-geofence-dialog";
import {
  fetchGeofences,
  createGeofence,
  updateGeofence,
  deleteGeofence,
} from "@/lib/geofences-sdk";
import type {
  Geofence,
  GeofenceCreate,
  GeofenceUpdate,
} from "@/types/geofence";

const GeofenceMap = dynamic(
  () =>
    import("@/components/geofences/geofence-map").then((m) => m.GeofenceMap),
  {
    ssr: false,
    loading: () => <Skeleton className="h-full w-full" />,
  },
);

const PAGE_SIZE = 20;

export default function GeofencesPage() {
  const { data: session, status } = useSession();
  const t = useTranslations("geofences");
  const isMobile = useIsMobile();

  const userRole: string = session?.user?.role ?? "viewer";
  const IS_READ_ONLY = userRole === "viewer";
  const CAN_EDIT = userRole === "admin" || userRole === "editor";
  const CAN_DELETE = userRole === "admin";

  // Data state
  const [geofences, setGeofences] = useState<Geofence[]>([]);
  const [totalItems, setTotalItems] = useState(0);
  const [page, setPage] = useState(1);
  const [isLoading, setIsLoading] = useState(true);

  // Filter state
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [zoneTypeFilter, setZoneTypeFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");

  // UI state
  const [selectedGeofence, setSelectedGeofence] = useState<Geofence | null>(null);
  const [detailOpen, setDetailOpen] = useState(false);
  const [formOpen, setFormOpen] = useState(false);
  const [formMode, setFormMode] = useState<"create" | "edit">("create");
  const [formKey, setFormKey] = useState(0);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<Geofence | null>(null);
  const [filterSheetOpen, setFilterSheetOpen] = useState(false);
  const [mobileView, setMobileView] = useState<"list" | "map">("list");

  // Debounce search
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(search);
      setPage(1);
    }, 300);
    return () => clearTimeout(timer);
  }, [search]);

  const loadGeofences = useCallback(async () => {
    setIsLoading(true);
    try {
      const isActive =
        statusFilter === "active"
          ? true
          : statusFilter === "inactive"
            ? false
            : undefined;
      const result = await fetchGeofences({
        page,
        page_size: PAGE_SIZE,
        search: debouncedSearch || undefined,
        zone_type: zoneTypeFilter !== "all" ? zoneTypeFilter : undefined,
        is_active: isActive,
      });
      setGeofences(result.items);
      setTotalItems(result.total);
    } catch {
      toast.error(t("toast.loadError"));
    } finally {
      setIsLoading(false);
    }
  }, [page, debouncedSearch, zoneTypeFilter, statusFilter, t]);

  useEffect(() => {
    if (status !== "authenticated") return;
    void loadGeofences();
  }, [loadGeofences, status]);

  const handleSelectGeofence = (geofence: Geofence) => {
    setSelectedGeofence(geofence);
    setDetailOpen(true);
  };

  const handleSelectGeofenceById = (id: number) => {
    const geofence = geofences.find((g) => g.id === id);
    if (geofence) {
      setSelectedGeofence(geofence);
      setDetailOpen(true);
    }
  };

  const handleCreateClick = () => {
    setSelectedGeofence(null);
    setFormMode("create");
    setFormKey((prev) => prev + 1);
    setFormOpen(true);
  };

  const handleEditGeofence = (geofence: Geofence) => {
    setSelectedGeofence(geofence);
    setFormMode("edit");
    setFormKey((prev) => prev + 1);
    setFormOpen(true);
    setDetailOpen(false);
  };

  const handleDeleteGeofence = (geofence: Geofence) => {
    setDeleteTarget(geofence);
    setDeleteOpen(true);
    setDetailOpen(false);
  };

  const handleFormSubmit = async (
    data: GeofenceCreate | GeofenceUpdate,
  ) => {
    try {
      if (formMode === "create") {
        await createGeofence(data as GeofenceCreate);
        toast.success(t("toast.created"));
      } else if (selectedGeofence) {
        await updateGeofence(selectedGeofence.id, data as GeofenceUpdate);
        toast.success(t("toast.updated"));
      }
      setFormOpen(false);
      void loadGeofences();
    } catch {
      toast.error(
        formMode === "create"
          ? t("toast.createError")
          : t("toast.updateError"),
      );
    }
  };

  const handleDeleteConfirm = async () => {
    if (!deleteTarget) return;
    try {
      await deleteGeofence(deleteTarget.id);
      toast.success(t("toast.deleted"));
      setDeleteOpen(false);
      setDeleteTarget(null);
      void loadGeofences();
    } catch {
      toast.error(t("toast.deleteError"));
    }
  };

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border px-(--spacing-page) py-(--spacing-card)">
        <div>
          <h1 className="text-lg font-heading font-semibold text-foreground">
            {t("title")}
          </h1>
          <p className="text-sm text-foreground-muted">{t("description")}</p>
        </div>
        <div className="flex items-center gap-2">
          {isMobile && (
            <>
              <Button
                variant="outline"
                size="sm"
                className="cursor-pointer"
                onClick={() => setFilterSheetOpen(true)}
              >
                <Filter className="mr-1 size-4" />
                {t("mobile.showFilters")}
              </Button>
              <Button
                variant="outline"
                size="sm"
                className="cursor-pointer"
                onClick={() =>
                  setMobileView(mobileView === "list" ? "map" : "list")
                }
              >
                {mobileView === "list"
                  ? t("mobile.showMap")
                  : t("mobile.showList")}
              </Button>
            </>
          )}
          {CAN_EDIT && (
            <Button
              size="sm"
              className="cursor-pointer"
              onClick={handleCreateClick}
            >
              <Plus className="mr-1 size-4" />
              {t("actions.create")}
            </Button>
          )}
        </div>
      </div>

      {/* Content */}
      <div className="flex flex-1 overflow-hidden">
        {/* Desktop: filters + table + map split */}
        {!isMobile && (
          <>
            <GeofencesFilters
              search={search}
              onSearchChange={setSearch}
              zoneTypeFilter={zoneTypeFilter}
              onZoneTypeFilterChange={(v) => {
                setZoneTypeFilter(v);
                setPage(1);
              }}
              statusFilter={statusFilter}
              onStatusFilterChange={(v) => {
                setStatusFilter(v);
                setPage(1);
              }}
              resultCount={totalItems}
            />
            <div className="flex flex-1 overflow-hidden">
              <div className="w-1/2 flex flex-col overflow-hidden border-r border-border">
                <GeofencesTable
                  geofences={geofences}
                  totalItems={totalItems}
                  page={page}
                  pageSize={PAGE_SIZE}
                  onPageChange={setPage}
                  selectedGeofence={selectedGeofence}
                  onSelectGeofence={handleSelectGeofence}
                  onEditGeofence={handleEditGeofence}
                  onDeleteGeofence={handleDeleteGeofence}
                  isLoading={isLoading}
                  isReadOnly={IS_READ_ONLY}
                  canDelete={CAN_DELETE}
                />
              </div>
              <div className="w-1/2">
                <GeofenceMap
                  geofences={geofences}
                  selectedGeofenceId={selectedGeofence?.id ?? null}
                  onSelectGeofence={handleSelectGeofenceById}
                />
              </div>
            </div>
          </>
        )}

        {/* Mobile: stacked layout */}
        {isMobile && (
          <>
            <GeofencesFilters
              asSheet
              sheetOpen={filterSheetOpen}
              onSheetOpenChange={setFilterSheetOpen}
              search={search}
              onSearchChange={setSearch}
              zoneTypeFilter={zoneTypeFilter}
              onZoneTypeFilterChange={(v) => {
                setZoneTypeFilter(v);
                setPage(1);
              }}
              statusFilter={statusFilter}
              onStatusFilterChange={(v) => {
                setStatusFilter(v);
                setPage(1);
              }}
              resultCount={totalItems}
            />
            <div className="flex flex-1 flex-col overflow-hidden">
              {mobileView === "map" ? (
                <div className="flex-1 min-h-[50vh]">
                  <GeofenceMap
                    geofences={geofences}
                    selectedGeofenceId={selectedGeofence?.id ?? null}
                    onSelectGeofence={handleSelectGeofenceById}
                  />
                </div>
              ) : (
                <GeofencesTable
                  geofences={geofences}
                  totalItems={totalItems}
                  page={page}
                  pageSize={PAGE_SIZE}
                  onPageChange={setPage}
                  selectedGeofence={selectedGeofence}
                  onSelectGeofence={handleSelectGeofence}
                  onEditGeofence={handleEditGeofence}
                  onDeleteGeofence={handleDeleteGeofence}
                  isLoading={isLoading}
                  isReadOnly={IS_READ_ONLY}
                  canDelete={CAN_DELETE}
                />
              )}
            </div>
          </>
        )}
      </div>

      {/* Dialogs */}
      <GeofenceDetail
        geofence={selectedGeofence}
        open={detailOpen}
        onOpenChange={setDetailOpen}
        onEdit={() => {
          if (selectedGeofence) handleEditGeofence(selectedGeofence);
        }}
        onDelete={() => {
          if (selectedGeofence) handleDeleteGeofence(selectedGeofence);
        }}
        isReadOnly={!CAN_EDIT}
        canDelete={CAN_DELETE}
      />

      <GeofenceForm
        key={`geofence-form-${formKey}`}
        mode={formMode}
        geofence={formMode === "edit" ? selectedGeofence : null}
        open={formOpen}
        onOpenChange={setFormOpen}
        onSubmit={handleFormSubmit}
      />

      <DeleteGeofenceDialog
        geofence={deleteTarget}
        open={deleteOpen}
        onOpenChange={setDeleteOpen}
        onConfirm={handleDeleteConfirm}
      />
    </div>
  );
}
