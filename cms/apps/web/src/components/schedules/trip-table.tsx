"use client";

import { useMemo } from "react";
import { useTranslations } from "next-intl";
import { Pencil, Trash2, MoreHorizontal } from "lucide-react";
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
import { Skeleton } from "@/components/ui/skeleton";
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
import { RouteTypeBadge } from "@/components/routes/route-type-badge";
import type { Trip } from "@/types/schedule";
import type { Route } from "@/types/route";
import type { Calendar } from "@/types/schedule";

interface TripTableProps {
  trips: Trip[];
  routes: Route[];
  calendars: Calendar[];
  total: number;
  page: number;
  pageSize: number;
  onPageChange: (page: number) => void;
  onSelect: (trip: Trip) => void;
  onEdit: (trip: Trip) => void;
  onDelete: (trip: Trip) => void;
  isReadOnly: boolean;
  isLoading: boolean;
}

export function TripTable({
  trips,
  routes,
  calendars,
  total,
  page,
  pageSize,
  onPageChange,
  onSelect,
  onEdit,
  onDelete,
  isReadOnly,
  isLoading,
}: TripTableProps) {
  const t = useTranslations("schedules.trips");

  const routeMap = useMemo(() => {
    const map: Record<number, string> = {};
    for (const r of routes) map[r.id] = r.route_short_name;
    return map;
  }, [routes]);

  const routeTypeMap = useMemo(() => {
    const map: Record<number, number> = {};
    for (const r of routes) map[r.id] = r.route_type;
    return map;
  }, [routes]);

  const calendarMap = useMemo(() => {
    const map: Record<number, string> = {};
    for (const c of calendars) map[c.id] = c.gtfs_service_id;
    return map;
  }, [calendars]);

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  if (!isLoading && trips.length === 0) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-(--spacing-grid) py-20">
        <p className="text-lg font-medium text-foreground">{t("noResults")}</p>
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
              <TableHead>{t("tripId")}</TableHead>
              <TableHead>{t("route")}</TableHead>
              <TableHead className="hidden sm:table-cell">{t("type")}</TableHead>
              <TableHead className="hidden md:table-cell">{t("calendar")}</TableHead>
              <TableHead className="hidden lg:table-cell w-24">{t("direction")}</TableHead>
              <TableHead className="hidden xl:table-cell">{t("headsign")}</TableHead>
              {!isReadOnly && (
                <TableHead className="w-16">
                  <span className="sr-only">{t("actions")}</span>
                </TableHead>
              )}
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading
              ? Array.from({ length: 5 }, (_, i) => (
                  <TableRow key={`skeleton-${i}`}>
                    <TableCell><Skeleton className="h-5 w-24" /></TableCell>
                    <TableCell><Skeleton className="h-5 w-16" /></TableCell>
                    <TableCell className="hidden sm:table-cell"><Skeleton className="h-5 w-20" /></TableCell>
                    <TableCell className="hidden md:table-cell"><Skeleton className="h-5 w-20" /></TableCell>
                    <TableCell className="hidden lg:table-cell"><Skeleton className="h-5 w-12" /></TableCell>
                    <TableCell className="hidden xl:table-cell"><Skeleton className="h-5 w-32" /></TableCell>
                    {!isReadOnly && <TableCell><Skeleton className="h-5 w-8" /></TableCell>}
                  </TableRow>
                ))
              : trips.map((trip) => (
                  <TableRow
                    key={trip.id}
                    className="cursor-pointer transition-colors"
                    onClick={() => onSelect(trip)}
                  >
                    <TableCell className="font-mono font-medium">{trip.gtfs_trip_id}</TableCell>
                    <TableCell>
                      <Badge variant="outline">{routeMap[trip.route_id] ?? "-"}</Badge>
                    </TableCell>
                    <TableCell className="hidden sm:table-cell">
                      {routeTypeMap[trip.route_id] !== undefined ? (
                        <RouteTypeBadge type={routeTypeMap[trip.route_id]} />
                      ) : "-"}
                    </TableCell>
                    <TableCell className="hidden md:table-cell text-foreground-muted">
                      {calendarMap[trip.calendar_id] ?? "-"}
                    </TableCell>
                    <TableCell className="hidden lg:table-cell">
                      {trip.direction_id !== null ? (
                        <Badge variant="outline" className="text-xs">
                          {trip.direction_id === 0 ? t("outbound") : t("inbound")}
                        </Badge>
                      ) : "-"}
                    </TableCell>
                    <TableCell className="hidden xl:table-cell text-foreground-muted">
                      {trip.trip_headsign ?? "-"}
                    </TableCell>
                    {!isReadOnly && (
                      <TableCell>
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button
                              variant="ghost"
                              size="sm"
                              className="size-8 p-0"
                              onClick={(e) => e.stopPropagation()}
                            >
                              <MoreHorizontal className="size-4" />
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            <DropdownMenuItem onClick={() => onEdit(trip)}>
                              <Pencil className="mr-2 size-4" />
                              {t("edit")}
                            </DropdownMenuItem>
                            <DropdownMenuItem
                              className="text-status-critical"
                              onClick={() => onDelete(trip)}
                            >
                              <Trash2 className="mr-2 size-4" />
                              {t("delete")}
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

      <div className="flex items-center justify-between border-t border-border px-(--spacing-card) py-(--spacing-tight)">
        <p className="hidden sm:block text-xs text-foreground-muted">
          {total > 0 ? `${from}-${to} / ${total}` : ""}
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
              {Array.from({ length: Math.min(totalPages, 5) }, (_, i) => (
                <PaginationItem key={i + 1} className="hidden sm:inline-flex">
                  <PaginationLink isActive={i + 1 === page} onClick={() => onPageChange(i + 1)}>
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
