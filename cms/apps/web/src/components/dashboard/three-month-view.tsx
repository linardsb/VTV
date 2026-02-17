"use client";

import { useMemo } from "react";
import { useTranslations } from "next-intl";
import { cn } from "@/lib/utils";
import type { CalendarEvent } from "@/types/dashboard";

interface ThreeMonthViewProps {
  currentDate: Date;
  events: CalendarEvent[];
}

const WEEKDAY_KEYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"] as const;
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

function getMiniMonthDays(year: number, month: number): (Date | null)[] {
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

function hasEventsOnDay(events: CalendarEvent[], date: Date): boolean {
  return events.some((e) => isSameDay(e.start, date));
}

function MiniMonth({
  year,
  month,
  events,
  today,
}: {
  year: number;
  month: number;
  events: CalendarEvent[];
  today: Date;
}) {
  const t = useTranslations("dashboard");
  const cells = useMemo(() => getMiniMonthDays(year, month), [year, month]);

  return (
    <div>
      <h3 className="mb-(--spacing-inline) text-center font-heading text-sm font-semibold text-foreground">
        {t(`months.${MONTH_KEYS[month]}`)} {year}
      </h3>
      <div className="grid grid-cols-7 gap-0.5">
        {WEEKDAY_KEYS.map((key) => (
          <div
            key={key}
            className="flex h-6 items-center justify-center text-[10px] font-medium text-foreground-muted"
          >
            {t(`weekdays.${key}`)}
          </div>
        ))}
        {cells.map((date, i) => {
          if (!date) {
            return <div key={`empty-${i}`} className="h-8 w-8" />;
          }
          const isToday = isSameDay(date, today);
          const hasEvents = hasEventsOnDay(events, date);

          return (
            <div
              key={date.getDate()}
              className={cn(
                "flex h-8 w-8 flex-col items-center justify-center rounded-sm text-xs",
                isToday && "rounded-full bg-interactive font-semibold text-white"
              )}
            >
              <span>{date.getDate()}</span>
              {hasEvents && !isToday && (
                <div className="mt-0.5 size-1 rounded-full bg-interactive" />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function ThreeMonthView({ currentDate, events }: ThreeMonthViewProps) {
  const months = useMemo(() => {
    const result: { year: number; month: number }[] = [];
    for (let offset = -1; offset <= 1; offset++) {
      const d = new Date(
        currentDate.getFullYear(),
        currentDate.getMonth() + offset,
        1
      );
      result.push({ year: d.getFullYear(), month: d.getMonth() });
    }
    return result;
  }, [currentDate]);

  const today = new Date();

  return (
    <div className="grid grid-cols-1 gap-(--spacing-section) p-(--spacing-card) sm:grid-cols-3">
      {months.map(({ year, month }) => (
        <MiniMonth
          key={`${year}-${month}`}
          year={year}
          month={month}
          events={events}
          today={today}
        />
      ))}
    </div>
  );
}
