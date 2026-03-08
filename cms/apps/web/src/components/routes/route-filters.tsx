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
import type { Agency } from "@/types/schedule";
import type { GTFSFeed } from "@/types/gtfs";

interface FilterContentProps {
  search: string;
  onSearchChange: (value: string) => void;
  typeFilter: number | null;
  onTypeFilterChange: (type: number | null) => void;
  statusFilter: "all" | "active" | "inactive";
  onStatusFilterChange: (status: "all" | "active" | "inactive") => void;
  agencyFilter: number | null;
  onAgencyFilterChange: (agencyId: number | null) => void;
  agencies: Agency[];
  resultCount: number;
  feeds: GTFSFeed[];
  feedFilter: string | null;
  onFeedFilterChange: (feedId: string | null) => void;
}

function FilterContent({
  search,
  onSearchChange,
  typeFilter,
  onTypeFilterChange,
  statusFilter,
  onStatusFilterChange,
  agencyFilter,
  onAgencyFilterChange,
  agencies,
  resultCount,
  feeds,
  feedFilter,
  onFeedFilterChange,
}: FilterContentProps) {
  const t = useTranslations("routes");

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

        {/* Feed Filter */}
        {feeds.length > 0 && (
          <>
            <div className="space-y-(--spacing-tight)">
              <p className="text-xs font-medium text-label-text uppercase tracking-wide">
                {t("filters.feed")}
              </p>
              <ToggleGroup
                type="single"
                spacing={1}
                value={feedFilter ?? "all"}
                onValueChange={(value) => {
                  onFeedFilterChange(value === "all" || value === "" ? null : value);
                }}
                className="flex flex-col gap-1"
              >
                <ToggleGroupItem value="all" className="w-full justify-start rounded-md text-sm data-[state=on]:bg-filter-active-bg data-[state=on]:text-filter-active-text data-[state=on]:font-semibold">
                  {t("filters.allFeeds")}
                </ToggleGroupItem>
                {feeds.filter(f => f.enabled).map((feed) => (
                  <ToggleGroupItem
                    key={feed.feed_id}
                    value={feed.feed_id}
                    className="w-full justify-start rounded-md text-sm data-[state=on]:bg-filter-active-bg data-[state=on]:text-filter-active-text data-[state=on]:font-semibold"
                  >
                    {feed.operator_name}
                  </ToggleGroupItem>
                ))}
              </ToggleGroup>
            </div>
            <Separator />
          </>
        )}

        {/* Type Filter */}
        <div className="space-y-(--spacing-tight)">
          <p className="text-xs font-medium text-label-text uppercase tracking-wide">
            {t("table.type")}
          </p>
          <ToggleGroup
            type="single"
            spacing={1}
            value={typeFilter === null ? "all" : String(typeFilter)}
            onValueChange={(value) => {
              if (value === "all" || value === "") {
                onTypeFilterChange(null);
              } else {
                onTypeFilterChange(Number(value));
              }
            }}
            className="flex flex-col gap-1"
          >
            <ToggleGroupItem value="all" className="w-full justify-start rounded-md text-sm data-[state=on]:bg-filter-active-bg data-[state=on]:text-filter-active-text data-[state=on]:font-semibold">
              {t("filters.allTypes")}
            </ToggleGroupItem>
            <ToggleGroupItem value="3" className="w-full justify-start rounded-md text-sm data-[state=on]:bg-filter-active-bg data-[state=on]:text-filter-active-text data-[state=on]:font-semibold">
              {t("filters.bus")}
            </ToggleGroupItem>
            <ToggleGroupItem value="11" className="w-full justify-start rounded-md text-sm data-[state=on]:bg-filter-active-bg data-[state=on]:text-filter-active-text data-[state=on]:font-semibold">
              {t("filters.trolleybus")}
            </ToggleGroupItem>
            <ToggleGroupItem value="0" className="w-full justify-start rounded-md text-sm data-[state=on]:bg-filter-active-bg data-[state=on]:text-filter-active-text data-[state=on]:font-semibold">
              {t("filters.tram")}
            </ToggleGroupItem>
          </ToggleGroup>
        </div>

        <Separator />

        {/* Agency Filter */}
        {agencies.length > 0 && (
          <>
            <div className="space-y-(--spacing-tight)">
              <p className="text-xs font-medium text-label-text uppercase tracking-wide">
                {t("filters.agency")}
              </p>
              <Select
                value={agencyFilter === null ? "all" : String(agencyFilter)}
                onValueChange={(v) =>
                  onAgencyFilterChange(v === "all" ? null : Number(v))
                }
              >
                <SelectTrigger aria-label={t("filters.agency")}>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">{t("filters.allAgencies")}</SelectItem>
                  {agencies.map((a) => (
                    <SelectItem key={a.id} value={String(a.id)}>
                      {a.agency_name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <Separator />
          </>
        )}

        {/* Status Filter */}
        <div className="space-y-(--spacing-tight)">
          <p className="text-xs font-medium text-label-text uppercase tracking-wide">
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
    </>
  );
}

interface RouteFiltersProps {
  search: string;
  onSearchChange: (value: string) => void;
  typeFilter: number | null;
  onTypeFilterChange: (type: number | null) => void;
  statusFilter: "all" | "active" | "inactive";
  onStatusFilterChange: (status: "all" | "active" | "inactive") => void;
  agencyFilter: number | null;
  onAgencyFilterChange: (agencyId: number | null) => void;
  agencies: Agency[];
  resultCount: number;
  feeds: GTFSFeed[];
  feedFilter: string | null;
  onFeedFilterChange: (feedId: string | null) => void;
  asSheet?: boolean;
  sheetOpen?: boolean;
  onSheetOpenChange?: (open: boolean) => void;
}

export function RouteFilters({
  search,
  onSearchChange,
  typeFilter,
  onTypeFilterChange,
  statusFilter,
  onStatusFilterChange,
  agencyFilter,
  onAgencyFilterChange,
  agencies,
  resultCount,
  feeds,
  feedFilter,
  onFeedFilterChange,
  asSheet,
  sheetOpen,
  onSheetOpenChange,
}: RouteFiltersProps) {
  const t = useTranslations("routes");

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
            typeFilter={typeFilter}
            onTypeFilterChange={onTypeFilterChange}
            statusFilter={statusFilter}
            onStatusFilterChange={onStatusFilterChange}
            agencyFilter={agencyFilter}
            onAgencyFilterChange={onAgencyFilterChange}
            agencies={agencies}
            resultCount={resultCount}
            feeds={feeds}
            feedFilter={feedFilter}
            onFeedFilterChange={onFeedFilterChange}
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
        agencyFilter={agencyFilter}
        onAgencyFilterChange={onAgencyFilterChange}
        agencies={agencies}
        resultCount={resultCount}
        feeds={feeds}
        feedFilter={feedFilter}
        onFeedFilterChange={onFeedFilterChange}
      />
    </aside>
  );
}
