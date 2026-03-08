"use client";

import { MoreHorizontal, LogIn, LogOut, Clock } from "lucide-react";
import { useTranslations } from "next-intl";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Pagination,
  PaginationContent,
  PaginationEllipsis,
  PaginationItem,
  PaginationLink,
  PaginationNext,
  PaginationPrevious,
} from "@/components/ui/pagination";
import { getPageRange } from "@/lib/pagination-utils";
import type { Geofence } from "@/types/geofence";

interface GeofencesTableProps {
  geofences: Geofence[];
  totalItems: number;
  page: number;
  pageSize: number;
  onPageChange: (page: number) => void;
  selectedGeofence: Geofence | null;
  onSelectGeofence: (geofence: Geofence) => void;
  onEditGeofence: (geofence: Geofence) => void;
  onDeleteGeofence: (geofence: Geofence) => void;
  isLoading: boolean;
  isReadOnly: boolean;
  canDelete: boolean;
}

const ZONE_TYPE_COLORS: Record<string, string> = {
  depot: "bg-interactive/10 text-interactive border-interactive/20",
  terminal: "bg-status-ontime/10 text-status-ontime border-status-ontime/20",
  restricted:
    "bg-status-critical/10 text-status-critical border-status-critical/20",
  customer:
    "bg-status-delayed/10 text-status-delayed border-status-delayed/20",
  custom: "bg-surface-secondary text-foreground-muted border-border",
};

const SEVERITY_COLORS: Record<string, string> = {
  critical: "bg-status-critical/10 text-status-critical border-status-critical/20",
  high: "bg-status-delayed/10 text-status-delayed border-status-delayed/20",
  medium: "bg-surface-secondary text-foreground-muted border-border",
  low: "bg-surface-secondary text-foreground-subtle border-border",
  info: "bg-interactive/10 text-interactive border-interactive/20",
};

