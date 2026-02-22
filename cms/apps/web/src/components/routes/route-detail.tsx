"use client";

import { useMemo } from "react";
import { useTranslations } from "next-intl";
import { useLocale } from "next-intl";
import { Pencil, Trash2 } from "lucide-react";
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
import { toHexColor } from "@/lib/color-utils";
import { RouteTypeBadge } from "./route-type-badge";
import type { Route } from "@/types/route";
import type { Agency } from "@/types/schedule";

interface RouteDetailProps {
  route: Route | null;
  isOpen: boolean;
  onClose: () => void;
  onEdit: (route: Route) => void;
  onDelete: (route: Route) => void;
  isReadOnly: boolean;
  agencies: Agency[];
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

export function RouteDetail({
  route,
  isOpen,
  onClose,
  onEdit,
  onDelete,
  isReadOnly,
  agencies,
}: RouteDetailProps) {
  const t = useTranslations("routes.detail");
  const tActions = useTranslations("routes.actions");
  const tFilters = useTranslations("routes.filters");
  const locale = useLocale();

  const agencyName = useMemo(() => {
    if (!route) return "-";
    return agencies.find((a) => a.id === route.agency_id)?.agency_name ?? "-";
  }, [route, agencies]);

  if (!route) return null;

  const dateFormatter = new Intl.DateTimeFormat(locale, {
    year: "numeric",
    month: "long",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });

  return (
    <Sheet open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <SheetContent side="right" className="w-full overflow-y-auto sm:w-[400px]">
        <SheetHeader>
          <SheetTitle className="font-heading text-heading font-semibold">
            {route.route_short_name} — {route.route_long_name}
          </SheetTitle>
          <RouteTypeBadge type={route.route_type} />
        </SheetHeader>

        <div className="px-4 pb-4 space-y-(--spacing-card)">
          {/* Color preview */}
          <div className="flex items-center gap-(--spacing-inline)">
            <span
              className="inline-block size-8 rounded-md border border-border"
              style={{ backgroundColor: toHexColor(route.route_color) }}
              aria-hidden="true"
            />
            <div>
              <p className="text-xs text-foreground-muted">{t("routeColor")}</p>
              <p className="font-mono text-sm">{toHexColor(route.route_color)}</p>
            </div>
          </div>

          <Separator />

          {/* Info grid */}
          <div className="space-y-(--spacing-card)">
            <DetailRow label={t("gtfsRouteId")}>
              <span className="font-mono">{route.gtfs_route_id}</span>
            </DetailRow>
            <DetailRow label={t("agency")}>
              {agencyName}
            </DetailRow>
            {route.route_sort_order !== null && (
              <DetailRow label={t("sortOrder")}>
                {route.route_sort_order}
              </DetailRow>
            )}
            <DetailRow label={t("isActive")}>
              <Badge
                variant="outline"
                className={cn(
                  "text-xs",
                  route.is_active
                    ? "border-status-ontime/30 bg-status-ontime/10 text-status-ontime"
                    : "border-status-delayed/30 bg-status-delayed/10 text-status-delayed"
                )}
              >
                {route.is_active ? tFilters("active") : tFilters("inactive")}
              </Badge>
            </DetailRow>
            <DetailRow label={t("createdAt")}>
              {dateFormatter.format(new Date(route.created_at))}
            </DetailRow>
            <DetailRow label={t("updatedAt")}>
              {dateFormatter.format(new Date(route.updated_at))}
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
                  onClick={() => onEdit(route)}
                >
                  <Pencil className="mr-2 size-4" />
                  {tActions("edit")}
                </Button>
                <Button
                  variant="destructive"
                  className="cursor-pointer"
                  onClick={() => onDelete(route)}
                >
                  <Trash2 className="mr-2 size-4" />
                  {tActions("delete")}
                </Button>
              </div>
            </>
          )}
        </div>
      </SheetContent>
    </Sheet>
  );
}
