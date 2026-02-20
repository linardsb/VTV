"use client";

import { useTranslations } from "next-intl";
import { useLocale } from "next-intl";
import { Pencil, Trash2, X } from "lucide-react";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";
import type { Stop } from "@/types/stop";

interface StopDetailProps {
  stop: Stop | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onEdit: () => void;
  onDelete: () => void;
  isReadOnly: boolean;
}

function DetailRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-(--spacing-tight)">
      <span className="text-xs font-medium text-label-text uppercase tracking-wide">
        {label}
      </span>
      <div className="text-sm text-foreground">{children}</div>
    </div>
  );
}

export function StopDetail({
  stop,
  open,
  onOpenChange,
  onEdit,
  onDelete,
  isReadOnly,
}: StopDetailProps) {
  const t = useTranslations("stops");
  const tLoc = useTranslations("stops.locationTypes");
  const tWheelchair = useTranslations("stops.wheelchairOptions");
  const locale = useLocale();

  if (!stop) return null;

  const dateFormatter = new Intl.DateTimeFormat(locale, {
    year: "numeric",
    month: "long",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-full overflow-y-auto sm:w-[400px]">
        <SheetHeader>
          <div className="flex items-start justify-between">
            <div className="space-y-(--spacing-tight)">
              <SheetTitle className="font-heading text-heading font-semibold">
                {stop.stop_name}
              </SheetTitle>
              <span className="font-mono text-xs text-foreground-muted">
                {stop.gtfs_stop_id}
              </span>
            </div>
            <Button
              variant="ghost"
              size="sm"
              className="size-8 p-0"
              onClick={() => onOpenChange(false)}
              aria-label={t("actions.close")}
            >
              <X className="size-4" />
            </Button>
          </div>
        </SheetHeader>

        <div className="mt-(--spacing-grid) space-y-(--spacing-grid)">
          <div className="space-y-(--spacing-card)">
            <DetailRow label={t("detail.description")}>
              {stop.stop_desc || "-"}
            </DetailRow>
            <DetailRow label={t("detail.locationType")}>
              <Badge variant="outline" className="text-xs">
                {tLoc(String(stop.location_type))}
              </Badge>
            </DetailRow>
            <DetailRow label={t("detail.coordinates")}>
              {stop.stop_lat !== null && stop.stop_lon !== null
                ? `${stop.stop_lat.toFixed(6)}, ${stop.stop_lon.toFixed(6)}`
                : "-"}
            </DetailRow>
            <DetailRow label={t("detail.wheelchairBoarding")}>
              <Badge
                variant="outline"
                className={cn(
                  "text-xs",
                  stop.wheelchair_boarding === 1 &&
                    "border-status-ontime/30 bg-status-ontime/10 text-status-ontime",
                  stop.wheelchair_boarding === 2 &&
                    "border-status-delayed/30 bg-status-delayed/10 text-status-delayed",
                )}
              >
                {tWheelchair(String(stop.wheelchair_boarding))}
              </Badge>
            </DetailRow>
            <DetailRow label={t("detail.isActive")}>
              <Badge
                variant="outline"
                className={cn(
                  "text-xs",
                  stop.is_active
                    ? "border-status-ontime/30 bg-status-ontime/10 text-status-ontime"
                    : "border-status-delayed/30 bg-status-delayed/10 text-status-delayed",
                )}
              >
                {stop.is_active ? t("filters.active") : t("filters.inactive")}
              </Badge>
            </DetailRow>
            <DetailRow label={t("detail.parentStation")}>
              {stop.parent_station_id !== null ? String(stop.parent_station_id) : "-"}
            </DetailRow>
          </div>

          <Separator />

          <div className="space-y-(--spacing-card)">
            <DetailRow label={t("detail.createdAt")}>
              {dateFormatter.format(new Date(stop.created_at))}
            </DetailRow>
            <DetailRow label={t("detail.updatedAt")}>
              {dateFormatter.format(new Date(stop.updated_at))}
            </DetailRow>
          </div>

          {/* Actions */}
          {!isReadOnly && (
            <>
              <Separator />
              <div className="flex gap-(--spacing-inline)">
                <Button
                  variant="outline"
                  className="flex-1 cursor-pointer"
                  onClick={onEdit}
                >
                  <Pencil className="mr-2 size-4" />
                  {t("actions.edit")}
                </Button>
                <Button
                  variant="destructive"
                  className="cursor-pointer"
                  onClick={onDelete}
                >
                  <Trash2 className="mr-2 size-4" />
                  {t("actions.delete")}
                </Button>
              </div>
            </>
          )}
        </div>
      </SheetContent>
    </Sheet>
  );
}
