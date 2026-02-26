"use client";

import { useMemo, useState } from "react";
import { useTranslations } from "next-intl";
import { cn } from "@/lib/utils";
import type { CalendarEvent } from "@/types/dashboard";
import { getGoalStatus } from "./goal-progress-badge";
import { getEventDotColor } from "./event-styles";

interface ThreeMonthViewProps {
  currentDate: Date;
  events: CalendarEvent[];
  onDayDrop?: (date: Date, driverJson: string) => void;
  onEventClick?: (event: CalendarEvent) => void;
}

const WEEKDAY_KEYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"] as const;
const MONTH_KEYS = [
  "jan", "feb", "mar", "apr", "may", "jun",
  "jul", "aug", "sep", "oct", "nov", "dec",
] as const;

const goalStatusDotColors: Record<string, string> = {
  "not-started": "bg-foreground/30",
  "in-progress": "bg-status-delayed",
  completed: "bg-status-ontime",
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
  onDayDrop,
  onEventClick,
}: {
  year: number;
  month: number;
  events: CalendarEvent[];
  today: Date;
  onDayDrop?: (date: Date, driverJson: string) => void;
  onEventClick?: (event: CalendarEvent) => void;
}) {
  const t = useTranslations("dashboard");
  const [dragOverDate, setDragOverDate] = useState<string | null>(null);
  const weeks = useMemo(() => getMonthGrid(year, month), [year, month]);

  const eventsByDate = useMemo(() => {
    const map = new Map<string, CalendarEvent[]>();
    for (const event of events) {
      const cursor = new Date(event.start);
      cursor.setHours(0, 0, 0, 0);
      const endDay = new Date(event.end);
      // If event ends exactly at midnight, it doesn't extend into that day
      if (endDay.getHours() === 0 && endDay.getMinutes() === 0) {
        endDay.setDate(endDay.getDate() - 1);
      }
      endDay.setHours(0, 0, 0, 0);

      while (cursor <= endDay) {
        // Only include days that fall within this mini-month
        if (cursor.getFullYear() === year && cursor.getMonth() === month) {
          const key = `${cursor.getFullYear()}-${cursor.getMonth()}-${cursor.getDate()}`;
          if (!map.has(key)) map.set(key, []);
          map.get(key)!.push(event);
        }
        cursor.setDate(cursor.getDate() + 1);
      }
    }
    return map;
  }, [events, year, month]);

  return (
    <div>
      <h3 className="mb-(--spacing-tight) text-center font-heading text-sm font-semibold text-foreground">
        {t(`months.${MONTH_KEYS[month]}`)} {year}
      </h3>

      {/* Weekday headers */}
      <div className="grid grid-cols-7 gap-px">
        {WEEKDAY_KEYS.map((key) => (
          <div
            key={key}
            className="py-0.5 text-center text-[9px] font-medium text-foreground-muted"
          >
            {t(`weekdays.${key}`)}
          </div>
        ))}
      </div>

      {/* Day grid */}
      <div className="flex flex-col gap-px">
        {weeks.map((week, weekIdx) => (
          <div
            key={weekIdx}
            className="grid grid-cols-7 gap-px"
          >
            {week.map((day, dayIdx) => {
              if (!day) {
                return (
                  <div
                    key={`empty-${dayIdx}`}
                    className="aspect-square overflow-hidden rounded-sm border border-border-subtle opacity-40"
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
                    "aspect-square overflow-hidden rounded-sm border border-border-subtle p-px transition-colors duration-200",
                    isToday && "border-interactive bg-interactive/10",
                    dragOverDate === dateKey && "ring-2 ring-interactive bg-interactive/10"
                  )}
                  aria-dropeffect={onDayDrop ? "copy" : undefined}
                  onDragOver={onDayDrop ? (e) => {
                    e.preventDefault();
                    e.dataTransfer.dropEffect = "copy";
                    setDragOverDate(dateKey);
                  } : undefined}
                  onDragLeave={onDayDrop ? () => setDragOverDate(null) : undefined}
                  onDrop={onDayDrop ? (e) => {
                    e.preventDefault();
                    setDragOverDate(null);
                    const driverJson = e.dataTransfer.getData("application/vtv-driver");
                    if (driverJson) {
                      onDayDrop(day, driverJson);
                    }
                  } : undefined}
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
                      {visibleEvents.map((event) => {
                        const hasGoals = event.goals && event.goals.items.length > 0;
                        const goalStatus = hasGoals ? getGoalStatus(event.goals!) : null;
                        const dotClass = hasGoals
                          ? goalStatusDotColors[goalStatus!]
                          : getEventDotColor(event.title, event.category);

                        return (
                          <button
                            key={event.id}
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              onEventClick?.(event);
                            }}
                            className="flex items-center gap-0.5 cursor-pointer"
                          >
                            <div
                              className={cn("size-1 shrink-0 rounded-full", dotClass)}
                            />
                            <span className="truncate text-[8px] leading-tight text-foreground-muted">
                              {event.title}
                            </span>
                          </button>
                        );
                      })}
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

export function ThreeMonthView({ currentDate, events, onDayDrop, onEventClick }: ThreeMonthViewProps) {
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
    <div className="grid h-full grid-cols-1 place-content-center gap-(--spacing-section) overflow-auto p-(--spacing-card) sm:grid-cols-3">
      {months.map(({ year, month }) => (
        <MiniMonth
          key={`${year}-${month}`}
          year={year}
          month={month}
          events={events}
          today={today}
          onDayDrop={onDayDrop}
          onEventClick={onEventClick}
        />
      ))}
    </div>
  );
}
