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
  roleFilter: string;
  onRoleFilterChange: (value: string) => void;
  statusFilter: string;
  onStatusFilterChange: (value: string) => void;
  resultCount: number;
}

function FilterContent({
  search,
  onSearchChange,
  roleFilter,
  onRoleFilterChange,
  statusFilter,
  onStatusFilterChange,
  resultCount,
}: FilterContentProps) {
  const t = useTranslations("users");

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

        {/* Role Filter */}
        <div className="space-y-(--spacing-tight)">
          <p className="text-xs font-medium text-label-text uppercase tracking-wide">
            {t("filters.role")}
          </p>
          <Select value={roleFilter} onValueChange={onRoleFilterChange}>
            <SelectTrigger aria-label={t("filters.role")}>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">{t("filters.allRoles")}</SelectItem>
              <SelectItem value="admin">{t("filters.admin")}</SelectItem>
              <SelectItem value="dispatcher">
                {t("filters.dispatcher")}
              </SelectItem>
              <SelectItem value="editor">{t("filters.editor")}</SelectItem>
              <SelectItem value="viewer">{t("filters.viewer")}</SelectItem>
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
              <SelectItem value="active">{t("filters.active")}</SelectItem>
              <SelectItem value="inactive">
                {t("filters.inactive")}
              </SelectItem>
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

interface UserFiltersProps {
  search: string;
  onSearchChange: (value: string) => void;
  roleFilter: string;
  onRoleFilterChange: (value: string) => void;
  statusFilter: string;
  onStatusFilterChange: (value: string) => void;
  resultCount: number;
  asSheet?: boolean;
  sheetOpen?: boolean;
  onSheetOpenChange?: (open: boolean) => void;
}

export function UserFilters({
  search,
  onSearchChange,
  roleFilter,
  onRoleFilterChange,
  statusFilter,
  onStatusFilterChange,
  resultCount,
  asSheet,
  sheetOpen,
  onSheetOpenChange,
}: UserFiltersProps) {
  const t = useTranslations("users");

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
            roleFilter={roleFilter}
            onRoleFilterChange={onRoleFilterChange}
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
        roleFilter={roleFilter}
        onRoleFilterChange={onRoleFilterChange}
        statusFilter={statusFilter}
        onStatusFilterChange={onStatusFilterChange}
        resultCount={resultCount}
      />
    </aside>
  );
}
