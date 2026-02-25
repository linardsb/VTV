"use client";

import { Search } from "lucide-react";
import { useTranslations } from "next-intl";
import { Input } from "@/components/ui/input";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
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
  locationTypeFilter: string;
  onLocationTypeFilterChange: (value: string) => void;
  resultCount: number;
}

function FilterContent({
  search,
  onSearchChange,
  statusFilter,
  onStatusFilterChange,
  locationTypeFilter,
  onLocationTypeFilterChange,
  resultCount,
}: FilterContentProps) {
  const t = useTranslations("stops");

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
              <SelectItem value="active">{t("filters.active")}</SelectItem>
              <SelectItem value="inactive">{t("filters.inactive")}</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <Separator />

        {/* Location Type Filter */}
        <div className="space-y-(--spacing-tight)">
          <p className="text-xs font-medium text-label-text uppercase tracking-wide">
            {t("filters.locationType")}
          </p>
          <ToggleGroup
            type="single"
            spacing={1}
            value={locationTypeFilter}
            onValueChange={(value) => {
              onLocationTypeFilterChange(value || "all");
            }}
            className="flex flex-col gap-1"
          >
            <ToggleGroupItem
              value="all"
              className="w-full justify-start rounded-md text-sm data-[state=on]:bg-filter-active-bg data-[state=on]:text-filter-active-text data-[state=on]:font-semibold"
            >
              {t("filters.allTypes")}
            </ToggleGroupItem>
            <ToggleGroupItem
              value="0"
              className="w-full justify-start rounded-md text-sm data-[state=on]:bg-filter-active-bg data-[state=on]:text-filter-active-text data-[state=on]:font-semibold"
            >
              {t("filters.stop")}
            </ToggleGroupItem>
            <ToggleGroupItem
              value="terminal"
              className="w-full justify-start rounded-md text-sm data-[state=on]:bg-filter-active-bg data-[state=on]:text-filter-active-text data-[state=on]:font-semibold"
            >
              {t("filters.station")}
            </ToggleGroupItem>
          </ToggleGroup>
        </div>
      </div>

      {/* Result count */}
      <div className="mt-auto pt-(--spacing-card)">
        <p className="text-xs text-foreground-muted">
          {resultCount} {t("table.name").toLowerCase()}
        </p>
      </div>
    </>
  );
}

interface StopFiltersProps {
  search: string;
  onSearchChange: (value: string) => void;
  statusFilter: string;
  onStatusFilterChange: (value: string) => void;
  locationTypeFilter: string;
  onLocationTypeFilterChange: (value: string) => void;
  resultCount: number;
  asSheet?: boolean;
  sheetOpen?: boolean;
  onSheetOpenChange?: (open: boolean) => void;
}

export function StopFilters({
  search,
  onSearchChange,
  statusFilter,
  onStatusFilterChange,
  locationTypeFilter,
  onLocationTypeFilterChange,
  resultCount,
  asSheet,
  sheetOpen,
  onSheetOpenChange,
}: StopFiltersProps) {
  const t = useTranslations("stops");

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
            locationTypeFilter={locationTypeFilter}
            onLocationTypeFilterChange={onLocationTypeFilterChange}
            resultCount={resultCount}
          />
        </SheetContent>
      </Sheet>
    );
  }

  return (
    <aside className="flex w-60 shrink-0 flex-col border-r border-border bg-surface p-(--spacing-card)">
      <FilterContent
        search={search}
        onSearchChange={onSearchChange}
        statusFilter={statusFilter}
        onStatusFilterChange={onStatusFilterChange}
        locationTypeFilter={locationTypeFilter}
        onLocationTypeFilterChange={onLocationTypeFilterChange}
        resultCount={resultCount}
      />
    </aside>
  );
}
