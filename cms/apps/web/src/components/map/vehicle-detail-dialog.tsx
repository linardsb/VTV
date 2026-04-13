"use client";

import { useTranslations } from "next-intl";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import type { BusPosition } from "@/types/route";

interface VehicleDetailDialogProps {
  vehicle: BusPosition | null;
  open: boolean;
  onClose: () => void;
}

function getDelayDisplay(
  delaySeconds: number,
  t: ReturnType<typeof useTranslations>,
): { text: string; className: string } {
  if (delaySeconds <= 0) {
    return {
      text: delaySeconds < 0 ? t("detail.early") : t("detail.onTime"),
      className: "text-status-ontime",
    };
  }
  const minutes = Math.round(delaySeconds / 60);
  if (delaySeconds <= 300) {
    return {
      text: `${minutes} ${t("detail.minutes")} ${t("detail.late")}`,
      className: "text-status-delayed",
    };
  }
  return {
    text: `${minutes} ${t("detail.minutes")} ${t("detail.late")}`,
    className: "text-status-critical",
  };
}

function getStatusLabel(
  status: BusPosition["currentStatus"],
  t: ReturnType<typeof useTranslations>,
): string {
  switch (status) {
    case "in_transit":
      return t("detail.inTransit");
    case "stopped":
      return t("detail.stopped");
    case "incoming":
      return t("detail.incoming");
    default:
      return status;
  }
}

export function VehicleDetailDialog({
  vehicle,
  open,
  onClose,
}: VehicleDetailDialogProps) {
  const t = useTranslations("map");

  if (!vehicle) return null;

  const delay = getDelayDisplay(vehicle.delaySeconds, t);

  return (
    <Dialog open={open} onOpenChange={(isOpen) => !isOpen && onClose()}>
      <DialogContent className="sm:max-w-[28rem]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-(--spacing-inline)">
            <span
              className="inline-flex size-8 items-center justify-center text-sm font-bold text-interactive-foreground"
              style={{ backgroundColor: vehicle.routeColor }}
              aria-hidden="true"
            >
              {vehicle.routeShortName}
            </span>
            <span>{t("detail.route")} {vehicle.routeShortName}</span>
          </DialogTitle>
        </DialogHeader>

        <div className="grid grid-cols-2 gap-(--spacing-grid) text-sm">
          <div>
            <p className="text-foreground-muted">{t("detail.status")}</p>
            <p className="font-medium text-foreground">
              {getStatusLabel(vehicle.currentStatus, t)}
            </p>
          </div>

          <div>
            <p className="text-foreground-muted">{t("detail.delay")}</p>
            <p className={`font-medium ${delay.className}`}>{delay.text}</p>
          </div>

          <div>
            <p className="text-foreground-muted">{t("detail.operator")}</p>
            <p className="font-medium text-foreground">
              {vehicle.operatorName || vehicle.feedId}
            </p>
          </div>

          <div>
            <p className="text-foreground-muted">{t("detail.bearing")}</p>
            <p className="font-medium text-foreground">
              {vehicle.bearing !== null ? `${vehicle.bearing}°` : "—"}
            </p>
          </div>

          {vehicle.nextStopName && (
            <div className="col-span-2">
              <p className="text-foreground-muted">{t("detail.nextStop")}</p>
              <p className="font-medium text-foreground">
                {vehicle.nextStopName}
              </p>
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
