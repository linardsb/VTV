"use client";

import { useTranslations } from "next-intl";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs";
import { cn } from "@/lib/utils";
import type { Vehicle, MaintenanceRecord } from "@/types/vehicle";

interface DetailRowProps {
  label: string;
  value: string | number | null | undefined;
}

function DetailRow({ label, value }: DetailRowProps) {
  return (
    <div className="flex justify-between py-1.5">
      <span className="text-sm text-foreground-muted">{label}</span>
      <span className="text-sm font-medium text-foreground text-right max-w-[60%] break-words">
        {value ?? "-"}
      </span>
    </div>
  );
}

const STATUS_COLORS: Record<string, string> = {
  active: "bg-status-ontime/10 text-status-ontime border-status-ontime/20",
  inactive: "bg-surface-secondary text-foreground-muted border-border",
  maintenance:
    "bg-status-delayed/10 text-status-delayed border-status-delayed/20",
};

const TYPE_COLORS: Record<string, string> = {
  bus: "bg-transport-bus/10 text-transport-bus border-transport-bus/20",
  trolleybus:
    "bg-transport-trolleybus/10 text-transport-trolleybus border-transport-trolleybus/20",
  tram: "bg-transport-tram/10 text-transport-tram border-transport-tram/20",
};

const MAINTENANCE_TYPE_COLORS: Record<string, string> = {
  scheduled: "bg-status-ontime/10 text-status-ontime border-status-ontime/20",
  unscheduled:
    "bg-status-delayed/10 text-status-delayed border-status-delayed/20",
  inspection: "bg-surface-secondary text-foreground-muted border-border",
  repair:
    "bg-status-critical/10 text-status-critical border-status-critical/20",
};

interface VehicleDetailProps {
  vehicle: Vehicle | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onEdit: () => void;
  onDelete: () => void;
  onAssignDriver: () => void;
  maintenanceRecords: MaintenanceRecord[];
  maintenanceLoading: boolean;
  onAddMaintenance: () => void;
  isReadOnly: boolean;
  canDelete: boolean;
  canAssignDriver: boolean;
  canAddMaintenance: boolean;
}

