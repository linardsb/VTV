"use client";

import { useState, useCallback, useEffect } from "react";
import { useSession } from "next-auth/react";
import { useTranslations } from "next-intl";
import { Plus, Filter } from "lucide-react";
import { toast } from "sonner";
import { useIsMobile } from "@/hooks/use-mobile";
import { Button } from "@/components/ui/button";
import { FleetDevicesTable } from "@/components/fleet/fleet-devices-table";
import { FleetDevicesFilters } from "@/components/fleet/fleet-devices-filters";
import { FleetDeviceForm } from "@/components/fleet/fleet-device-form";
import { FleetDeviceDetail } from "@/components/fleet/fleet-device-detail";
import { DeleteFleetDeviceDialog } from "@/components/fleet/delete-fleet-device-dialog";
import {
  fetchDevices,
  createDevice,
  updateDevice,
  deleteDevice,
} from "@/lib/fleet-sdk";
import type {
  TrackedDevice,
  TrackedDeviceCreate,
  TrackedDeviceUpdate,
} from "@/types/fleet";

const PAGE_SIZE = 20;

export default function FleetDevicesPage() {
  const { data: session, status } = useSession();
  const t = useTranslations("fleet");
  const isMobile = useIsMobile();

  const userRole: string = session?.user?.role ?? "viewer";
  const IS_READ_ONLY = userRole === "viewer";
  const CAN_EDIT = userRole === "admin" || userRole === "editor";
  const CAN_DELETE = userRole === "admin";

  // Data state
  const [devices, setDevices] = useState<TrackedDevice[]>([]);
  const [totalItems, setTotalItems] = useState(0);
  const [page, setPage] = useState(1);
  const [isLoading, setIsLoading] = useState(true);

  // Filter state
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [protocolFilter, setProtocolFilter] = useState("all");
  const [linkFilter, setLinkFilter] = useState("all");

  // UI state
  const [selectedDevice, setSelectedDevice] = useState<TrackedDevice | null>(null);
  const [detailOpen, setDetailOpen] = useState(false);
  const [formOpen, setFormOpen] = useState(false);
  const [formMode, setFormMode] = useState<"create" | "edit">("create");
  const [formKey, setFormKey] = useState(0);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<TrackedDevice | null>(null);
  const [filterSheetOpen, setFilterSheetOpen] = useState(false);

  // Debounce search
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(search);
      setPage(1);
    }, 300);
    return () => clearTimeout(timer);
  }, [search]);

  const loadDevices = useCallback(async () => {
    setIsLoading(true);
    try {
      const result = await fetchDevices({
        page,
        page_size: PAGE_SIZE,
        search: debouncedSearch || undefined,
        status: statusFilter !== "all" ? statusFilter : undefined,
        vehicle_linked: linkFilter !== "all" ? linkFilter : undefined,
      });
      setDevices(result.items);
      setTotalItems(result.total);
    } catch {
      toast.error(t("toast.loadError"));
    } finally {
      setIsLoading(false);
    }
  }, [page, debouncedSearch, statusFilter, linkFilter, t]);

  useEffect(() => {
    if (status !== "authenticated") return;
    void loadDevices();
  }, [loadDevices, status]);

  const handleSelectDevice = (device: TrackedDevice) => {
    setSelectedDevice(device);
    setDetailOpen(true);
  };

  const handleCreateClick = () => {
    setSelectedDevice(null);
    setFormMode("create");
    setFormKey((prev) => prev + 1);
    setFormOpen(true);
  };

  const handleEditDevice = (device: TrackedDevice) => {
    setSelectedDevice(device);
    setFormMode("edit");
    setFormKey((prev) => prev + 1);
    setFormOpen(true);
    setDetailOpen(false);
  };

  const handleDeleteDevice = (device: TrackedDevice) => {
    setDeleteTarget(device);
    setDeleteOpen(true);
    setDetailOpen(false);
  };

  const handleFormSubmit = async (
    data: TrackedDeviceCreate | TrackedDeviceUpdate,
  ) => {
    try {
      if (formMode === "create") {
        await createDevice(data as TrackedDeviceCreate);
        toast.success(t("toast.created"));
      } else if (selectedDevice) {
        await updateDevice(selectedDevice.id, data as TrackedDeviceUpdate);
        toast.success(t("toast.updated"));
      }
      setFormOpen(false);
      void loadDevices();
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
      await deleteDevice(deleteTarget.id);
      toast.success(t("toast.deleted"));
      setDeleteOpen(false);
      setDeleteTarget(null);
      void loadDevices();
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
            <Button
              variant="outline"
              size="sm"
              className="cursor-pointer"
              onClick={() => setFilterSheetOpen(true)}
            >
              <Filter className="mr-1 size-4" />
              {t("mobile.showFilters")}
            </Button>
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
        {!isMobile && (
          <FleetDevicesFilters
            search={search}
            onSearchChange={setSearch}
            statusFilter={statusFilter}
            onStatusFilterChange={(v) => {
              setStatusFilter(v);
              setPage(1);
            }}
            protocolFilter={protocolFilter}
            onProtocolFilterChange={(v) => {
              setProtocolFilter(v);
              setPage(1);
            }}
            linkFilter={linkFilter}
            onLinkFilterChange={(v) => {
              setLinkFilter(v);
              setPage(1);
            }}
            resultCount={totalItems}
          />
        )}
        {isMobile && (
          <FleetDevicesFilters
            asSheet
            sheetOpen={filterSheetOpen}
            onSheetOpenChange={setFilterSheetOpen}
            search={search}
            onSearchChange={setSearch}
            statusFilter={statusFilter}
            onStatusFilterChange={(v) => {
              setStatusFilter(v);
              setPage(1);
            }}
            protocolFilter={protocolFilter}
            onProtocolFilterChange={(v) => {
              setProtocolFilter(v);
              setPage(1);
            }}
            linkFilter={linkFilter}
            onLinkFilterChange={(v) => {
              setLinkFilter(v);
              setPage(1);
            }}
            resultCount={totalItems}
          />
        )}

        <div className="flex flex-1 flex-col overflow-hidden">
          <FleetDevicesTable
            devices={devices}
            totalItems={totalItems}
            page={page}
            pageSize={PAGE_SIZE}
            onPageChange={setPage}
            selectedDevice={selectedDevice}
            onSelectDevice={handleSelectDevice}
            onEditDevice={handleEditDevice}
            onDeleteDevice={handleDeleteDevice}
            isLoading={isLoading}
            isReadOnly={IS_READ_ONLY}
            canDelete={CAN_DELETE}
          />
        </div>
      </div>

      {/* Dialogs */}
      <FleetDeviceDetail
        device={selectedDevice}
        open={detailOpen}
        onOpenChange={setDetailOpen}
        onEdit={() => {
          if (selectedDevice) handleEditDevice(selectedDevice);
        }}
        onDelete={() => {
          if (selectedDevice) handleDeleteDevice(selectedDevice);
        }}
        isReadOnly={!CAN_EDIT}
        canDelete={CAN_DELETE}
      />

      <FleetDeviceForm
        key={`device-form-${formKey}`}
        mode={formMode}
        device={formMode === "edit" ? selectedDevice : null}
        open={formOpen}
        onOpenChange={setFormOpen}
        onSubmit={handleFormSubmit}
      />

      <DeleteFleetDeviceDialog
        device={deleteTarget}
        open={deleteOpen}
        onOpenChange={setDeleteOpen}
        onConfirm={handleDeleteConfirm}
      />
    </div>
  );
}
