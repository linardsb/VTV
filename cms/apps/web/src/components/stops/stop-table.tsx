"use client";

import { useTranslations } from "next-intl";
import { MoreHorizontal, Pencil, Trash2 } from "lucide-react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Pagination,
  PaginationContent,
  PaginationItem,
  PaginationLink,
  PaginationNext,
  PaginationPrevious,
} from "@/components/ui/pagination";
import { cn } from "@/lib/utils";
import type { Stop } from "@/types/stop";

interface StopTableProps {
  stops: Stop[];
  total: number;
  page: number;
  pageSize: number;
  onPageChange: (page: number) => void;
  selectedStopId: number | null;
  onSelectStop: (stop: Stop) => void;
  onEditStop: (stop: Stop) => void;
  onDeleteStop: (stop: Stop) => void;
  isReadOnly: boolean;
  isLoading: boolean;
}

export function StopTable({
  stops,
  total,
  page,
  pageSize,
  onPageChange,
  selectedStopId,
  onSelectStop,
  onEditStop,
  onDeleteStop,
  isReadOnly,
  isLoading,
}: StopTableProps) {
  const t = useTranslations("stops");
  const tLoc = useTranslations("stops.locationTypes");
  const tWheelchair = useTranslations("stops.wheelchairOptions");

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  if (isLoading) {
    return (
      <div className="flex flex-1 items-center justify-center">
        <p className="text-sm text-foreground-muted">{t("description")}</p>
      </div>
    );
  }

  if (stops.length === 0) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-(--spacing-grid) py-20">
        <p className="text-lg font-medium text-foreground">{t("table.noResults")}</p>
        <p className="text-sm text-foreground-muted">{t("table.noResultsDescription")}</p>
      </div>
    );
  }

  const from = (page - 1) * pageSize + 1;
  const to = Math.min(page * pageSize, total);

  return (
    <div className="flex flex-1 flex-col">
      <div className="flex-1 overflow-auto">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>{t("table.name")}</TableHead>
              <TableHead className="hidden sm:table-cell w-28">{t("table.gtfsId")}</TableHead>
              <TableHead className="hidden md:table-cell w-36">{t("table.location")}</TableHead>
              <TableHead className="hidden lg:table-cell w-28">{t("table.type")}</TableHead>
              <TableHead className="hidden lg:table-cell w-28">{t("table.wheelchair")}</TableHead>
              <TableHead className="w-24">{t("table.status")}</TableHead>
              {!isReadOnly && (
                <TableHead className="w-16">
                  <span className="sr-only">{t("table.actions")}</span>
                </TableHead>
              )}
            </TableRow>
          </TableHeader>
          <TableBody>
            {stops.map((stop) => (
              <TableRow
                key={stop.id}
                className={cn(
                  "cursor-pointer transition-colors",
                  selectedStopId === stop.id && "bg-selected-bg",
                )}
                onClick={() => onSelectStop(stop)}
              >
                <TableCell>
                  <span className="font-medium">{stop.stop_name}</span>
                </TableCell>
                <TableCell className="hidden sm:table-cell">
                  <span className="font-mono text-xs text-foreground-muted">
                    {stop.gtfs_stop_id}
                  </span>
                </TableCell>
                <TableCell className="hidden md:table-cell text-foreground-muted text-xs">
                  {stop.stop_lat !== null && stop.stop_lon !== null
                    ? `${stop.stop_lat.toFixed(4)}, ${stop.stop_lon.toFixed(4)}`
                    : "-"}
                </TableCell>
                <TableCell className="hidden lg:table-cell">
                  <Badge variant="outline" className="text-xs">
                    {tLoc(String(stop.location_type))}
                  </Badge>
                </TableCell>
                <TableCell className="hidden lg:table-cell">
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
                </TableCell>
                <TableCell>
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
                </TableCell>
                {!isReadOnly && (
                  <TableCell>
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="size-8 p-0"
                          aria-label={t("table.actions")}
                          onClick={(e) => e.stopPropagation()}
                        >
                          <MoreHorizontal className="size-4" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem onClick={() => onEditStop(stop)}>
                          <Pencil className="mr-2 size-4" />
                          {t("actions.edit")}
                        </DropdownMenuItem>
                        <DropdownMenuItem
                          className="text-status-critical"
                          onClick={() => onDeleteStop(stop)}
                        >
                          <Trash2 className="mr-2 size-4" />
                          {t("actions.delete")}
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </TableCell>
                )}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      {/* Pagination */}
      <div className="flex items-center justify-between border-t border-border px-(--spacing-card) py-(--spacing-tight)">
        <p className="hidden sm:block text-xs text-foreground-muted">
          {t("table.showing", { from, to, total })}
        </p>
        {totalPages > 1 && (
          <Pagination>
            <PaginationContent>
              <PaginationItem>
                <PaginationPrevious
                  onClick={() => onPageChange(Math.max(1, page - 1))}
                  aria-disabled={page === 1}
                  className={cn(page === 1 && "pointer-events-none opacity-50")}
                />
              </PaginationItem>
              {Array.from({ length: totalPages }, (_, i) => (
                <PaginationItem key={i} className="hidden sm:inline-flex">
                  <PaginationLink
                    isActive={i + 1 === page}
                    onClick={() => onPageChange(i + 1)}
                  >
                    {i + 1}
                  </PaginationLink>
                </PaginationItem>
              ))}
              <PaginationItem>
                <PaginationNext
                  onClick={() => onPageChange(Math.min(totalPages, page + 1))}
                  aria-disabled={page === totalPages}
                  className={cn(page === totalPages && "pointer-events-none opacity-50")}
                />
              </PaginationItem>
            </PaginationContent>
          </Pagination>
        )}
      </div>
    </div>
  );
}
