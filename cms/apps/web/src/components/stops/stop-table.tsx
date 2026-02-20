"use client";

import { useCallback, useState } from "react";
import { useTranslations } from "next-intl";
import { Check, Copy, MoreHorizontal, Pencil, Trash2 } from "lucide-react";
import { toast } from "sonner";
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

function CopyGtfsButton({ gtfsId, label, copiedLabel }: { gtfsId: string; label: string; copiedLabel: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = useCallback(
    (e: React.MouseEvent) => {
      e.stopPropagation();
      void navigator.clipboard.writeText(gtfsId).then(() => {
        setCopied(true);
        toast.success(copiedLabel);
        setTimeout(() => setCopied(false), 2000);
      });
    },
    [gtfsId, copiedLabel],
  );

  return (
    <button
      type="button"
      onClick={handleCopy}
      className="inline-flex items-center gap-1 rounded px-1 py-0.5 font-mono text-xs text-foreground-muted transition-colors hover:bg-surface hover:text-foreground"
      title={label}
      aria-label={`${label}: ${gtfsId}`}
    >
      {gtfsId}
      {copied ? (
        <Check className="size-3 text-status-ontime" />
      ) : (
        <Copy className="size-3 opacity-0 transition-opacity group-hover/row:opacity-100" />
      )}
    </button>
  );
}

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
                  "group/row cursor-pointer transition-colors",
                  selectedStopId === stop.id && "bg-selected-bg",
                )}
                onClick={() => onSelectStop(stop)}
              >
                <TableCell>
                  <div className="flex flex-col gap-0.5">
                    <span className="font-medium">{stop.stop_name}</span>
                    {stop.stop_desc && (
                      <span className="text-xs text-foreground-muted">
                        {stop.stop_desc}
                      </span>
                    )}
                    <CopyGtfsButton
                      gtfsId={stop.gtfs_stop_id}
                      label={t("table.copyGtfsId")}
                      copiedLabel={t("table.copied")}
                    />
                  </div>
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
