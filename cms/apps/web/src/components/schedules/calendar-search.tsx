"use client";

import { useTranslations } from "next-intl";
import { Search } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface CalendarSearchProps {
  searchQuery: string;
  onSearchChange: (query: string) => void;
  activeTodayFilter: boolean;
  onActiveTodayChange: (active: boolean) => void;
}

export function CalendarSearch({
  searchQuery,
  onSearchChange,
  activeTodayFilter,
  onActiveTodayChange,
}: CalendarSearchProps) {
  const t = useTranslations("schedules.calendars");

  return (
    <div className="flex items-center gap-(--spacing-inline)">
      <div className="relative w-56">
        <Search className="absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-foreground-muted" aria-hidden="true" />
        <Input
          placeholder={t("search")}
          value={searchQuery}
          onChange={(e) => onSearchChange(e.target.value)}
          className="pl-9 h-9"
        />
      </div>
      <Button
        variant="outline"
        size="sm"
        className={cn(
          "cursor-pointer text-xs",
          activeTodayFilter && "bg-interactive text-interactive-foreground hover:bg-interactive/90"
        )}
        onClick={() => onActiveTodayChange(!activeTodayFilter)}
      >
        {t("activeToday")}
      </Button>
    </div>
  );
}
