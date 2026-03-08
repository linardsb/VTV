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
  typeFilter: string;
  onTypeFilterChange: (value: string) => void;
  domainFilter: string;
  onDomainFilterChange: (value: string) => void;
  statusFilter: string;
  onStatusFilterChange: (value: string) => void;
  languageFilter: string;
  onLanguageFilterChange: (value: string) => void;
  domains: string[];
  resultCount: number;
}

function FilterContent({
  search,
  onSearchChange,
  typeFilter,
  onTypeFilterChange,
  domainFilter,
  onDomainFilterChange,
  statusFilter,
  onStatusFilterChange,
  languageFilter,
  onLanguageFilterChange,
  domains,
  resultCount,
}: FilterContentProps) {
  const t = useTranslations("documents");

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
          <ToggleGroup
            type="single"
            spacing={1}
            value={typeFilter || "all"}
            onValueChange={(value) => {
              onTypeFilterChange(value === "all" || value === "" ? "" : value);
            }}
            className="flex flex-col gap-1"
          >
            <ToggleGroupItem value="all" className="w-full justify-start rounded-md text-sm data-[state=on]:bg-filter-active-bg data-[state=on]:text-filter-active-text data-[state=on]:font-semibold">
              {t("filters.allTypes")}
            </ToggleGroupItem>
            <ToggleGroupItem value="pdf" className="w-full justify-start rounded-md text-sm data-[state=on]:bg-filter-active-bg data-[state=on]:text-filter-active-text data-[state=on]:font-semibold">
              {t("filters.pdf")}
            </ToggleGroupItem>
            <ToggleGroupItem value="docx" className="w-full justify-start rounded-md text-sm data-[state=on]:bg-filter-active-bg data-[state=on]:text-filter-active-text data-[state=on]:font-semibold">
              {t("filters.docx")}
            </ToggleGroupItem>
            <ToggleGroupItem value="xlsx" className="w-full justify-start rounded-md text-sm data-[state=on]:bg-filter-active-bg data-[state=on]:text-filter-active-text data-[state=on]:font-semibold">
              {t("filters.xlsx")}
            </ToggleGroupItem>
            <ToggleGroupItem value="image" className="w-full justify-start rounded-md text-sm data-[state=on]:bg-filter-active-bg data-[state=on]:text-filter-active-text data-[state=on]:font-semibold">
              {t("filters.image")}
            </ToggleGroupItem>
            <ToggleGroupItem value="text" className="w-full justify-start rounded-md text-sm data-[state=on]:bg-filter-active-bg data-[state=on]:text-filter-active-text data-[state=on]:font-semibold">
              {t("filters.text")}
            </ToggleGroupItem>
          </ToggleGroup>
        </div>

        <Separator />

        {/* Domain Filter */}
        <div className="space-y-(--spacing-tight)">
          <p className="text-xs font-medium text-label-text uppercase tracking-wide">
            {t("filters.domain")}
          </p>
          <Select value={domainFilter || "all"} onValueChange={(v) => onDomainFilterChange(v === "all" ? "" : v)}>
            <SelectTrigger aria-label={t("filters.domain")}>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">{t("filters.allDomains")}</SelectItem>
              {domains.map((domain) => (
                <SelectItem key={domain} value={domain}>
                  {domain}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <Separator />

        {/* Status Filter */}
        <div className="space-y-(--spacing-tight)">
          <p className="text-xs font-medium text-label-text uppercase tracking-wide">
            {t("filters.status")}
          </p>
          <ToggleGroup
            type="single"
            spacing={1}
            value={statusFilter || "all"}
            onValueChange={(value) => {
              onStatusFilterChange(value === "all" || value === "" ? "" : value);
            }}
            className="flex flex-col gap-1"
          >
            <ToggleGroupItem value="all" className="w-full justify-start rounded-md text-sm data-[state=on]:bg-filter-active-bg data-[state=on]:text-filter-active-text data-[state=on]:font-semibold">
              {t("filters.allStatuses")}
            </ToggleGroupItem>
            <ToggleGroupItem value="completed" className="w-full justify-start rounded-md text-sm data-[state=on]:bg-filter-active-bg data-[state=on]:text-filter-active-text data-[state=on]:font-semibold">
              {t("filters.completed")}
            </ToggleGroupItem>
            <ToggleGroupItem value="processing" className="w-full justify-start rounded-md text-sm data-[state=on]:bg-filter-active-bg data-[state=on]:text-filter-active-text data-[state=on]:font-semibold">
              {t("filters.processing")}
            </ToggleGroupItem>
            <ToggleGroupItem value="failed" className="w-full justify-start rounded-md text-sm data-[state=on]:bg-filter-active-bg data-[state=on]:text-filter-active-text data-[state=on]:font-semibold">
              {t("filters.failed")}
            </ToggleGroupItem>
          </ToggleGroup>
        </div>

        <Separator />

        {/* Language Filter */}
        <div className="space-y-(--spacing-tight)">
          <p className="text-xs font-medium text-label-text uppercase tracking-wide">
            {t("filters.language")}
          </p>
          <ToggleGroup
            type="single"
            spacing={1}
            value={languageFilter || "all"}
            onValueChange={(value) => {
              onLanguageFilterChange(value === "all" || value === "" ? "" : value);
            }}
            className="flex flex-col gap-1"
          >
            <ToggleGroupItem value="all" className="w-full justify-start rounded-md text-sm data-[state=on]:bg-filter-active-bg data-[state=on]:text-filter-active-text data-[state=on]:font-semibold">
              {t("filters.allLanguages")}
            </ToggleGroupItem>
            <ToggleGroupItem value="lv" className="w-full justify-start rounded-md text-sm data-[state=on]:bg-filter-active-bg data-[state=on]:text-filter-active-text data-[state=on]:font-semibold">
              {t("filters.lv")}
            </ToggleGroupItem>
            <ToggleGroupItem value="en" className="w-full justify-start rounded-md text-sm data-[state=on]:bg-filter-active-bg data-[state=on]:text-filter-active-text data-[state=on]:font-semibold">
              {t("filters.en")}
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

interface DocumentFiltersProps {
  search: string;
  onSearchChange: (value: string) => void;
  typeFilter: string;
  onTypeFilterChange: (value: string) => void;
  domainFilter: string;
  onDomainFilterChange: (value: string) => void;
  statusFilter: string;
  onStatusFilterChange: (value: string) => void;
  languageFilter: string;
  onLanguageFilterChange: (value: string) => void;
  domains: string[];
  resultCount: number;
  asSheet?: boolean;
  sheetOpen?: boolean;
  onSheetOpenChange?: (open: boolean) => void;
}

export function DocumentFilters({
  search,
  onSearchChange,
  typeFilter,
  onTypeFilterChange,
  domainFilter,
  onDomainFilterChange,
  statusFilter,
  onStatusFilterChange,
  languageFilter,
  onLanguageFilterChange,
  domains,
  resultCount,
  asSheet,
  sheetOpen,
  onSheetOpenChange,
}: DocumentFiltersProps) {
  const t = useTranslations("documents");

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
            domainFilter={domainFilter}
            onDomainFilterChange={onDomainFilterChange}
            statusFilter={statusFilter}
            onStatusFilterChange={onStatusFilterChange}
            languageFilter={languageFilter}
            onLanguageFilterChange={onLanguageFilterChange}
            domains={domains}
            resultCount={resultCount}
          />
        </SheetContent>
      </Sheet>
    );
  }

  return (
    <aside className="flex w-52 shrink-0 flex-col border-r border-border bg-surface p-(--spacing-card) overflow-y-auto">
      <FilterContent
        search={search}
        onSearchChange={onSearchChange}
        typeFilter={typeFilter}
        onTypeFilterChange={onTypeFilterChange}
        domainFilter={domainFilter}
        onDomainFilterChange={onDomainFilterChange}
        statusFilter={statusFilter}
        onStatusFilterChange={onStatusFilterChange}
        languageFilter={languageFilter}
        onLanguageFilterChange={onLanguageFilterChange}
        domains={domains}
        resultCount={resultCount}
      />
    </aside>
  );
}
