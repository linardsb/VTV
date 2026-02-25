"use client";

import { useMemo } from "react";
import { useTranslations, useLocale } from "next-intl";
import { Pencil, Trash2, MoreHorizontal, Check, X } from "lucide-react";
import { CalendarStatusBadge } from "@/components/schedules/calendar-status-badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
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
import type { Calendar } from "@/types/schedule";

const DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"] as const;

function DayIndicator({ active }: { active: boolean }) {
  return active ? (
    <Check className="size-3.5 text-status-ontime" aria-label="active" />
  ) : (
    <X className="size-3.5 text-foreground-subtle" aria-label="inactive" />
  );
}

interface CalendarTableProps {
  calendars: Calendar[];
  total: number;
  page: number;
  pageSize: number;
  onPageChange: (page: number) => void;
  onSelect: (calendar: Calendar) => void;
  onEdit: (calendar: Calendar) => void;
  onDelete: (calendar: Calendar) => void;
  isReadOnly: boolean;
  isLoading: boolean;
}

export function CalendarTable({
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
}: CalendarTableProps) {
  const t = useTranslations("schedules.calendars");
  const tDays = useTranslations("schedules.days");
  const locale = useLocale();

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  const dateFormatter = useMemo(
    () => new Intl.DateTimeFormat(locale, { year: "numeric", month: "short", day: "numeric" }),
    [locale]
  );

  const createdFormatter = useMemo(
    () => new Intl.DateTimeFormat(locale, { year: "numeric", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }),
    [locale]
  );

  if (!isLoading && calendars.length === 0) {
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
              <TableHead>{t("serviceId")}</TableHead>
              {DAYS.map((day) => (
                <TableHead key={day} className="w-10 text-center hidden sm:table-cell">
                  {tDays(day.slice(0, 3))}
                </TableHead>
              ))}
              <TableHead className="hidden md:table-cell">{t("dateRange")}</TableHead>
              <TableHead className="hidden lg:table-cell">{t("status")}</TableHead>
              <TableHead className="hidden xl:table-cell">{t("createdBy")}</TableHead>
              <TableHead className="hidden xl:table-cell">{t("createdAt")}</TableHead>
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
                    {DAYS.map((day) => (
                      <TableCell key={day} className="hidden sm:table-cell"><Skeleton className="mx-auto h-4 w-4" /></TableCell>
                    ))}
                    <TableCell className="hidden md:table-cell"><Skeleton className="h-5 w-32" /></TableCell>
                    <TableCell className="hidden lg:table-cell"><Skeleton className="h-5 w-16" /></TableCell>
                    <TableCell className="hidden xl:table-cell"><Skeleton className="h-5 w-24" /></TableCell>
                    <TableCell className="hidden xl:table-cell"><Skeleton className="h-5 w-28" /></TableCell>
                    {!isReadOnly && <TableCell><Skeleton className="h-5 w-8" /></TableCell>}
                  </TableRow>
                ))
              : calendars.map((cal) => (
                  <TableRow
                    key={cal.id}
                    className="cursor-pointer transition-colors"
                    onClick={() => onSelect(cal)}
                  >
                    <TableCell className="font-mono font-medium">{cal.gtfs_service_id}</TableCell>
                    {DAYS.map((day) => (
                      <TableCell key={day} className="text-center hidden sm:table-cell">
                        <DayIndicator active={cal[day]} />
                      </TableCell>
                    ))}
                    <TableCell className="hidden md:table-cell text-foreground-muted text-sm">
                      {dateFormatter.format(new Date(cal.start_date))} — {dateFormatter.format(new Date(cal.end_date))}
                    </TableCell>
                    <TableCell className="hidden lg:table-cell">
                      <CalendarStatusBadge startDate={cal.start_date} endDate={cal.end_date} />
                    </TableCell>
                    <TableCell className="hidden xl:table-cell text-foreground-muted text-sm whitespace-nowrap">
                      {cal.created_by_name || "-"}
                    </TableCell>
                    <TableCell className="hidden xl:table-cell text-foreground-muted text-xs whitespace-nowrap">
                      {createdFormatter.format(new Date(cal.created_at))}
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
                            <DropdownMenuItem onClick={() => onEdit(cal)}>
                              <Pencil className="mr-2 size-4" />
                              {t("edit")}
                            </DropdownMenuItem>
                            <DropdownMenuItem
                              className="text-status-critical"
                              onClick={() => onDelete(cal)}
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
