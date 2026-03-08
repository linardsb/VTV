"use client";

import { useTranslations } from "next-intl";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";

interface GeofencesFiltersProps {
  search: string;
  onSearchChange: (value: string) => void;
  zoneTypeFilter: string;
  onZoneTypeFilterChange: (value: string) => void;
  statusFilter: string;
  onStatusFilterChange: (value: string) => void;
  resultCount: number;
  asSheet?: boolean;
  sheetOpen?: boolean;
  onSheetOpenChange?: (open: boolean) => void;
}

function FilterContent({
  search,
  onSearchChange,
  zoneTypeFilter,
  onZoneTypeFilterChange,
  statusFilter,
  onStatusFilterChange,
  resultCount,
}: Omit<GeofencesFiltersProps, "asSheet" | "sheetOpen" | "onSheetOpenChange">) {
  const t = useTranslations("geofences");

  return (
    <div className="space-y-(--spacing-card)">
      <Input
        placeholder={t("search")}
        value={search}
        onChange={(e) => onSearchChange(e.target.value)}
        className="h-9"
        aria-label={t("search")}
      />

      <div className="space-y-2">
        <p className="text-xs font-medium text-foreground-muted uppercase tracking-wide">
          {t("filters.zoneType")}
        </p>
        <Select value={zoneTypeFilter} onValueChange={onZoneTypeFilterChange}>
          <SelectTrigger className="h-9 text-xs" aria-label={t("filters.zoneType")}>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">{t("filters.allTypes")}</SelectItem>
            <SelectItem value="depot">{t("filters.depot")}</SelectItem>
            <SelectItem value="terminal">{t("filters.terminal")}</SelectItem>
            <SelectItem value="restricted">{t("filters.restricted")}</SelectItem>
            <SelectItem value="customer">{t("filters.customer")}</SelectItem>
            <SelectItem value="custom">{t("filters.custom")}</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div className="space-y-2">
        <p className="text-xs font-medium text-foreground-muted uppercase tracking-wide">
          {t("filters.status")}
        </p>
        <Select value={statusFilter} onValueChange={onStatusFilterChange}>
          <SelectTrigger className="h-9 text-xs" aria-label={t("filters.status")}>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">{t("filters.allStatuses")}</SelectItem>
            <SelectItem value="active">{t("filters.activeOnly")}</SelectItem>
            <SelectItem value="inactive">{t("filters.inactiveOnly")}</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <p className="text-xs text-foreground-subtle">
        {resultCount} {resultCount === 1 ? "result" : "results"}
      </p>
    </div>
  );
}

export function GeofencesFilters(props: GeofencesFiltersProps) {
  const { asSheet, sheetOpen, onSheetOpenChange, ...filterProps } = props;
  const t = useTranslations("geofences");

  if (asSheet) {
    return (
      <Sheet open={sheetOpen} onOpenChange={onSheetOpenChange}>
        <SheetContent side="left" className="w-[280px] p-4">
          <SheetHeader>
            <SheetTitle>{t("mobile.showFilters")}</SheetTitle>
          </SheetHeader>
          <div className="mt-4">
            <FilterContent {...filterProps} />
          </div>
        </SheetContent>
      </Sheet>
    );
  }

  return (
    <aside className="hidden md:block w-52 shrink-0 border-r border-border p-(--spacing-card)">
      <FilterContent {...filterProps} />
    </aside>
  );
}
