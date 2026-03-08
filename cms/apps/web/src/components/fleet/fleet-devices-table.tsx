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
import type { TrackedDevice } from "@/types/fleet";

interface FleetDevicesTableProps {
  devices: TrackedDevice[];
  totalItems: number;
  page: number;
  pageSize: number;
  onPageChange: (page: number) => void;
  selectedDevice: TrackedDevice | null;
  onSelectDevice: (device: TrackedDevice) => void;
  onEditDevice: (device: TrackedDevice) => void;
  onDeleteDevice: (device: TrackedDevice) => void;
  isLoading: boolean;
  isReadOnly: boolean;
  canDelete: boolean;
}

const STATUS_COLORS: Record<string, string> = {
  active: "bg-status-ontime/10 text-status-ontime border-status-ontime/20",
  inactive: "bg-surface-secondary text-foreground-muted border-border",
  offline: "bg-status-critical/10 text-status-critical border-status-critical/20",
};

function StatusBadge({ status }: { status: string }) {
  const t = useTranslations("fleet.filters");
  return (
    <Badge
      variant="outline"
      className={cn("text-xs", STATUS_COLORS[status] ?? "")}
    >
      {t(status)}
    </Badge>
  );
}

function formatRelativeTime(dateStr: string | null): string {
  if (!dateStr) return "";
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMin = Math.floor(diffMs / 60000);
  if (diffMin < 1) return "Just now";
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHrs = Math.floor(diffMin / 60);
  if (diffHrs < 24) return `${diffHrs}h ago`;
  const diffDays = Math.floor(diffHrs / 24);
  return `${diffDays}d ago`;
}

export function FleetDevicesTable({
  devices,
  totalItems,
  page,
  pageSize,
  onPageChange,
  selectedDevice,
  onSelectDevice,
  onEditDevice,
  onDeleteDevice,
  isLoading,
  isReadOnly,
  canDelete,
}: FleetDevicesTableProps) {
  const t = useTranslations("fleet");
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

  if (devices.length === 0) {
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
              <TableHead>{t("table.imei")}</TableHead>
              <TableHead>{t("table.deviceName")}</TableHead>
              <TableHead className="hidden lg:table-cell">
                {t("table.protocol")}
              </TableHead>
              <TableHead>{t("table.status")}</TableHead>
              <TableHead className="hidden lg:table-cell">
                {t("table.vehicle")}
              </TableHead>
              <TableHead className="hidden md:table-cell">
                {t("table.lastSeen")}
              </TableHead>
              <TableHead className="w-10">
                <span className="sr-only">{t("table.actions")}</span>
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {devices.map((device) => (
              <TableRow
                key={device.id}
                className={cn(
                  "cursor-pointer",
                  selectedDevice?.id === device.id && "bg-selected-bg",
                )}
                onClick={() => onSelectDevice(device)}
              >
                <TableCell className="font-mono text-xs">
                  {device.imei}
                </TableCell>
                <TableCell className="text-foreground-muted">
                  {device.device_name ?? "-"}
                </TableCell>
                <TableCell className="hidden lg:table-cell">
                  <Badge variant="outline" className="text-xs">
                    {device.protocol_type}
                  </Badge>
                </TableCell>
                <TableCell>
                  <StatusBadge status={device.status} />
                </TableCell>
                <TableCell className="hidden lg:table-cell text-foreground-muted">
                  {device.vehicle_id ?? t("table.unlinked")}
                </TableCell>
                <TableCell className="hidden md:table-cell text-foreground-muted text-xs">
                  {device.last_seen_at
                    ? formatRelativeTime(device.last_seen_at)
                    : t("table.neverSeen")}
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
                            onEditDevice(device);
                          }}
                        >
                          {t("actions.edit")}
                        </DropdownMenuItem>
                        {canDelete && (
                          <DropdownMenuItem
                            onClick={(e) => {
                              e.stopPropagation();
                              onDeleteDevice(device);
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
