"use client";

import { useTranslations } from "next-intl";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import type { CalendarViewMode } from "@/types/dashboard";

interface CalendarHeaderProps {
  currentDate: Date;
  view: CalendarViewMode;
  onViewChange: (view: CalendarViewMode) => void;
  onDateChange: (date: Date) => void;
}

const MONTH_KEYS = [
  "jan", "feb", "mar", "apr", "may", "jun",
  "jul", "aug", "sep", "oct", "nov", "dec",
] as const;

function getDateLabel(
  date: Date,
  view: CalendarViewMode,
  t: (key: string) => string
): string {
  const month = t(`months.${MONTH_KEYS[date.getMonth()]}`);
  const year = date.getFullYear();

  switch (view) {
    case "week": {
      const monday = new Date(date);
      const day = monday.getDay();
      monday.setDate(monday.getDate() - ((day + 6) % 7));
      const sunday = new Date(monday);
      sunday.setDate(monday.getDate() + 6);
      const mMonth = t(`months.${MONTH_KEYS[monday.getMonth()]}`);
      const sMonth = t(`months.${MONTH_KEYS[sunday.getMonth()]}`);
      if (monday.getMonth() === sunday.getMonth()) {
        return `${monday.getDate()} – ${sunday.getDate()} ${mMonth} ${year}`;
      }
      return `${monday.getDate()} ${mMonth} – ${sunday.getDate()} ${sMonth} ${year}`;
    }
    case "month":
      return `${month} ${year}`;
    case "3month": {
      const prev = new Date(date.getFullYear(), date.getMonth() - 1, 1);
      const next = new Date(date.getFullYear(), date.getMonth() + 1, 1);
      const pMonth = t(`months.${MONTH_KEYS[prev.getMonth()]}`);
      const nMonth = t(`months.${MONTH_KEYS[next.getMonth()]}`);
      return `${pMonth} – ${nMonth} ${year}`;
    }
    case "year":
      return `${year}`;
  }
}

export function CalendarHeader({
  currentDate,
  view,
  onViewChange,
  onDateChange,
}: CalendarHeaderProps) {
  const t = useTranslations("dashboard");

  function navigate(direction: -1 | 1) {
    const d = new Date(currentDate);
    switch (view) {
      case "week":
        d.setDate(d.getDate() + direction * 7);
        break;
      case "month":
        d.setMonth(d.getMonth() + direction);
        break;
      case "3month":
        d.setMonth(d.getMonth() + direction * 3);
        break;
      case "year":
        d.setFullYear(d.getFullYear() + direction);
        break;
    }
    onDateChange(d);
  }

  return (
    <div className="flex flex-wrap items-center justify-between gap-(--spacing-grid) p-(--spacing-card)">
      <h2 className="font-heading text-heading font-semibold text-foreground">
        {t("calendar.title")}
      </h2>

      <div className="flex items-center gap-(--spacing-inline)">
        <Button
          variant="ghost"
          size="icon-sm"
          onClick={() => navigate(-1)}
          aria-label="Previous"
        >
          <ChevronLeft className="size-4" />
        </Button>

        <Button
          variant="outline"
          size="sm"
          onClick={() => onDateChange(new Date())}
        >
          {t("calendar.today")}
        </Button>

        <span className="min-w-[10rem] text-center text-sm font-medium text-foreground">
          {getDateLabel(currentDate, view, t)}
        </span>

        <Button
          variant="ghost"
          size="icon-sm"
          onClick={() => navigate(1)}
          aria-label="Next"
        >
          <ChevronRight className="size-4" />
        </Button>
      </div>

      <ToggleGroup
        type="single"
        variant="outline"
        size="sm"
        value={view}
        onValueChange={(v) => {
          if (v) onViewChange(v as CalendarViewMode);
        }}
      >
        <ToggleGroupItem value="year" aria-label={t("calendar.year")}>
          {t("calendar.year")}
        </ToggleGroupItem>
        <ToggleGroupItem value="3month" aria-label={t("calendar.threeMonth")}>
          {t("calendar.threeMonth")}
        </ToggleGroupItem>
        <ToggleGroupItem value="month" aria-label={t("calendar.month")}>
          {t("calendar.month")}
        </ToggleGroupItem>
        <ToggleGroupItem value="week" aria-label={t("calendar.week")}>
          {t("calendar.week")}
        </ToggleGroupItem>
      </ToggleGroup>
    </div>
  );
}
