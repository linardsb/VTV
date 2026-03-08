"use client";

import { Search } from "lucide-react";
import { useTranslations } from "next-intl";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";

interface FilterContentProps {
  search: string;
  onSearchChange: (value: string) => void;
  statusFilter: string;
  onStatusFilterChange: (value: string) => void;
  shiftFilter: string;
  onShiftFilterChange: (value: string) => void;
  resultCount: number;
}

function FilterContent({
  search,
  onSearchChange,
  statusFilter,
  onStatusFilterChange,
  shiftFilter,
  onShiftFilterChange,
  resultCount,
}: FilterContentProps) {
  const t = useTranslations("drivers");

  return (
    <>
      <div className="space-y-(--spacing-grid)">
        {/* Search */}
        <div className="relative">
          <Search
            className="absolute left-2.5 top-2.5 size-4 text-foreground-muted"
            aria-hidden="true"
          />
          <Input
            placeholder={t("search")}
            value={search}
            onChange={(e) => onSearchChange(e.target.value)}
            className="pl-9"
            aria-label={t("search")}
          />
        </div>

        <Separator />

        {/* Status Filter */}
        <div className="space-y-(--spacing-tight)">
          <p className="text-xs font-medium text-label-text uppercase tracking-wide">
            {t("filters.status")}
          </p>
          <Select
            value={statusFilter}
            onValueChange={onStatusFilterChange}
          >
            <SelectTrigger aria-label={t("filters.status")}>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">{t("filters.allStatuses")}</SelectItem>
              <SelectItem value="available">{t("filters.available")}</SelectItem>
              <SelectItem value="on_duty">{t("filters.on_duty")}</SelectItem>
              <SelectItem value="on_leave">{t("filters.on_leave")}</SelectItem>
              <SelectItem value="sick">{t("filters.sick")}</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <Separator />

        {/* Shift Filter */}
        <div className="space-y-(--spacing-tight)">
          <p className="text-xs font-medium text-label-text uppercase tracking-wide">
            {t("filters.shift")}
          </p>
          <Select
            value={shiftFilter}
            onValueChange={onShiftFilterChange}
          >
            <SelectTrigger aria-label={t("filters.shift")}>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">{t("filters.allShifts")}</SelectItem>
              <SelectItem value="morning">{t("filters.morning")}</SelectItem>
              <SelectItem value="afternoon">{t("filters.afternoon")}</SelectItem>
              <SelectItem value="evening">{t("filters.evening")}</SelectItem>
              <SelectItem value="night">{t("filters.night")}</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* Result count */}
      <div className="mt-auto pt-(--spacing-card)">
        <p className="text-xs text-foreground-muted">
          {resultCount} {t("table.showing").toLowerCase()}
        </p>
      </div>
    </>
  );
}

interface DriverFiltersProps {
  search: string;
  onSearchChange: (value: string) => void;
  statusFilter: string;
  onStatusFilterChange: (value: string) => void;
  shiftFilter: string;
  onShiftFilterChange: (value: string) => void;
  resultCount: number;
  asSheet?: boolean;
  sheetOpen?: boolean;
  onSheetOpenChange?: (open: boolean) => void;
}

export function DriverFilters({
  search,
  onSearchChange,
  statusFilter,
  onStatusFilterChange,
  shiftFilter,
  onShiftFilterChange,
  resultCount,
  asSheet,
  sheetOpen,
  onSheetOpenChange,
}: DriverFiltersProps) {
  const t = useTranslations("drivers");

  if (asSheet) {
    return (
      <Sheet open={sheetOpen} onOpenChange={onSheetOpenChange}>
        <SheetContent side="left" className="w-[280px] flex flex-col p-(--spacing-card)">
          <SheetHeader>
            <SheetTitle className="font-heading text-sm font-semibold">
              {t("mobile.showFilters")}
            </SheetTitle>
          </SheetHeader>
          <FilterContent
            search={search}
            onSearchChange={onSearchChange}
            statusFilter={statusFilter}
            onStatusFilterChange={onStatusFilterChange}
            shiftFilter={shiftFilter}
            onShiftFilterChange={onShiftFilterChange}
            resultCount={resultCount}
          />
        </SheetContent>
      </Sheet>
    );
  }

  return (
    <aside className="flex w-52 shrink-0 flex-col border-r border-border bg-surface p-(--spacing-card)">
      <FilterContent
        search={search}
        onSearchChange={onSearchChange}
        statusFilter={statusFilter}
        onStatusFilterChange={onStatusFilterChange}
        shiftFilter={shiftFilter}
        onShiftFilterChange={onShiftFilterChange}
        resultCount={resultCount}
      />
    </aside>
  );
}
