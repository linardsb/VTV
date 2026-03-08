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
  typeFilter: string;
  onTypeFilterChange: (value: string) => void;
  statusFilter: string;
  onStatusFilterChange: (value: string) => void;
  resultCount: number;
}

function FilterContent({
  search,
  onSearchChange,
  typeFilter,
  onTypeFilterChange,
  statusFilter,
  onStatusFilterChange,
  resultCount,
}: FilterContentProps) {
  const t = useTranslations("vehicles");

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

        {/* Type Filter */}
        <div className="space-y-(--spacing-tight)">
          <p className="text-xs font-medium text-label-text uppercase tracking-wide">
            {t("filters.type")}
          </p>
          <Select value={typeFilter} onValueChange={onTypeFilterChange}>
            <SelectTrigger aria-label={t("filters.type")}>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">{t("filters.allTypes")}</SelectItem>
              <SelectItem value="bus">{t("filters.bus")}</SelectItem>
              <SelectItem value="trolleybus">
                {t("filters.trolleybus")}
              </SelectItem>
              <SelectItem value="tram">{t("filters.tram")}</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <Separator />

        {/* Status Filter */}
        <div className="space-y-(--spacing-tight)">
          <p className="text-xs font-medium text-label-text uppercase tracking-wide">
            {t("filters.status")}
          </p>
          <Select value={statusFilter} onValueChange={onStatusFilterChange}>
            <SelectTrigger aria-label={t("filters.status")}>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">
                {t("filters.allStatuses")}
              </SelectItem>
              <SelectItem value="active">
                {t("filters.active")}
              </SelectItem>
              <SelectItem value="inactive">
                {t("filters.inactive")}
              </SelectItem>
              <SelectItem value="maintenance">
                {t("filters.maintenance")}
              </SelectItem>
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

interface VehicleFiltersProps {
  search: string;
  onSearchChange: (value: string) => void;
  typeFilter: string;
  onTypeFilterChange: (value: string) => void;
  statusFilter: string;
  onStatusFilterChange: (value: string) => void;
  resultCount: number;
  asSheet?: boolean;
  sheetOpen?: boolean;
  onSheetOpenChange?: (open: boolean) => void;
}

export function VehicleFilters({
  search,
  onSearchChange,
  typeFilter,
  onTypeFilterChange,
  statusFilter,
  onStatusFilterChange,
  resultCount,
  asSheet,
  sheetOpen,
  onSheetOpenChange,
}: VehicleFiltersProps) {
  const t = useTranslations("vehicles");

  if (asSheet) {
    return (
      <Sheet open={sheetOpen} onOpenChange={onSheetOpenChange}>
        <SheetContent
          side="left"
          className="w-[280px] flex flex-col p-(--spacing-card)"
        >
          <SheetHeader>
            <SheetTitle className="font-heading text-sm font-semibold">
              {t("mobile.showFilters")}
            </SheetTitle>
          </SheetHeader>
          <FilterContent
            search={search}
            onSearchChange={onSearchChange}
            typeFilter={typeFilter}
            onTypeFilterChange={onTypeFilterChange}
            statusFilter={statusFilter}
            onStatusFilterChange={onStatusFilterChange}
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
        typeFilter={typeFilter}
        onTypeFilterChange={onTypeFilterChange}
        statusFilter={statusFilter}
        onStatusFilterChange={onStatusFilterChange}
        resultCount={resultCount}
      />
    </aside>
  );
}