export function VehicleDetail({
  vehicle,
  open,
  onOpenChange,
  onEdit,
  onDelete,
  onAssignDriver,
  maintenanceRecords,
  maintenanceLoading,
  onAddMaintenance,
  isReadOnly,
  canDelete,
  canAssignDriver,
  canAddMaintenance,
}: VehicleDetailProps) {
  const t = useTranslations("vehicles");

  if (!vehicle) return null;

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return null;
    try {
      return new Intl.DateTimeFormat("en-CA").format(new Date(dateStr));
    } catch {
      return dateStr;
    }
  };

  const formatDateTime = (dateStr: string) => {
    try {
      return new Intl.DateTimeFormat("en-CA", {
        dateStyle: "short",
        timeStyle: "short",
      }).format(new Date(dateStr));
    } catch {
      return dateStr;
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="sm:max-w-[32rem] max-h-[90vh] overflow-y-auto"
        showCloseButton
      >
        <DialogHeader>
          <DialogTitle className="font-heading text-heading font-semibold">
            {vehicle.fleet_number}
          </DialogTitle>
          <DialogDescription className="sr-only">
            {vehicle.fleet_number}
          </DialogDescription>
          <div className="flex gap-2 pt-1">
            <Badge
              variant="outline"
              className={cn(
                "text-xs",
                TYPE_COLORS[vehicle.vehicle_type] ?? "",
              )}
            >
              {t(`types.${vehicle.vehicle_type}`)}
            </Badge>
            <Badge
              variant="outline"
              className={cn(
                "text-xs",
                STATUS_COLORS[vehicle.status] ?? "",
              )}
            >
              {t(`statuses.${vehicle.status}`)}
            </Badge>
            {!vehicle.is_active && (
              <Badge
                variant="outline"
                className="text-xs bg-status-critical/10 text-status-critical"
              >
                {t("detail.inactive")}
              </Badge>
            )}
          </div>
        </DialogHeader>

        <Tabs defaultValue="info">
          <TabsList className="w-full">
            <TabsTrigger value="info" className="flex-1">
              {t("detail.tabs.info")}
            </TabsTrigger>
            <TabsTrigger value="maintenance" className="flex-1">
              {t("detail.tabs.maintenance")}
            </TabsTrigger>
          </TabsList>

          {/* Info Tab */}
          <TabsContent value="info" className="space-y-(--spacing-card)">
            {/* Vehicle Info */}
            <div>
              <p className="text-xs font-medium text-label-text uppercase tracking-wide mb-2">
                {t("detail.vehicleInfo")}
              </p>
              <DetailRow
                label={t("detail.fleetNumber")}
                value={vehicle.fleet_number}
              />
              <DetailRow
                label={t("detail.licensePlate")}
                value={vehicle.license_plate}
              />
              <DetailRow
                label={t("detail.manufacturer")}
                value={vehicle.manufacturer}
              />
              <DetailRow
                label={t("detail.model")}
                value={vehicle.model_name}
              />
              <DetailRow
                label={t("detail.modelYear")}
                value={vehicle.model_year}
              />
              <DetailRow
                label={t("detail.capacity")}
                value={vehicle.capacity}
              />
            </div>

            <Separator />

            {/* Operations */}
            <div>
              <p className="text-xs font-medium text-label-text uppercase tracking-wide mb-2">
                {t("form.operations")}
              </p>
              <DetailRow
                label={t("detail.mileage")}
                value={
                  vehicle.mileage_km != null
                    ? vehicle.mileage_km.toLocaleString()
                    : null
                }
              />
              <DetailRow
                label={t("detail.registrationExpiry")}
                value={formatDate(vehicle.registration_expiry)}
              />
              <DetailRow
                label={t("detail.nextMaintenance")}
                value={formatDate(vehicle.next_maintenance_date)}
              />
              <DetailRow
                label={t("detail.qualifiedRoutes")}
                value={vehicle.qualified_route_ids}
              />
              <DetailRow
                label={t("detail.driver")}
                value={
                  vehicle.current_driver_id
                    ? `#${vehicle.current_driver_id}`
                    : t("detail.noDriver")
                }
              />
            </div>

            {/* Notes */}
            {vehicle.notes && (
              <>
                <Separator />
                <div>
                  <p className="text-xs font-medium text-label-text uppercase tracking-wide mb-2">
                    {t("detail.notes")}
                  </p>
                  <p className="text-sm text-foreground">{vehicle.notes}</p>
                </div>
              </>
            )}

            <Separator />

            {/* Metadata */}
            <div>
              <p className="text-xs font-medium text-label-text uppercase tracking-wide mb-2">
                {t("detail.metadata")}
              </p>
              <DetailRow
                label={t("detail.createdAt")}
                value={formatDateTime(vehicle.created_at)}
              />
              <DetailRow
                label={t("detail.updatedAt")}
                value={formatDateTime(vehicle.updated_at)}
              />
            </div>

            {/* Actions */}
            {(!isReadOnly || canAssignDriver) && (
              <>
                <Separator />
                <div className="flex gap-2">
                  {!isReadOnly && (
                    <Button
                      variant="outline"
                      className="flex-1"
                      onClick={onEdit}
                    >
                      {t("actions.edit")}
                    </Button>
                  )}
                  {canAssignDriver && (
                    <Button
                      variant="outline"
                      className="flex-1"
                      onClick={onAssignDriver}
                    >
                      {vehicle.current_driver_id
                        ? t("driverAssignment.unassign")
                        : t("driverAssignment.assign")}
                    </Button>
                  )}
                  {canDelete && (
                    <Button
                      variant="destructive"
                      className="flex-1"
                      onClick={onDelete}
                    >
                      {t("actions.delete")}
                    </Button>
                  )}
                </div>
              </>
            )}
          </TabsContent>

          {/* Maintenance Tab */}
          <TabsContent
            value="maintenance"
            className="space-y-(--spacing-card)"
          >
            <div className="flex items-center justify-between">
              <p className="text-xs font-medium text-label-text uppercase tracking-wide">
                {t("maintenance.title")}
              </p>
              {canAddMaintenance && (
                <Button size="sm" onClick={onAddMaintenance}>
                  {t("maintenance.addRecord")}
                </Button>
              )}
            </div>

            {maintenanceLoading ? (
              <div className="space-y-2">
                {Array.from({ length: 3 }).map((_, i) => (
                  <Skeleton key={`mskel-${i}`} className="h-16 w-full" />
                ))}
              </div>
            ) : maintenanceRecords.length === 0 ? (
              <p className="text-sm text-foreground-muted text-center py-(--spacing-page)">
                {t("maintenance.noRecords")}
              </p>
            ) : (
              <ScrollArea className="max-h-[400px]">
                <div className="space-y-3">
                  {maintenanceRecords.map((record) => (
                    <div
                      key={record.id}
                      className="border border-border p-(--spacing-card) space-y-1"
                    >
                      <div className="flex items-center justify-between">
                        <Badge
                          variant="outline"
                          className={cn(
                            "text-xs",
                            MAINTENANCE_TYPE_COLORS[
                              record.maintenance_type
                            ] ?? "",
                          )}
                        >
                          {t(
                            `maintenance.types.${record.maintenance_type}`,
                          )}
                        </Badge>
                        <span className="text-xs text-foreground-muted">
                          {formatDate(record.performed_date)}
                        </span>
                      </div>
                      <p className="text-sm text-foreground">
                        {record.description}
                      </p>
                      <div className="flex gap-3 text-xs text-foreground-muted">
                        {record.cost_eur != null && (
                          <span>{record.cost_eur.toFixed(2)} EUR</span>
                        )}
                        {record.performed_by && (
                          <span>{record.performed_by}</span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </ScrollArea>
            )}
          </TabsContent>
        </Tabs>
      </DialogContent>
    </Dialog>
  );
}
