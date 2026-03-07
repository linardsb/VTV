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
import type { Vehicle } from "@/types/vehicle";

interface VehicleTableProps {
  vehicles: Vehicle[];
  totalItems: number;
  page: number;
  pageSize: number;
  onPageChange: (page: number) => void;
  selectedVehicle: Vehicle | null;
  onSelectVehicle: (vehicle: Vehicle) => void;
  onEditVehicle: (vehicle: Vehicle) => void;
  onDeleteVehicle: (vehicle: Vehicle) => void;
  isLoading: boolean;
  isReadOnly: boolean;
  canDelete: boolean;
}

const STATUS_COLORS: Record<string, string> = {
  active: "bg-status-ontime/10 text-status-ontime border-status-ontime/20",
  inactive: "bg-surface-secondary text-foreground-muted border-border",
  maintenance:
    "bg-status-delayed/10 text-status-delayed border-status-delayed/20",
};

const TYPE_COLORS: Record<string, string> = {
  bus: "bg-transport-bus/10 text-transport-bus border-transport-bus/20",
  trolleybus:
    "bg-transport-trolleybus/10 text-transport-trolleybus border-transport-trolleybus/20",
  tram: "bg-transport-tram/10 text-transport-tram border-transport-tram/20",
};

function StatusBadge({ status }: { status: string }) {
  const t = useTranslations("vehicles.statuses");
  return (
    <Badge
      variant="outline"
      className={cn("text-xs", STATUS_COLORS[status] ?? "")}
    >
      {t(status)}
    </Badge>
  );
}

function TypeBadge({ type }: { type: string }) {
  const t = useTranslations("vehicles.types");
  return (
    <Badge
      variant="outline"
      className={cn("text-xs", TYPE_COLORS[type] ?? "")}
    >
      {t(type)}
    </Badge>
  );
}

export function VehicleTable({
  vehicles,
  totalItems,
  page,
  pageSize,
  onPageChange,
  selectedVehicle,
  onSelectVehicle,
  onEditVehicle,
  onDeleteVehicle,
  isLoading,
  isReadOnly,
  canDelete,
}: VehicleTableProps) {
  const t = useTranslations("vehicles");
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

  if (vehicles.length === 0) {
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
              <TableHead>{t("table.fleetNumber")}</TableHead>
              <TableHead>{t("table.type")}</TableHead>
              <TableHead>{t("table.licensePlate")}</TableHead>
              <TableHead>{t("table.status")}</TableHead>
              <TableHead className="hidden lg:table-cell">
                {t("table.manufacturer")}
              </TableHead>
              <TableHead className="hidden lg:table-cell">
                {t("table.capacity")}
              </TableHead>
              <TableHead className="w-10">
                <span className="sr-only">{t("table.actions")}</span>
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {vehicles.map((vehicle) => (
              <TableRow
                key={vehicle.id}
                className={cn(
                  "cursor-pointer",
                  selectedVehicle?.id === vehicle.id && "bg-selected-bg",
                )}
                onClick={() => onSelectVehicle(vehicle)}
              >
                <TableCell className="font-mono text-xs">
                  {vehicle.fleet_number}
                </TableCell>
                <TableCell>
                  <TypeBadge type={vehicle.vehicle_type} />
                </TableCell>
                <TableCell>{vehicle.license_plate}</TableCell>
                <TableCell>
                  <StatusBadge status={vehicle.status} />
                </TableCell>
                <TableCell className="hidden lg:table-cell text-foreground-muted">
                  {vehicle.manufacturer ?? "-"}
                </TableCell>
                <TableCell className="hidden lg:table-cell text-foreground-muted">
                  {vehicle.capacity ?? "-"}
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
                            onEditVehicle(vehicle);
                          }}
                        >
                          {t("actions.edit")}
                        </DropdownMenuItem>
                        {canDelete && (
                          <DropdownMenuItem
                            onClick={(e) => {
                              e.stopPropagation();
                              onDeleteVehicle(vehicle);
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
