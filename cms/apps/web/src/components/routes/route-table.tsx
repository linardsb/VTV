"use client";

import { useMemo, useState } from "react";
import { useTranslations } from "next-intl";
import { MoreHorizontal, Pencil, Trash2, ArrowUpDown } from "lucide-react";
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
import { toHexColor } from "@/lib/color-utils";
import { RouteTypeBadge } from "./route-type-badge";
import type { Route } from "@/types/route";
import type { Agency } from "@/types/schedule";

type SortField = "route_short_name" | "route_long_name" | "route_type" | "agency_id";
type SortDir = "asc" | "desc";

function SortableHeader({
  field,
  children,
  onToggle,
}: {
  field: SortField;
  children: React.ReactNode;
  onToggle: (field: SortField) => void;
}) {
  return (
    <Button
      variant="ghost"
      size="sm"
      className="-ml-3 h-8 cursor-pointer"
      onClick={() => onToggle(field)}
    >
      {children}
      <ArrowUpDown className="ml-1 size-3" aria-hidden="true" />
    </Button>
  );
}

interface RouteTableProps {
  routes: Route[];
  selectedRouteId: number | null;
  onSelectRoute: (routeId: number) => void;
  onEditRoute: (route: Route) => void;
  onDeleteRoute: (route: Route) => void;
  isReadOnly: boolean;
  agencies: Agency[];
  total: number;
  page: number;
  pageSize: number;
  onPageChange: (page: number) => void;
  isLoading: boolean;
}

export function RouteTable({
  routes,
  selectedRouteId,
  onSelectRoute,
  onEditRoute,
  onDeleteRoute,
  isReadOnly,
  agencies,
  total,
  page,
  pageSize,
  onPageChange,
  isLoading,
}: RouteTableProps) {
  const t = useTranslations("routes");
  const [sortField, setSortField] = useState<SortField>("route_short_name");
  const [sortDir, setSortDir] = useState<SortDir>("asc");

  const agencyMap = useMemo(() => {
    const map: Record<number, string> = {};
    for (const a of agencies) {
      map[a.id] = a.agency_name;
    }
    return map;
  }, [agencies]);

  const sorted = useMemo(() => {
    const copy = [...routes];
    copy.sort((a, b) => {
      const aVal = a[sortField];
      const bVal = b[sortField];
      if (typeof aVal === "number" && typeof bVal === "number") {
        return sortDir === "asc" ? aVal - bVal : bVal - aVal;
      }
      const cmp = String(aVal).localeCompare(String(bVal), undefined, { numeric: true });
      return sortDir === "asc" ? cmp : -cmp;
    });
    return copy;
  }, [routes, sortField, sortDir]);

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  function toggleSort(field: SortField) {
    if (sortField === field) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortField(field);
      setSortDir("asc");
    }
  }

  if (!isLoading && routes.length === 0) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-(--spacing-grid) py-20">
        <p className="text-lg font-medium text-foreground">{t("table.noResults")}</p>
        <p className="text-sm text-foreground-muted">{t("description")}</p>
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
              <TableHead className="w-20">
                <SortableHeader onToggle={toggleSort} field="route_short_name">{t("table.routeNumber")}</SortableHeader>
              </TableHead>
              <TableHead>
                <SortableHeader onToggle={toggleSort} field="route_long_name">{t("table.name")}</SortableHeader>
              </TableHead>
              <TableHead className="hidden sm:table-cell w-32">
                <SortableHeader onToggle={toggleSort} field="route_type">{t("table.type")}</SortableHeader>
              </TableHead>
              <TableHead className="hidden md:table-cell w-44">
                <SortableHeader onToggle={toggleSort} field="agency_id">{t("table.agency")}</SortableHeader>
              </TableHead>
              <TableHead className="w-24">{t("table.status")}</TableHead>
              {!isReadOnly && (
                <TableHead className="w-16">
                  <span className="sr-only">{t("table.actions")}</span>
                </TableHead>
              )}
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading
              ? Array.from({ length: 5 }, (_, i) => (
                  <TableRow key={`skeleton-${i}`}>
                    <TableCell><Skeleton className="h-5 w-12" /></TableCell>
                    <TableCell><Skeleton className="h-5 w-40" /></TableCell>
                    <TableCell className="hidden sm:table-cell"><Skeleton className="h-5 w-20" /></TableCell>
                    <TableCell className="hidden md:table-cell"><Skeleton className="h-5 w-28" /></TableCell>
                    <TableCell><Skeleton className="h-5 w-16" /></TableCell>
                    {!isReadOnly && <TableCell><Skeleton className="h-5 w-8" /></TableCell>}
                  </TableRow>
                ))
              : sorted.map((route) => (
                  <TableRow
                    key={route.id}
                    className={cn(
                      "cursor-pointer transition-colors",
                      selectedRouteId === route.id && "bg-selected-bg"
                    )}
                    onClick={() => onSelectRoute(route.id)}
                  >
                    <TableCell>
                      <div className="flex items-center gap-(--spacing-tight)">
                        <span
                          className="inline-block size-3 shrink-0 rounded-full"
                          style={{ backgroundColor: toHexColor(route.route_color) }}
                          aria-hidden="true"
                        />
                        <span className="font-semibold">{route.route_short_name}</span>
                      </div>
                    </TableCell>
                    <TableCell className="text-foreground">{route.route_long_name}</TableCell>
                    <TableCell className="hidden sm:table-cell">
                      <RouteTypeBadge type={route.route_type} />
                    </TableCell>
                    <TableCell className="hidden md:table-cell text-foreground-muted">
                      {agencyMap[route.agency_id] ?? "-"}
                    </TableCell>
                    <TableCell>
                      <Badge
                        variant="outline"
                        className={cn(
                          "text-xs",
                          route.is_active
                            ? "border-status-ontime/30 bg-status-ontime/10 text-status-ontime"
                            : "border-status-delayed/30 bg-status-delayed/10 text-status-delayed"
                        )}
                      >
                        {route.is_active ? t("filters.active") : t("filters.inactive")}
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
                            <DropdownMenuItem onClick={() => onEditRoute(route)}>
                              <Pencil className="mr-2 size-4" />
                              {t("actions.edit")}
                            </DropdownMenuItem>
                            <DropdownMenuItem
                              className="text-status-critical"
                              onClick={() => onDeleteRoute(route)}
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
          {total > 0
            ? t("table.showing", { from, to, total })
            : ""}
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
              {Array.from({ length: Math.min(totalPages, 5) }, (_, i) => {
                const pageNum = i + 1;
                return (
                  <PaginationItem key={pageNum} className="hidden sm:inline-flex">
                    <PaginationLink
                      isActive={pageNum === page}
                      onClick={() => onPageChange(pageNum)}
                    >
                      {pageNum}
                    </PaginationLink>
                  </PaginationItem>
                );
              })}
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
