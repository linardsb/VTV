"use client";

import { useMemo } from "react";
import { useTranslations } from "next-intl";
import { cn } from "@/lib/utils";
import type { CalendarEvent } from "@/types/dashboard";

interface YearViewProps {
  currentDate: Date;
  events: CalendarEvent[];
}

const MONTH_KEYS = [
  "jan", "feb", "mar", "apr", "may", "jun",
  "jul", "aug", "sep", "oct", "nov", "dec",
] as const;

function isSameDay(a: Date, b: Date): boolean {
  return (
    a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate()
  );
}

function getMiniDays(year: number, month: number): (Date | null)[] {
  const firstDay = new Date(year, month, 1);
  const lastDay = new Date(year, month + 1, 0);
  const startOffset = (firstDay.getDay() + 6) % 7;
  const cells: (Date | null)[] = [];
  for (let i = 0; i < startOffset; i++) cells.push(null);
  for (let day = 1; day <= lastDay.getDate(); day++) {
    cells.push(new Date(year, month, day));
  }
  while (cells.length % 7 !== 0) cells.push(null);
  return cells;
}

function countEventsOnDay(events: CalendarEvent[], date: Date): number {
  return events.filter((e) => isSameDay(e.start, date)).length;
}

export function YearView({ currentDate, events }: YearViewProps) {
  const t = useTranslations("dashboard");
  const year = currentDate.getFullYear();
  const today = new Date();

  const months = useMemo(
    () =>
      Array.from({ length: 12 }, (_, i) => ({
        month: i,
        days: getMiniDays(year, i),
      })),
    [year]
  );

  return (
    <div className="grid grid-cols-2 gap-(--spacing-grid) p-(--spacing-card) sm:grid-cols-3 lg:grid-cols-4">
      {months.map(({ month, days }) => (
        <div key={month}>
          <p className="mb-(--spacing-tight) text-xs font-medium text-foreground-muted">
            {t(`months.${MONTH_KEYS[month]}`)}
          </p>
          <div className="grid grid-cols-7 gap-px">
            {days.map((date, i) => {
              if (!date) {
                return <div key={`e-${i}`} className="size-4" />;
              }
              const isToday = isSameDay(date, today);
              const count = countEventsOnDay(events, date);

              return (
                <div
                  key={date.getDate()}
                  className={cn(
                    "size-4 rounded-[2px]",
                    count === 0 && "bg-border-subtle",
                    count === 1 && "bg-interactive/30",
                    count === 2 && "bg-interactive/60",
                    count >= 3 && "bg-interactive",
                    isToday && "ring-1 ring-status-critical"
                  )}
                  title={`${date.toLocaleDateString()}: ${t("calendar.eventsCount", { count })}`}
                />
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}
