"use client";

import { useState, useEffect, useCallback } from "react";
import { useTranslations } from "next-intl";
import { useSession } from "next-auth/react";
import { Plus, Filter } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { useIsMobile } from "@/hooks/use-mobile";
import { VehicleFilters } from "@/components/vehicles/vehicle-filters";
import { VehicleTable } from "@/components/vehicles/vehicle-table";
import { VehicleDetail } from "@/components/vehicles/vehicle-detail";
import { VehicleForm } from "@/components/vehicles/vehicle-form";
import { DeleteVehicleDialog } from "@/components/vehicles/delete-vehicle-dialog";
import { MaintenanceForm } from "@/components/vehicles/maintenance-form";
import {
  fetchVehicles,
  createVehicle,
  updateVehicle,
  deleteVehicle,
  assignDriver,
  fetchMaintenanceHistory,
  createMaintenanceRecord,
} from "@/lib/vehicles-sdk";
import { fetchDrivers } from "@/lib/drivers-sdk";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import type {
  Vehicle,
  VehicleCreate,
  VehicleUpdate,
  MaintenanceRecord,
  MaintenanceRecordCreate,
} from "@/types/vehicle";
import type { Driver } from "@/types/driver";

const PAGE_SIZE = 20;

export default function VehiclesPage() {
  const t = useTranslations("vehicles");
  const isMobile = useIsMobile();
  const { data: session, status } = useSession();
  const userRole: string = session?.user?.role ?? "viewer";
  const IS_READ_ONLY = userRole === "viewer";
  const CAN_DELETE = userRole === "admin";
  const CAN_EDIT = userRole === "admin" || userRole === "editor";
  const CAN_ASSIGN_DRIVER =
    userRole === "admin" || userRole === "dispatcher";
  const CAN_ADD_MAINTENANCE =
    userRole === "admin" || userRole === "editor";

  // Data state
  const [vehicles, setVehicles] = useState<Vehicle[]>([]);
  const [totalItems, setTotalItems] = useState(0);
  const [page, setPage] = useState(1);
  const [isLoading, setIsLoading] = useState(true);

  // Maintenance state
  const [maintenanceRecords, setMaintenanceRecords] = useState<
    MaintenanceRecord[]
  >([]);
  const [maintenanceLoading, setMaintenanceLoading] = useState(false);

  // Filter state
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [filterSheetOpen, setFilterSheetOpen] = useState(false);

  // UI state
  const [selectedVehicle, setSelectedVehicle] = useState<Vehicle | null>(
    null,
  );
  const [detailOpen, setDetailOpen] = useState(false);
  const [formOpen, setFormOpen] = useState(false);
  const [formMode, setFormMode] = useState<"create" | "edit">("create");
  const [formKey, setFormKey] = useState(0);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<Vehicle | null>(null);
  const [maintenanceFormOpen, setMaintenanceFormOpen] = useState(false);
  const [maintenanceFormKey, setMaintenanceFormKey] = useState(0);

  // Driver assignment state
  const [driverAssignOpen, setDriverAssignOpen] = useState(false);
  const [availableDrivers, setAvailableDrivers] = useState<Driver[]>([]);
  const [driversLoading, setDriversLoading] = useState(false);

  // Debounced search
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(search);
      setPage(1);
    }, 300);
    return () => clearTimeout(timer);
  }, [search]);

  // Load data
  const loadVehicles = useCallback(async () => {
    setIsLoading(true);
    try {
      const result = await fetchVehicles({
        page,
        page_size: PAGE_SIZE,
        search: debouncedSearch || undefined,
        active_only: true,
        vehicle_type:
          typeFilter !== "all" ? typeFilter : undefined,
        status: statusFilter !== "all" ? statusFilter : undefined,
      });
      setVehicles(result.items);
      setTotalItems(result.total);
    } catch (e) {
      console.warn("[vehicles] Failed to load:", e);
      toast.error(t("toast.loadError"));
    } finally {
      setIsLoading(false);
    }
  }, [page, debouncedSearch, typeFilter, statusFilter, t]);

  useEffect(() => {
    if (status !== "authenticated") return;
    void loadVehicles();
  }, [loadVehicles, status]);

  // Load maintenance for selected vehicle
  const loadMaintenance = useCallback(
    async (vehicleId: number) => {
      setMaintenanceLoading(true);
      try {
        const result = await fetchMaintenanceHistory(vehicleId, {
          page: 1,
          page_size: 50,
        });
        setMaintenanceRecords(result.items);
      } catch {
        setMaintenanceRecords([]);
      } finally {
        setMaintenanceLoading(false);
      }
    },
    [],
  );

  // Handlers
  const handleSelectVehicle = useCallback(
    (vehicle: Vehicle) => {
      setSelectedVehicle(vehicle);
      setDetailOpen(true);
      void loadMaintenance(vehicle.id);
    },
    [loadMaintenance],
  );

  const handleCreateClick = () => {
    setSelectedVehicle(null);
    setFormMode("create");
    setFormKey((prev) => prev + 1);
    setFormOpen(true);
  };

  const handleEditVehicle = (vehicle: Vehicle) => {
    setSelectedVehicle(vehicle);
    setFormMode("edit");
    setFormKey((prev) => prev + 1);
    setFormOpen(true);
    setDetailOpen(false);
  };

  const handleDeleteVehicle = (vehicle: Vehicle) => {
    setDeleteTarget(vehicle);
    setDeleteOpen(true);
    setDetailOpen(false);
  };

  const handleFormSubmit = async (data: VehicleCreate | VehicleUpdate) => {
    try {
      if (formMode === "create") {
        await createVehicle(data as VehicleCreate);
        toast.success(t("toast.created"));
      } else if (selectedVehicle) {
        await updateVehicle(selectedVehicle.id, data as VehicleUpdate);
        toast.success(t("toast.updated"));
      }
      setFormOpen(false);
      void loadVehicles();
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
      await deleteVehicle(deleteTarget.id);
      toast.success(t("toast.deleted"));
      setDeleteTarget(null);
      if (selectedVehicle?.id === deleteTarget.id) {
        setSelectedVehicle(null);
        setDetailOpen(false);
      }
      void loadVehicles();
    } catch {
      toast.error(t("toast.deleteError"));
    }
  };

  // Driver assignment
  const handleAssignDriverClick = async () => {
    setDriversLoading(true);
    setDriverAssignOpen(true);
    try {
      const result = await fetchDrivers({
        active_only: true,
        page_size: 100,
      });
      setAvailableDrivers(result.items);
    } catch {
      setAvailableDrivers([]);
    } finally {
      setDriversLoading(false);
    }
  };

  const handleDriverAssign = async (driverId: string) => {
    if (!selectedVehicle) return;
    try {
      const id = driverId === "unassign" ? null : Number(driverId);
      const updated = await assignDriver(selectedVehicle.id, id);
      setSelectedVehicle(updated);
      toast.success(
        id
          ? t("driverAssignment.toast.assigned")
          : t("driverAssignment.toast.unassigned"),
      );
      setDriverAssignOpen(false);
      void loadVehicles();
    } catch {
      toast.error(t("driverAssignment.toast.assignError"));
    }
  };

  // Maintenance
  const handleAddMaintenance = () => {
    setMaintenanceFormKey((prev) => prev + 1);
    setMaintenanceFormOpen(true);
  };

  const handleMaintenanceSubmit = async (data: MaintenanceRecordCreate) => {
    if (!selectedVehicle) return;
    try {
      await createMaintenanceRecord(selectedVehicle.id, data);
      toast.success(t("maintenance.toast.created"));
      setMaintenanceFormOpen(false);
      void loadMaintenance(selectedVehicle.id);
    } catch {
      toast.error(t("maintenance.toast.createError"));
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
          <p className="text-sm text-foreground-muted">
            {t("description")}
          </p>
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
          {CAN_EDIT && (
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
          <VehicleFilters
            search={search}
            onSearchChange={setSearch}
            typeFilter={typeFilter}
            onTypeFilterChange={(v) => {
              setTypeFilter(v);
              setPage(1);
            }}
            statusFilter={statusFilter}
            onStatusFilterChange={(v) => {
              setStatusFilter(v);
              setPage(1);
            }}
            resultCount={totalItems}
          />
        )}

        {/* Mobile filter sheet */}
        {isMobile && (
          <VehicleFilters
            asSheet
            sheetOpen={filterSheetOpen}
            onSheetOpenChange={setFilterSheetOpen}
            search={search}
            onSearchChange={setSearch}
            typeFilter={typeFilter}
            onTypeFilterChange={(v) => {
              setTypeFilter(v);
              setPage(1);
            }}
            statusFilter={statusFilter}
            onStatusFilterChange={(v) => {
              setStatusFilter(v);
              setPage(1);
            }}
            resultCount={totalItems}
          />
        )}

        {/* Table */}
        <div className="flex flex-1 flex-col overflow-hidden">
          <VehicleTable
            vehicles={vehicles}
            totalItems={totalItems}
            page={page}
            pageSize={PAGE_SIZE}
            onPageChange={setPage}
            selectedVehicle={selectedVehicle}
            onSelectVehicle={handleSelectVehicle}
            onEditVehicle={handleEditVehicle}
            onDeleteVehicle={handleDeleteVehicle}
            isLoading={isLoading}
            isReadOnly={IS_READ_ONLY && !CAN_ASSIGN_DRIVER}
            canDelete={CAN_DELETE}
          />
        </div>
      </div>

      {/* Detail Dialog */}
      <VehicleDetail
        vehicle={selectedVehicle}
        open={detailOpen}
        onOpenChange={setDetailOpen}
        onEdit={() => {
          if (selectedVehicle) handleEditVehicle(selectedVehicle);
        }}
        onDelete={() => {
          if (selectedVehicle) handleDeleteVehicle(selectedVehicle);
        }}
        onAssignDriver={() => void handleAssignDriverClick()}
        maintenanceRecords={maintenanceRecords}
        maintenanceLoading={maintenanceLoading}
        onAddMaintenance={handleAddMaintenance}
        isReadOnly={!CAN_EDIT}
        canDelete={CAN_DELETE}
        canAssignDriver={CAN_ASSIGN_DRIVER}
        canAddMaintenance={CAN_ADD_MAINTENANCE}
      />

      {/* Form Dialog */}
      <VehicleForm
        key={formKey}
        mode={formMode}
        vehicle={formMode === "edit" ? selectedVehicle : null}
        open={formOpen}
        onOpenChange={setFormOpen}
        onSubmit={handleFormSubmit}
      />

      {/* Delete Dialog */}
      <DeleteVehicleDialog
        vehicle={deleteTarget}
        open={deleteOpen}
        onOpenChange={setDeleteOpen}
        onConfirm={handleDeleteConfirm}
      />

      {/* Maintenance Form Dialog */}
      <MaintenanceForm
        key={maintenanceFormKey}
        open={maintenanceFormOpen}
        onOpenChange={setMaintenanceFormOpen}
        onSubmit={handleMaintenanceSubmit}
      />

      {/* Driver Assignment Dialog */}
      <Dialog open={driverAssignOpen} onOpenChange={setDriverAssignOpen}>
        <DialogContent className="sm:max-w-[28rem]">
          <DialogHeader>
            <DialogTitle className="font-heading text-heading font-semibold">
              {t("driverAssignment.assign")}
            </DialogTitle>
            <DialogDescription className="sr-only">
              {t("driverAssignment.assign")}
            </DialogDescription>
          </DialogHeader>
          {driversLoading ? (
            <p className="text-sm text-foreground-muted">
              {t("driverAssignment.selectDriver")}
            </p>
          ) : availableDrivers.length === 0 ? (
            <p className="text-sm text-foreground-muted">
              {t("driverAssignment.noDrivers")}
            </p>
          ) : (
            <Select onValueChange={handleDriverAssign}>
              <SelectTrigger aria-label={t("driverAssignment.selectDriver")}>
                <SelectValue
                  placeholder={t("driverAssignment.selectDriver")}
                />
              </SelectTrigger>
              <SelectContent>
                {selectedVehicle?.current_driver_id && (
                  <SelectItem value="unassign">
                    {t("driverAssignment.unassign")}
                  </SelectItem>
                )}
                {availableDrivers.map((driver) => (
                  <SelectItem
                    key={driver.id}
                    value={String(driver.id)}
                  >
                    {driver.first_name} {driver.last_name} (
                    {driver.employee_number})
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
