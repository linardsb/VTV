"use client";

import { useTranslations } from "next-intl";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { cn } from "@/lib/utils";
import type { TrackedDevice } from "@/types/fleet";

interface FleetDeviceDetailProps {
  device: TrackedDevice | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onEdit: () => void;
  onDelete: () => void;
  isReadOnly: boolean;
  canDelete: boolean;
}

const STATUS_COLORS: Record<string, string> = {
  active: "bg-status-ontime/10 text-status-ontime border-status-ontime/20",
  inactive: "bg-surface-secondary text-foreground-muted border-border",
  offline: "bg-status-critical/10 text-status-critical border-status-critical/20",
};

function DetailRow({
  label,
  value,
}: {
  label: string;
  value: React.ReactNode;
}) {
  return (
    <div className="flex justify-between py-1.5">
      <span className="text-sm text-foreground-muted">{label}</span>
      <span className="text-sm font-medium text-foreground text-right max-w-[60%] break-words">
        {value ?? "-"}
      </span>
    </div>
  );
}

function TelemetryCard({
  label,
  value,
  unit,
}: {
  label: string;
  value: number | null;
  unit: string;
}) {
  return (
    <div className="border border-border p-(--spacing-card)">
      <p className="text-xs text-foreground-muted">{label}</p>
      <p className="text-lg font-heading font-semibold text-foreground">
        {value !== null ? `${value} ${unit}` : "-"}
      </p>
    </div>
  );
}

export function FleetDeviceDetail({
  device,
  open,
  onOpenChange,
  onEdit,
  onDelete,
  isReadOnly,
  canDelete,
}: FleetDeviceDetailProps) {
  const t = useTranslations("fleet");

  if (!device) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[28rem] max-h-[90vh] overflow-y-auto" showCloseButton>
        <DialogHeader>
          <DialogTitle className="font-heading text-heading font-semibold">
            {t("detail.title")}
          </DialogTitle>
          <DialogDescription className="sr-only">
            {t("detail.title")}
          </DialogDescription>
        </DialogHeader>

        <Tabs defaultValue="info">
          <TabsList className="w-full">
            <TabsTrigger value="info" className="flex-1 cursor-pointer">
              {t("detail.tabs.info")}
            </TabsTrigger>
            <TabsTrigger value="telemetry" className="flex-1 cursor-pointer">
              {t("detail.tabs.telemetry")}
            </TabsTrigger>
          </TabsList>

          <TabsContent value="info" className="space-y-1 mt-(--spacing-card)">
            <DetailRow label={t("detail.imei")} value={
              <span className="font-mono text-xs">{device.imei}</span>
            } />
            <DetailRow
              label={t("detail.simNumber")}
              value={device.sim_number}
            />
            <DetailRow
              label={t("detail.protocol")}
              value={
                <Badge variant="outline" className="text-xs">
                  {device.protocol_type}
                </Badge>
              }
            />
            <DetailRow
              label={t("detail.firmware")}
              value={device.firmware_version}
            />
            <DetailRow
              label={t("detail.vehicle")}
              value={device.vehicle_id ?? t("table.unlinked")}
            />
            <DetailRow
              label={t("detail.status")}
              value={
                <Badge
                  variant="outline"
                  className={cn(
                    "text-xs",
                    STATUS_COLORS[device.status] ?? "",
                  )}
                >
                  {t(`filters.${device.status}`)}
                </Badge>
              }
            />
            <DetailRow
              label={t("detail.lastSeen")}
              value={
                device.last_seen_at
                  ? new Date(device.last_seen_at).toLocaleString()
                  : t("table.neverSeen")
              }
            />
            <DetailRow
              label={t("detail.notes")}
              value={device.notes}
            />
            <DetailRow
              label={t("detail.createdAt")}
              value={new Date(device.created_at).toLocaleString()}
            />
          </TabsContent>

          <TabsContent value="telemetry" className="mt-(--spacing-card)">
            <p className="text-sm text-foreground-muted mb-(--spacing-card)">
              {t("detail.noTelemetry")}
            </p>
            <div className="grid grid-cols-2 gap-(--spacing-card)">
              <TelemetryCard label={t("telemetry.speed")} value={null} unit="km/h" />
              <TelemetryCard label={t("telemetry.rpm")} value={null} unit="" />
              <TelemetryCard label={t("telemetry.fuelLevel")} value={null} unit="%" />
              <TelemetryCard label={t("telemetry.coolantTemp")} value={null} unit="\u00b0C" />
              <TelemetryCard label={t("telemetry.engineLoad")} value={null} unit="%" />
              <TelemetryCard label={t("telemetry.battery")} value={null} unit="V" />
            </div>
          </TabsContent>
        </Tabs>

        {(!isReadOnly || canDelete) && (
          <>
            <Separator />
            <div className="flex gap-2">
              {!isReadOnly && (
                <Button
                  variant="outline"
                  className="flex-1 cursor-pointer"
                  onClick={onEdit}
                >
                  {t("actions.edit")}
                </Button>
              )}
              {canDelete && (
                <Button
                  variant="destructive"
                  className="flex-1 cursor-pointer"
                  onClick={onDelete}
                >
                  {t("actions.delete")}
                </Button>
              )}
            </div>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
