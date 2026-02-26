"use client";

import { useMemo, useState } from "react";
import { useTranslations } from "next-intl";
import { cn } from "@/lib/utils";
import type { CalendarEvent } from "@/types/dashboard";
import { GoalProgressBadge } from "./goal-progress-badge";

interface MonthViewProps {
  currentDate: Date;
  events: CalendarEvent[];
  onDayDrop?: (date: Date, driverJson: string) => void;
  onEventClick?: (event: CalendarEvent) => void;
}

const WEEKDAY_KEYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"] as const;

const categoryDotColors: Record<string, string> = {
  maintenance: "bg-category-maintenance",
  "route-change": "bg-category-route-change",
  "driver-shift": "bg-category-driver-shift",
  "service-alert": "bg-category-service-alert",
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
  // Monday = 0 in our grid
  const startOffset = (firstDay.getDay() + 6) % 7;

  const weeks: (Date | null)[][] = [];
  let currentWeek: (Date | null)[] = [];

  // Fill leading nulls
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

  // Fill trailing nulls
  if (currentWeek.length > 0) {
    while (currentWeek.length < 7) {
      currentWeek.push(null);
    }
    weeks.push(currentWeek);
  }

  return weeks;
}

export function MonthView({ currentDate, events, onDayDrop, onEventClick }: MonthViewProps) {
  const t = useTranslations("dashboard");
  const today = new Date();
  const year = currentDate.getFullYear();
  const month = currentDate.getMonth();

  const [dragOverDate, setDragOverDate] = useState<string | null>(null);

  const weeks = useMemo(() => getMonthGrid(year, month), [year, month]);

  const eventsByDate = useMemo(() => {
    const map = new Map<string, CalendarEvent[]>();
    for (const event of events) {
      const key = `${event.start.getFullYear()}-${event.start.getMonth()}-${event.start.getDate()}`;
      if (!map.has(key)) map.set(key, []);
      map.get(key)!.push(event);
    }
    return map;
  }, [events]);

  return (
    <div className="flex h-full flex-col p-(--spacing-card)">
      {/* Weekday headers */}
      <div className="grid shrink-0 grid-cols-7 gap-(--spacing-tight)">
        {WEEKDAY_KEYS.map((key) => (
          <div
            key={key}
            className="p-(--spacing-cell) text-center text-xs font-medium text-foreground-muted"
          >
            {t(`weekdays.${key}`)}
          </div>
        ))}
      </div>

      {/* Day grid — each week row stretches equally */}
      <div className="flex min-h-0 flex-1 flex-col gap-(--spacing-tight)">
        {weeks.map((week, weekIdx) => (
          <div key={weekIdx} className="grid min-h-0 flex-1 grid-cols-7 gap-(--spacing-tight)">
            {week.map((day, dayIdx) => {
              if (!day) {
                return (
                  <div
                    key={`empty-${dayIdx}`}
                    className="overflow-hidden rounded-sm border border-border-subtle p-(--spacing-tight) opacity-40"
                  />
                );
              }

              const isToday = isSameDay(day, today);
              const dateKey = `${day.getFullYear()}-${day.getMonth()}-${day.getDate()}`;
              const dayEvents = eventsByDate.get(dateKey) ?? [];
              const visibleEvents = dayEvents.slice(0, 3);
              const overflow = dayEvents.length - 3;

              return (
                <div
                  key={day.getDate()}
                  className={cn(
                    "overflow-hidden rounded-sm border border-border-subtle p-(--spacing-tight) transition-colors duration-200",
                    isToday && "border-interactive bg-interactive/10",
                    dragOverDate === dateKey && "ring-2 ring-interactive bg-interactive/10"
                  )}
                  aria-dropeffect={onDayDrop ? "copy" : undefined}
                  onDragOver={(e) => {
                    if (!onDayDrop) return;
                    e.preventDefault();
                    e.dataTransfer.dropEffect = "copy";
                    setDragOverDate(dateKey);
                  }}
                  onDragLeave={() => setDragOverDate(null)}
                  onDrop={(e) => {
                    e.preventDefault();
                    setDragOverDate(null);
                    const driverJson = e.dataTransfer.getData("application/vtv-driver");
                    if (driverJson && onDayDrop) {
                      onDayDrop(day, driverJson);
                    }
                  }}
                >
                  <p
                    className={cn(
                      "text-sm text-foreground",
                      isToday && "font-semibold text-interactive"
                    )}
                  >
                    {day.getDate()}
                  </p>
                  <div className="mt-(--spacing-tight) flex flex-col gap-0.5">
                    {visibleEvents.map((event) => {
                      const hasGoals = event.goals && event.goals.items.length > 0;
                      return hasGoals ? (
                        <button
                          key={event.id}
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            onEventClick?.(event);
                          }}
                          className="flex w-full items-center justify-between gap-(--spacing-tight) rounded bg-surface-raised px-1 py-0.5 text-left transition-colors duration-200 hover:bg-interactive/10 cursor-pointer"
                        >
                          <span className="truncate text-[10px] font-medium text-foreground">
                            {event.title}
                          </span>
                          <GoalProgressBadge goals={event.goals!} variant="compact" />
                        </button>
                      ) : (
                        <button
                          key={event.id}
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            onEventClick?.(event);
                          }}
                          className="flex w-full items-center gap-(--spacing-tight) text-left cursor-pointer"
                        >
                          <div
                            className={cn(
                              "size-1.5 shrink-0 rounded-full",
                              categoryDotColors[event.category]
                            )}
                          />
                          <span className="truncate text-[10px] text-foreground-muted">
                            {event.title}
                          </span>
                        </button>
                      );
                    })}
                    {overflow > 0 && (
                      <span className="text-[10px] text-foreground-muted">
                        {t("calendar.moreEvents", { count: overflow })}
                      </span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        ))}
      </div>
    </div>
  );
}
