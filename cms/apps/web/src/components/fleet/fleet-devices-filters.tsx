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

interface FleetDevicesFiltersProps {
  search: string;
  onSearchChange: (value: string) => void;
  statusFilter: string;
  onStatusFilterChange: (value: string) => void;
  protocolFilter: string;
  onProtocolFilterChange: (value: string) => void;
  linkFilter: string;
  onLinkFilterChange: (value: string) => void;
  resultCount: number;
  asSheet?: boolean;
  sheetOpen?: boolean;
  onSheetOpenChange?: (open: boolean) => void;
}

function FilterContent({
  search,
  onSearchChange,
  statusFilter,
  onStatusFilterChange,
  protocolFilter,
  onProtocolFilterChange,
  linkFilter,
  onLinkFilterChange,
  resultCount,
}: Omit<FleetDevicesFiltersProps, "asSheet" | "sheetOpen" | "onSheetOpenChange">) {
  const t = useTranslations("fleet");

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
          {t("filters.status")}
        </p>
        <Select value={statusFilter} onValueChange={onStatusFilterChange}>
          <SelectTrigger className="h-9 text-xs" aria-label={t("filters.status")}>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">{t("filters.allStatuses")}</SelectItem>
            <SelectItem value="active">{t("filters.active")}</SelectItem>
            <SelectItem value="inactive">{t("filters.inactive")}</SelectItem>
            <SelectItem value="offline">{t("filters.offline")}</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div className="space-y-2">
        <p className="text-xs font-medium text-foreground-muted uppercase tracking-wide">
          {t("filters.protocol")}
        </p>
        <Select value={protocolFilter} onValueChange={onProtocolFilterChange}>
          <SelectTrigger className="h-9 text-xs" aria-label={t("filters.protocol")}>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">{t("filters.allProtocols")}</SelectItem>
            <SelectItem value="teltonika">{t("filters.teltonika")}</SelectItem>
            <SelectItem value="queclink">{t("filters.queclink")}</SelectItem>
            <SelectItem value="general">{t("filters.general")}</SelectItem>
            <SelectItem value="osmand">{t("filters.osmand")}</SelectItem>
            <SelectItem value="other">{t("filters.other")}</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div className="space-y-2">
        <p className="text-xs font-medium text-foreground-muted uppercase tracking-wide">
          {t("filters.vehicleLink")}
        </p>
        <Select value={linkFilter} onValueChange={onLinkFilterChange}>
          <SelectTrigger className="h-9 text-xs" aria-label={t("filters.vehicleLink")}>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">{t("filters.allLinks")}</SelectItem>
            <SelectItem value="linked">{t("filters.linkedOnly")}</SelectItem>
            <SelectItem value="unlinked">{t("filters.unlinkedOnly")}</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <p className="text-xs text-foreground-subtle">
        {resultCount} {resultCount === 1 ? "result" : "results"}
      </p>
    </div>
  );
}

export function FleetDevicesFilters(props: FleetDevicesFiltersProps) {
  const { asSheet, sheetOpen, onSheetOpenChange, ...filterProps } = props;
  const t = useTranslations("fleet");

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
