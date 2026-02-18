"use client";

import { useState, useMemo } from "react";
import { useTranslations } from "next-intl";
import { MoreHorizontal, Pencil, Copy, Trash2, ArrowUpDown } from "lucide-react";
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
import { RouteTypeBadge } from "./route-type-badge";
import type { Route } from "@/types/route";

const PAGE_SIZE = 10;

type SortField = "shortName" | "longName" | "type" | "agencyId";
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
  selectedRouteId: string | null;
  onSelectRoute: (routeId: string) => void;
  onEditRoute: (route: Route) => void;
  onDeleteRoute: (route: Route) => void;
  onDuplicateRoute: (route: Route) => void;
  isReadOnly: boolean;
}

export function RouteTable({
  routes,
  selectedRouteId,
  onSelectRoute,
  onEditRoute,
  onDeleteRoute,
  onDuplicateRoute,
  isReadOnly,
}: RouteTableProps) {
  const t = useTranslations("routes");
  const [page, setPage] = useState(0);
  const [sortField, setSortField] = useState<SortField>("shortName");
  const [sortDir, setSortDir] = useState<SortDir>("asc");

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

  const totalPages = Math.max(1, Math.ceil(sorted.length / PAGE_SIZE));
  const safePage = Math.min(page, totalPages - 1);
  const paginated = sorted.slice(safePage * PAGE_SIZE, (safePage + 1) * PAGE_SIZE);

  function toggleSort(field: SortField) {
    if (sortField === field) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortField(field);
      setSortDir("asc");
    }
  }

  if (routes.length === 0) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-(--spacing-grid) py-20">
        <p className="text-lg font-medium text-foreground">{t("table.noResults")}</p>
        <p className="text-sm text-foreground-muted">{t("description")}</p>
      </div>
    );
  }

  const from = safePage * PAGE_SIZE + 1;
  const to = Math.min((safePage + 1) * PAGE_SIZE, sorted.length);

  return (
    <div className="flex flex-1 flex-col">
      <div className="flex-1 overflow-auto">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-20">
                <SortableHeader onToggle={toggleSort} field="shortName">{t("table.routeNumber")}</SortableHeader>
              </TableHead>
              <TableHead>
                <SortableHeader onToggle={toggleSort} field="longName">{t("table.name")}</SortableHeader>
              </TableHead>
              <TableHead className="hidden sm:table-cell w-32">
                <SortableHeader onToggle={toggleSort} field="type">{t("table.type")}</SortableHeader>
              </TableHead>
              <TableHead className="hidden md:table-cell w-44">
                <SortableHeader onToggle={toggleSort} field="agencyId">{t("table.agency")}</SortableHeader>
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
            {paginated.map((route) => (
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
                      style={{ backgroundColor: route.color }}
                      aria-hidden="true"
                    />
                    <span className="font-semibold">{route.shortName}</span>
                  </div>
                </TableCell>
                <TableCell className="text-foreground">{route.longName}</TableCell>
                <TableCell className="hidden sm:table-cell">
                  <RouteTypeBadge type={route.type} />
                </TableCell>
                <TableCell className="hidden md:table-cell text-foreground-muted">
                  {t(`agencies.${route.agencyId}`)}
                </TableCell>
                <TableCell>
                  <Badge
                    variant="outline"
                    className={cn(
                      "text-xs",
                      route.isActive
                        ? "border-status-ontime/30 bg-status-ontime/10 text-status-ontime"
                        : "border-status-delayed/30 bg-status-delayed/10 text-status-delayed"
                    )}
                  >
                    {route.isActive ? t("filters.active") : t("filters.inactive")}
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
                        <DropdownMenuItem onClick={() => onDuplicateRoute(route)}>
                          <Copy className="mr-2 size-4" />
                          {t("actions.duplicate")}
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
          {t("table.showing", { from, to, total: sorted.length })}
        </p>
        {totalPages > 1 && (
          <Pagination>
            <PaginationContent>
              <PaginationItem>
                <PaginationPrevious
                  onClick={() => setPage((p) => Math.max(0, p - 1))}
                  aria-disabled={safePage === 0}
                  className={cn(safePage === 0 && "pointer-events-none opacity-50")}
                />
              </PaginationItem>
              {Array.from({ length: totalPages }, (_, i) => (
                <PaginationItem key={i} className="hidden sm:inline-flex">
                  <PaginationLink
                    isActive={i === safePage}
                    onClick={() => setPage(i)}
                  >
                    {i + 1}
                  </PaginationLink>
                </PaginationItem>
              ))}
              <PaginationItem>
                <PaginationNext
                  onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
                  aria-disabled={safePage === totalPages - 1}
                  className={cn(safePage === totalPages - 1 && "pointer-events-none opacity-50")}
                />
              </PaginationItem>
            </PaginationContent>
          </Pagination>
        )}
      </div>
    </div>
  );
}