export function GeofencesTable({
  geofences,
  totalItems,
  page,
  pageSize,
  onPageChange,
  selectedGeofence,
  onSelectGeofence,
  onEditGeofence,
  onDeleteGeofence,
  isLoading,
  isReadOnly,
  canDelete,
}: GeofencesTableProps) {
  const t = useTranslations("geofences");
  const totalPages = Math.ceil(totalItems / pageSize);

  if (isLoading) {
    return (
      <div className="space-y-2 p-(--spacing-card)">
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton key={`skel-${i}`} className="h-12 w-full" />
        ))}
      </div>
    );
  }

  if (geofences.length === 0) {
    return (
      <div className="flex flex-1 items-center justify-center p-(--spacing-page)">
        <div className="text-center">
          <p className="text-sm font-medium text-foreground">
            {t("table.noResults")}
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-1 flex-col">
      <div className="flex-1 overflow-auto">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>{t("table.name")}</TableHead>
              <TableHead>{t("table.zoneType")}</TableHead>
              <TableHead className="hidden md:table-cell">
                {t("table.alertsEnabled")}
              </TableHead>
              <TableHead className="hidden lg:table-cell">
                {t("table.severity")}
              </TableHead>
              <TableHead>{t("table.status")}</TableHead>
              <TableHead className="w-10">
                <span className="sr-only">{t("table.actions")}</span>
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {geofences.map((geofence) => (
              <TableRow
                key={geofence.id}
                className={cn(
                  "cursor-pointer",
                  selectedGeofence?.id === geofence.id && "bg-selected-bg",
                )}
                onClick={() => onSelectGeofence(geofence)}
              >
                <TableCell className="font-medium">
                  {geofence.name}
                </TableCell>
                <TableCell>
                  <Badge
                    variant="outline"
                    className={cn(
                      "text-xs",
                      ZONE_TYPE_COLORS[geofence.zone_type] ?? "",
                    )}
                  >
                    {t(`filters.${geofence.zone_type}`)}
                  </Badge>
                </TableCell>
                <TableCell className="hidden md:table-cell">
                  <div className="flex gap-1">
                    {geofence.alert_on_enter && (
                      <LogIn
                        className="size-3.5 text-status-ontime"
                        aria-label={t("detail.alertOnEnter")}
                      />
                    )}
                    {geofence.alert_on_exit && (
                      <LogOut
                        className="size-3.5 text-status-delayed"
                        aria-label={t("detail.alertOnExit")}
                      />
                    )}
                    {geofence.alert_on_dwell && (
                      <Clock
                        className="size-3.5 text-status-critical"
                        aria-label={t("detail.alertOnDwell")}
                      />
                    )}
                  </div>
                </TableCell>
                <TableCell className="hidden lg:table-cell">
                  <Badge
                    variant="outline"
                    className={cn(
                      "text-xs",
                      SEVERITY_COLORS[geofence.alert_severity] ?? "",
                    )}
                  >
                    {geofence.alert_severity}
                  </Badge>
                </TableCell>
                <TableCell>
                  <Badge
                    variant="outline"
                    className={cn(
                      "text-xs",
                      geofence.is_active
                        ? "bg-status-ontime/10 text-status-ontime border-status-ontime/20"
                        : "bg-surface-secondary text-foreground-muted border-border",
                    )}
                  >
                    {geofence.is_active
                      ? t("table.active")
                      : t("table.inactive")}
                  </Badge>
                </TableCell>
                <TableCell>
                  {!isReadOnly && (
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="size-8 p-0"
                          onClick={(e) => e.stopPropagation()}
                        >
                          <MoreHorizontal className="size-4" />
                          <span className="sr-only">
                            {t("table.actions")}
                          </span>
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem
                          onClick={(e) => {
                            e.stopPropagation();
                            onEditGeofence(geofence);
                          }}
                        >
                          {t("actions.edit")}
                        </DropdownMenuItem>
                        {canDelete && (
                          <DropdownMenuItem
                            onClick={(e) => {
                              e.stopPropagation();
                              onDeleteGeofence(geofence);
                            }}
                            className="text-status-critical"
                          >
                            {t("actions.delete")}
                          </DropdownMenuItem>
                        )}
                      </DropdownMenuContent>
                    </DropdownMenu>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      {totalPages > 1 && (
        <div className="flex items-center justify-end border-t border-border px-(--spacing-card) py-(--spacing-tight)">
          <Pagination className="mx-0 w-auto justify-end">
            <PaginationContent className="gap-0.5">
              <PaginationItem>
                <PaginationPrevious
                  onClick={() => onPageChange(Math.max(1, page - 1))}
                  aria-disabled={page === 1}
                  className={cn(
                    "h-8 w-8 p-0 [&>svg]:size-4 [&>span]:hidden",
                    page === 1 && "pointer-events-none opacity-50",
                  )}
                />
              </PaginationItem>
              {getPageRange(page, totalPages).map((item, idx) =>
                item === "ellipsis" ? (
                  <PaginationItem
                    key={`ellipsis-${idx}`}
                    className="hidden sm:inline-flex"
                  >
                    <PaginationEllipsis className="size-8" />
                  </PaginationItem>
                ) : (
                  <PaginationItem
                    key={item}
                    className="hidden sm:inline-flex"
                  >
                    <PaginationLink
                      isActive={item === page}
                      onClick={() => onPageChange(item)}
                      className="h-8 w-8 text-xs"
                    >
                      {item}
                    </PaginationLink>
                  </PaginationItem>
                ),
              )}
              <PaginationItem>
                <PaginationNext
                  onClick={() =>
                    onPageChange(Math.min(totalPages, page + 1))
                  }
                  aria-disabled={page === totalPages}
                  className={cn(
                    "h-8 w-8 p-0 [&>svg]:size-4 [&>span]:hidden",
                    page === totalPages &&
                      "pointer-events-none opacity-50",
                  )}
                />
              </PaginationItem>
            </PaginationContent>
          </Pagination>
        </div>
      )}
    </div>
  );
}
