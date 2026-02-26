"use client";

import { useState, useEffect, useCallback } from "react";
import { useTranslations } from "next-intl";
import { useSession } from "next-auth/react";
import { Plus, Filter } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { useIsMobile } from "@/hooks/use-mobile";
import { DriverFilters } from "@/components/drivers/driver-filters";
import { DriverTable } from "@/components/drivers/driver-table";
import { DriverDetail } from "@/components/drivers/driver-detail";
import { DriverForm } from "@/components/drivers/driver-form";
import { DeleteDriverDialog } from "@/components/drivers/delete-driver-dialog";
import {
  fetchDrivers,
  createDriver,
  updateDriver,
  deleteDriver,
} from "@/lib/drivers-sdk";
import type { Driver, DriverCreate, DriverUpdate } from "@/types/driver";

const PAGE_SIZE = 20;

export default function DriversPage() {
  const t = useTranslations("drivers");
  const isMobile = useIsMobile();
  const { data: session, status } = useSession();
  const userRole = session?.user?.role ?? "viewer";
  const IS_READ_ONLY = userRole === "viewer";

  // Data state
  const [drivers, setDrivers] = useState<Driver[]>([]);
  const [totalItems, setTotalItems] = useState(0);
  const [page, setPage] = useState(1);
  const [isLoading, setIsLoading] = useState(true);

  // Filter state
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [shiftFilter, setShiftFilter] = useState("all");
  const [filterSheetOpen, setFilterSheetOpen] = useState(false);

  // UI state
  const [selectedDriver, setSelectedDriver] = useState<Driver | null>(null);
  const [detailOpen, setDetailOpen] = useState(false);
  const [formOpen, setFormOpen] = useState(false);
  const [formMode, setFormMode] = useState<"create" | "edit">("create");
  const [formKey, setFormKey] = useState(0);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<Driver | null>(null);

  // Debounced search
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(search);
      setPage(1);
    }, 300);
    return () => clearTimeout(timer);
  }, [search]);

  // Load data
  const loadDrivers = useCallback(async () => {
    setIsLoading(true);
    try {
      const result = await fetchDrivers({
        page,
        page_size: PAGE_SIZE,
        search: debouncedSearch || undefined,
        active_only: true,
        status: statusFilter !== "all" ? statusFilter : undefined,
        shift: shiftFilter !== "all" ? shiftFilter : undefined,
      });
      setDrivers(result.items);
      setTotalItems(result.total);
    } catch (e) {
      console.warn("[drivers] Failed to load:", e);
      toast.error(t("toast.loadError"));
    } finally {
      setIsLoading(false);
    }
  }, [page, debouncedSearch, statusFilter, shiftFilter, t]);

  useEffect(() => {
    if (status !== "authenticated") return;
    void loadDrivers();
  }, [loadDrivers, status]);

  // Handlers
  const handleSelectDriver = (driver: Driver) => {
    setSelectedDriver(driver);
    setDetailOpen(true);
  };

  const handleCreateClick = () => {
    setSelectedDriver(null);
    setFormMode("create");
    setFormKey((prev) => prev + 1);
    setFormOpen(true);
  };

  const handleEditDriver = (driver: Driver) => {
    setSelectedDriver(driver);
    setFormMode("edit");
    setFormKey((prev) => prev + 1);
    setFormOpen(true);
    setDetailOpen(false);
  };

  const handleDeleteDriver = (driver: Driver) => {
    setDeleteTarget(driver);
    setDeleteOpen(true);
    setDetailOpen(false);
  };

  const handleFormSubmit = async (data: DriverCreate | DriverUpdate) => {
    try {
      if (formMode === "create") {
        await createDriver(data as DriverCreate);
        toast.success(t("toast.created"));
      } else if (selectedDriver) {
        await updateDriver(selectedDriver.id, data as DriverUpdate);
        toast.success(t("toast.updated"));
      }
      setFormOpen(false);
      void loadDrivers();
    } catch {
      toast.error(
        formMode === "create" ? t("toast.createError") : t("toast.updateError"),
      );
    }
  };

  const handleDeleteConfirm = async () => {
    if (!deleteTarget) return;
    try {
      await deleteDriver(deleteTarget.id);
      toast.success(t("toast.deleted"));
      setDeleteTarget(null);
      if (selectedDriver?.id === deleteTarget.id) {
        setSelectedDriver(null);
        setDetailOpen(false);
      }
      void loadDrivers();
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
              onClick={() => setFilterSheetOpen(true)}
            >
              <Filter className="mr-1 size-4" />
              {t("mobile.showFilters")}
            </Button>
          )}
          {!IS_READ_ONLY && (
            <Button size="sm" onClick={handleCreateClick}>
              <Plus className="mr-1 size-4" />
              {t("actions.create")}
            </Button>
          )}
        </div>
      </div>

      {/* Content */}
      <div className="flex flex-1 overflow-hidden">
        {/* Desktop filters */}
        {!isMobile && (
          <DriverFilters
            search={search}
            onSearchChange={setSearch}
            statusFilter={statusFilter}
            onStatusFilterChange={(v) => { setStatusFilter(v); setPage(1); }}
            shiftFilter={shiftFilter}
            onShiftFilterChange={(v) => { setShiftFilter(v); setPage(1); }}
            resultCount={totalItems}
          />
        )}

        {/* Mobile filter sheet */}
        {isMobile && (
          <DriverFilters
            asSheet
            sheetOpen={filterSheetOpen}
            onSheetOpenChange={setFilterSheetOpen}
            search={search}
            onSearchChange={setSearch}
            statusFilter={statusFilter}
            onStatusFilterChange={(v) => { setStatusFilter(v); setPage(1); }}
            shiftFilter={shiftFilter}
            onShiftFilterChange={(v) => { setShiftFilter(v); setPage(1); }}
            resultCount={totalItems}
          />
        )}

        {/* Table */}
        <div className="flex flex-1 flex-col overflow-hidden">
          <DriverTable
            drivers={drivers}
            totalItems={totalItems}
            page={page}
            pageSize={PAGE_SIZE}
            onPageChange={setPage}
            selectedDriver={selectedDriver}
            onSelectDriver={handleSelectDriver}
            onEditDriver={handleEditDriver}
            onDeleteDriver={handleDeleteDriver}
            isLoading={isLoading}
            isReadOnly={IS_READ_ONLY}
          />
        </div>
      </div>

      {/* Detail Sheet */}
      <DriverDetail
        driver={selectedDriver}
        open={detailOpen}
        onOpenChange={setDetailOpen}
        onEdit={() => {
          if (selectedDriver) handleEditDriver(selectedDriver);
        }}
        onDelete={() => {
          if (selectedDriver) handleDeleteDriver(selectedDriver);
        }}
        isReadOnly={IS_READ_ONLY}
      />

      {/* Form Sheet */}
      <DriverForm
        key={formKey}
        mode={formMode}
        driver={formMode === "edit" ? selectedDriver : null}
        open={formOpen}
        onOpenChange={setFormOpen}
        onSubmit={handleFormSubmit}
      />

      {/* Delete Dialog */}
      <DeleteDriverDialog
        driver={deleteTarget}
        open={deleteOpen}
        onOpenChange={setDeleteOpen}
        onConfirm={handleDeleteConfirm}
      />
    </div>
  );
}
