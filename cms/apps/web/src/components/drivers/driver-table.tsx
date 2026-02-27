"use client";

import { MoreHorizontal } from "lucide-react";
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
import type { Driver } from "@/types/driver";

interface DriverTableProps {
  drivers: Driver[];
  totalItems: number;
  page: number;
  pageSize: number;
  onPageChange: (page: number) => void;
  selectedDriver: Driver | null;
  onSelectDriver: (driver: Driver) => void;
  onEditDriver: (driver: Driver) => void;
  onDeleteDriver: (driver: Driver) => void;
  isLoading: boolean;
  isReadOnly: boolean;
}

function StatusBadge({ status }: { status: string }) {
  const t = useTranslations("drivers.statuses");
  const colorMap: Record<string, string> = {
    available: "bg-status-ontime/10 text-status-ontime border-status-ontime/20",
    on_duty: "bg-surface-secondary text-foreground-muted border-border",
    on_leave: "bg-status-delayed/10 text-status-delayed border-status-delayed/20",
    sick: "bg-status-critical/10 text-status-critical border-status-critical/20",
  };
  return (
    <Badge variant="outline" className={cn("text-xs", colorMap[status] ?? "")}>
      {t(status)}
    </Badge>
  );
}

function ShiftBadge({ shift }: { shift: string }) {
  const t = useTranslations("drivers.shifts");
  return (
    <Badge variant="outline" className="text-xs">
      {t(shift)}
    </Badge>
  );
}

function isLicenseExpiringSoon(dateStr: string | null): "expired" | "warning" | null {
  if (!dateStr) return null;
  const expiry = new Date(dateStr);
  const now = new Date();
  const thirtyDaysFromNow = new Date();
  thirtyDaysFromNow.setDate(thirtyDaysFromNow.getDate() + 30);
  if (expiry < now) return "expired";
  if (expiry < thirtyDaysFromNow) return "warning";
  return null;
}

export function DriverTable({
  drivers,
  totalItems,
  page,
  pageSize,
  onPageChange,
  selectedDriver,
  onSelectDriver,
  onEditDriver,
  onDeleteDriver,
  isLoading,
  isReadOnly,
}: DriverTableProps) {
  const t = useTranslations("drivers");
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

  if (drivers.length === 0) {
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
              <TableHead>{t("table.employeeNumber")}</TableHead>
              <TableHead>{t("table.name")}</TableHead>
              <TableHead>{t("table.status")}</TableHead>
              <TableHead>{t("table.shift")}</TableHead>
              <TableHead className="hidden lg:table-cell">{t("table.phone")}</TableHead>
              <TableHead className="hidden lg:table-cell">{t("table.licenseExpiry")}</TableHead>
              <TableHead className="w-10">
                <span className="sr-only">{t("table.actions")}</span>
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {drivers.map((driver) => {
              const licenseStatus = isLicenseExpiringSoon(driver.license_expiry_date);
              return (
                <TableRow
                  key={driver.id}
                  className={cn(
                    "cursor-pointer",
                    selectedDriver?.id === driver.id && "bg-selected-bg",
                  )}
                  onClick={() => onSelectDriver(driver)}
                >
                  <TableCell className="font-mono text-xs">
                    {driver.employee_number}
                  </TableCell>
                  <TableCell className="font-medium">
                    {driver.first_name} {driver.last_name}
                  </TableCell>
                  <TableCell>
                    <StatusBadge status={driver.status} />
                  </TableCell>
                  <TableCell>
                    <ShiftBadge shift={driver.default_shift} />
                  </TableCell>
                  <TableCell className="hidden lg:table-cell text-foreground-muted">
                    {driver.phone ?? "-"}
                  </TableCell>
                  <TableCell className="hidden lg:table-cell">
                    {driver.license_expiry_date ? (
                      <span
                        className={cn(
                          licenseStatus === "expired" && "text-status-critical font-medium",
                          licenseStatus === "warning" && "text-status-delayed font-medium",
                        )}
                      >
                        {driver.license_expiry_date}
                      </span>
                    ) : (
                      <span className="text-foreground-muted">-</span>
                    )}
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
                            <span className="sr-only">{t("table.actions")}</span>
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuItem
                            onClick={(e) => {
                              e.stopPropagation();
                              onEditDriver(driver);
                            }}
                          >
                            {t("actions.edit")}
                          </DropdownMenuItem>
                          <DropdownMenuItem
                            onClick={(e) => {
                              e.stopPropagation();
                              onDeleteDriver(driver);
                            }}
                            className="text-status-critical"
                          >
                            {t("actions.delete")}
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    )}
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </div>

      {/* Pagination */}
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
                  <PaginationItem key={`ellipsis-${idx}`} className="hidden sm:inline-flex">
                    <PaginationEllipsis className="size-8" />
                  </PaginationItem>
                ) : (
                  <PaginationItem key={item} className="hidden sm:inline-flex">
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
                  onClick={() => onPageChange(Math.min(totalPages, page + 1))}
                  aria-disabled={page === totalPages}
                  className={cn(
                    "h-8 w-8 p-0 [&>svg]:size-4 [&>span]:hidden",
                    page === totalPages && "pointer-events-none opacity-50",
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
