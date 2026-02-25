"use client";

import type { DragEvent } from "react";
import { useTranslations } from "next-intl";
import { cn } from "@/lib/utils";
import type { Driver } from "@/types/driver";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Skeleton } from "@/components/ui/skeleton";

interface DriverRosterProps {
  drivers: Driver[];
  isLoading: boolean;
  canDrag: boolean;
}

interface DriverRosterCardProps {
  driver: Driver;
  canDrag: boolean;
}

const statusStyles: Record<string, string> = {
  available: "bg-status-ontime/15 text-status-ontime",
  on_duty: "bg-foreground/10 text-foreground",
  on_leave: "bg-status-delayed/15 text-status-delayed",
  sick: "bg-status-critical/15 text-status-critical",
};

const shiftLabels: Record<string, string> = {
  morning: "shiftMorning",
  afternoon: "shiftAfternoon",
  evening: "shiftEvening",
  night: "shiftNight",
};

function DriverRosterCard({ driver, canDrag }: DriverRosterCardProps) {
  const t = useTranslations("dashboard");
  const statusClass = statusStyles[driver.status] ?? "bg-foreground/10 text-foreground";
  const shiftKey = shiftLabels[driver.default_shift];

  function handleDragStart(e: DragEvent<HTMLDivElement>) {
    e.dataTransfer.setData("application/vtv-driver", JSON.stringify(driver));
    e.dataTransfer.effectAllowed = "copy";
  }

  return (
    <div
      draggable={canDrag}
      onDragStart={canDrag ? handleDragStart : undefined}
      className={cn(
        "flex items-center gap-(--spacing-inline) rounded-lg border border-border-subtle bg-surface-raised p-(--spacing-inline) transition-colors duration-200 hover:border-border",
        canDrag && "cursor-grab active:cursor-grabbing"
      )}
    >
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium text-foreground">
          {driver.first_name} {driver.last_name}
        </p>
        <p className="truncate text-xs text-foreground-muted">
          {t("roster.employee")} {driver.employee_number}
          {shiftKey ? ` · ${t(`dropAction.${shiftKey}`)}` : ""}
        </p>
      </div>
      <Badge
        variant="secondary"
        className={cn("shrink-0 text-[10px]", statusClass)}
      >
        {t(`roster.status.${driver.status}`)}
      </Badge>
    </div>
  );
}

export function DriverRoster({ drivers, isLoading, canDrag }: DriverRosterProps) {
  const t = useTranslations("dashboard");

  return (
    <div className="flex h-full flex-col rounded-lg border border-card-border bg-card-bg">
      <div className="shrink-0 border-b border-border-subtle p-(--spacing-card)">
        <div className="flex items-center justify-between">
          <h2 className="font-heading text-sm font-semibold text-foreground">
            {t("roster.title")}
          </h2>
          {!isLoading && (
            <Badge variant="secondary" className="text-[10px]">
              {drivers.length}
            </Badge>
          )}
        </div>
        {canDrag && (
          <p className="mt-(--spacing-tight) text-xs text-foreground-muted">
            {t("roster.dragHint")}
          </p>
        )}
      </div>

      <ScrollArea className="min-h-0 flex-1">
        <div className="flex flex-col gap-(--spacing-tight) p-(--spacing-card)">
          {isLoading &&
            Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={`skel-${String(i)}`} className="h-14 rounded-lg" />
            ))}

          {!isLoading && drivers.length === 0 && (
            <p className="py-8 text-center text-sm text-foreground-muted">
              {t("roster.empty")}
            </p>
          )}

          {!isLoading &&
            drivers.map((driver) => (
              <DriverRosterCard
                key={driver.id}
                driver={driver}
                canDrag={canDrag}
              />
            ))}
        </div>
      </ScrollArea>
    </div>
  );
}
