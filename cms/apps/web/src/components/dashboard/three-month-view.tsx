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

const categoryDotColors: Record<string, string> = {
  maintenance: "bg-blue-400",
  "route-change": "bg-amber-400",
  "driver-shift": "bg-emerald-500",
  "service-alert": "bg-red-500",
};

function isSameDay(a: Date, b: Date): boolean {
  return (
    a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate()
  );
}

function getMonthGrid(year: number, month: number): (Date | null)[][] {
  const firstDay = new Date(year, month, 1);
  const lastDay = new Date(year, month + 1, 0);
  const startOffset = (firstDay.getDay() + 6) % 7;

  const weeks: (Date | null)[][] = [];
  let currentWeek: (Date | null)[] = [];

  for (let i = 0; i < startOffset; i++) {
    currentWeek.push(null);
  }

  for (let day = 1; day <= lastDay.getDate(); day++) {
    currentWeek.push(new Date(year, month, day));
    if (currentWeek.length === 7) {
      weeks.push(currentWeek);
      currentWeek = [];
    }
  }

  if (currentWeek.length > 0) {
    while (currentWeek.length < 7) {
      currentWeek.push(null);
    }
    weeks.push(currentWeek);
  }

  return weeks;
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
  const weeks = useMemo(() => getMonthGrid(year, month), [year, month]);

  const eventsByDate = useMemo(() => {
    const map = new Map<string, CalendarEvent[]>();
    for (const event of events) {
      const eventDate = event.start;
      if (
        eventDate.getFullYear() === year &&
        eventDate.getMonth() === month
      ) {
        const key = `${eventDate.getFullYear()}-${eventDate.getMonth()}-${eventDate.getDate()}`;
        if (!map.has(key)) map.set(key, []);
        map.get(key)!.push(event);
      }
    }
    return map;
  }, [events, year, month]);

  return (
    <div className="flex h-full flex-col">
      <h3 className="mb-(--spacing-tight) shrink-0 text-center font-heading text-sm font-semibold text-foreground">
        {t(`months.${MONTH_KEYS[month]}`)} {year}
      </h3>

      {/* Weekday headers */}
      <div className="grid shrink-0 grid-cols-7 gap-px">
        {WEEKDAY_KEYS.map((key) => (
          <div
            key={key}
            className="py-0.5 text-center text-[9px] font-medium text-foreground-muted"
          >
            {t(`weekdays.${key}`)}
          </div>
        ))}
      </div>

      {/* Day grid — each week row stretches equally */}
      <div className="flex min-h-0 flex-1 flex-col gap-px">
        {weeks.map((week, weekIdx) => (
          <div
            key={weekIdx}
            className="grid min-h-0 flex-1 grid-cols-7 gap-px"
          >
            {week.map((day, dayIdx) => {
              if (!day) {
                return (
                  <div
                    key={`empty-${dayIdx}`}
                    className="overflow-hidden rounded-sm border border-border-subtle opacity-40"
                  />
                );
              }

              const isToday = isSameDay(day, today);
              const dateKey = `${day.getFullYear()}-${day.getMonth()}-${day.getDate()}`;
              const dayEvents = eventsByDate.get(dateKey) ?? [];
              const visibleEvents = dayEvents.slice(0, 2);
              const overflow = dayEvents.length - 2;

              return (
                <div
                  key={day.getDate()}
                  className={cn(
                    "overflow-hidden rounded-sm border border-border-subtle p-px transition-colors duration-200",
                    isToday && "border-interactive bg-interactive/10"
                  )}
                >
                  <p
                    className={cn(
                      "text-[10px] leading-none text-foreground",
                      isToday && "font-semibold text-interactive"
                    )}
                  >
                    {day.getDate()}
                  </p>
                  {visibleEvents.length > 0 && (
                    <div className="mt-px flex flex-col gap-0">
                      {visibleEvents.map((event) => (
                        <div
                          key={event.id}
                          className="flex items-center gap-0.5"
                        >
                          <div
                            className={cn(
                              "size-1 shrink-0 rounded-full",
                              categoryDotColors[event.category]
                            )}
                          />
                          <span className="truncate text-[8px] leading-tight text-foreground-muted">
                            {t(event.title)}
                          </span>
                        </div>
                      ))}
                      {overflow > 0 && (
                        <span className="text-[8px] leading-tight text-foreground-muted">
                          +{overflow}
                        </span>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        ))}
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
    <div className="grid h-full grid-cols-1 gap-(--spacing-section) p-(--spacing-card) sm:grid-cols-3">
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
