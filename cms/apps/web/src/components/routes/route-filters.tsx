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
import type { RouteType } from "@/types/route";

interface RouteFiltersProps {
  search: string;
  onSearchChange: (value: string) => void;
  typeFilter: RouteType | null;
  onTypeFilterChange: (type: RouteType | null) => void;
  statusFilter: "all" | "active" | "inactive";
  onStatusFilterChange: (status: "all" | "active" | "inactive") => void;
  resultCount: number;
}

export function RouteFilters({
  search,
  onSearchChange,
  typeFilter,
  onTypeFilterChange,
  statusFilter,
  onStatusFilterChange,
  resultCount,
}: RouteFiltersProps) {
  const t = useTranslations("routes");

  return (
    <aside className="flex w-60 shrink-0 flex-col border-r border-border bg-surface p-(--spacing-card)">
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
          <p className="text-xs font-medium text-foreground-muted uppercase tracking-wide">
            {t("table.type")}
          </p>
          <ToggleGroup
            type="single"
            value={typeFilter === null ? "all" : String(typeFilter)}
            onValueChange={(value) => {
              if (value === "all" || value === "") {
                onTypeFilterChange(null);
              } else {
                onTypeFilterChange(Number(value) as RouteType);
              }
            }}
            className="flex flex-col gap-1"
          >
            <ToggleGroupItem value="all" className="w-full justify-start text-sm">
              {t("filters.allTypes")}
            </ToggleGroupItem>
            <ToggleGroupItem value="3" className="w-full justify-start text-sm">
              {t("filters.bus")}
            </ToggleGroupItem>
            <ToggleGroupItem value="11" className="w-full justify-start text-sm">
              {t("filters.trolleybus")}
            </ToggleGroupItem>
            <ToggleGroupItem value="0" className="w-full justify-start text-sm">
              {t("filters.tram")}
            </ToggleGroupItem>
          </ToggleGroup>
        </div>

        <Separator />

        {/* Status Filter */}
        <div className="space-y-(--spacing-tight)">
          <p className="text-xs font-medium text-foreground-muted uppercase tracking-wide">
            {t("table.status")}
          </p>
          <Select value={statusFilter} onValueChange={(v) => onStatusFilterChange(v as "all" | "active" | "inactive")}>
            <SelectTrigger aria-label={t("table.status")}>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">{t("filters.allStatuses")}</SelectItem>
              <SelectItem value="active">{t("filters.active")}</SelectItem>
              <SelectItem value="inactive">{t("filters.inactive")}</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* Result count */}
      <div className="mt-auto pt-(--spacing-card)">
        <p className="text-xs text-foreground-muted">
          {resultCount} {t("table.name").toLowerCase()}
        </p>
      </div>
    </aside>
  );
}
