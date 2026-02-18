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
import { RouteTypeBadge } from "./route-type-badge";
import type { Route } from "@/types/route";

interface RouteDetailProps {
  route: Route | null;
  isOpen: boolean;
  onClose: () => void;
  onEdit: (route: Route) => void;
  onDelete: (route: Route) => void;
  isReadOnly: boolean;
}

function DetailRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-(--spacing-tight)">
      <span className="text-xs font-medium text-foreground-muted uppercase tracking-wide">
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
}: RouteDetailProps) {
  const t = useTranslations("routes.detail");
  const tActions = useTranslations("routes.actions");
  const tAgencies = useTranslations("routes.agencies");
  const tFilters = useTranslations("routes.filters");
  const locale = useLocale();

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
          <div className="flex items-start justify-between">
            <div className="space-y-(--spacing-tight)">
              <SheetTitle className="font-heading text-heading font-semibold">
                {route.shortName} — {route.longName}
              </SheetTitle>
              <RouteTypeBadge type={route.type} />
            </div>
            <Button
              variant="ghost"
              size="sm"
              className="size-8 p-0"
              onClick={onClose}
              aria-label={tActions("close")}
            >
              <X className="size-4" />
            </Button>
          </div>
        </SheetHeader>

        <div className="mt-(--spacing-grid) space-y-(--spacing-grid)">
          {/* Color preview */}
          <div className="flex items-center gap-(--spacing-inline)">
            <span
              className="inline-block size-8 rounded-md border border-border"
              style={{ backgroundColor: route.color }}
              aria-hidden="true"
            />
            <div>
              <p className="text-xs text-foreground-muted">{t("routeColor")}</p>
              <p className="font-mono text-sm">{route.color}</p>
            </div>
          </div>

          <Separator />

          {/* Info grid */}
          <div className="space-y-(--spacing-card)">
            <DetailRow label={t("description")}>
              {route.description || "—"}
            </DetailRow>
            <DetailRow label={t("agency")}>
              {tAgencies(route.agencyId)}
            </DetailRow>
            <DetailRow label={t("isActive")}>
              <Badge
                variant="outline"
                className={cn(
                  "text-xs",
                  route.isActive
                    ? "border-status-ontime/30 bg-status-ontime/10 text-status-ontime"
                    : "border-status-delayed/30 bg-status-delayed/10 text-status-delayed"
                )}
              >
                {route.isActive ? tFilters("active") : tFilters("inactive")}
              </Badge>
            </DetailRow>
            <DetailRow label={t("createdAt")}>
              {dateFormatter.format(new Date(route.createdAt))}
            </DetailRow>
            <DetailRow label={t("updatedAt")}>
              {dateFormatter.format(new Date(route.updatedAt))}
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
