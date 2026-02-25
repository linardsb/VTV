"use client";

import { useMemo, useState } from "react";
import { useTranslations } from "next-intl";
import { cn } from "@/lib/utils";
import type { CalendarEvent } from "@/types/dashboard";
import { CalendarEventCard } from "./calendar-event";
import { LiveTimeline } from "./live-timeline";

interface WeekViewProps {
  currentDate: Date;
  events: CalendarEvent[];
  onDayDrop?: (date: Date, driverJson: string) => void;
}

const START_HOUR = 6;
const END_HOUR = 22;
const TOTAL_HOURS = END_HOUR - START_HOUR;
const WEEKDAY_KEYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"] as const;

function getMonday(date: Date): Date {
  const d = new Date(date);
  const day = d.getDay();
  const diff = (day + 6) % 7;
  d.setDate(d.getDate() - diff);
  d.setHours(0, 0, 0, 0);
  return d;
}

function isSameDay(a: Date, b: Date): boolean {
  return (
    a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate()
  );
}

export function WeekView({ currentDate, events, onDayDrop }: WeekViewProps) {
  const t = useTranslations("dashboard");
  const today = new Date();

  const [dragOverDay, setDragOverDay] = useState<number | null>(null);

  const weekDays = useMemo(() => {
    const monday = getMonday(currentDate);
    return Array.from({ length: 7 }, (_, i) => {
      const d = new Date(monday);
      d.setDate(monday.getDate() + i);
      return d;
    });
  }, [currentDate]);

  const hours = useMemo(
    () => Array.from({ length: TOTAL_HOURS }, (_, i) => START_HOUR + i),
    []
  );

  const eventsByDay = useMemo(() => {
    const map = new Map<number, CalendarEvent[]>();
    for (let i = 0; i < 7; i++) {
      map.set(i, []);
    }
    for (const event of events) {
      const dayIdx = weekDays.findIndex((d) => isSameDay(d, event.start));
      if (dayIdx >= 0) {
        map.get(dayIdx)!.push(event);
      }
    }
    return map;
  }, [events, weekDays]);

  return (
    <div className="overflow-auto">
      {/* Day header row */}
      <div className="grid grid-cols-[4rem_repeat(7,1fr)] border-b border-border">
        <div className="p-(--spacing-cell)" />
        {weekDays.map((day, i) => {
          const isToday = isSameDay(day, today);
          return (
            <div
              key={i}
              className={cn(
                "border-l border-border-subtle p-(--spacing-cell) text-center",
                isToday && "bg-interactive/10",
                dragOverDay === i && "bg-interactive/10"
              )}
            >
              <p
                className={cn(
                  "text-xs font-medium text-foreground-muted",
                  isToday && "text-interactive"
                )}
              >
                {t(`weekdays.${WEEKDAY_KEYS[i]}`)}
              </p>
              <p
                className={cn(
                  "text-heading font-semibold text-foreground",
                  isToday && "text-interactive"
                )}
              >
                {day.getDate()}
              </p>
            </div>
          );
        })}
      </div>

      {/* Time grid */}
      <div className="relative grid grid-cols-[4rem_repeat(7,1fr)]">
        <LiveTimeline startHour={START_HOUR} endHour={END_HOUR} />

        {/* Time labels + hour rows */}
        {hours.map((hour) => (
          <div
            key={`time-${hour}`}
            className="flex h-(--spacing-row) items-start border-b border-border-subtle p-(--spacing-tight)"
          >
            <span className="text-xs text-foreground-muted">
              {String(hour).padStart(2, "0")}:00
            </span>
          </div>
        ))}

        {/* Day columns with events */}
        {weekDays.map((_, dayIdx) => (
          <div
            key={`col-${dayIdx}`}
            className={cn(
              "relative border-l border-border-subtle transition-colors duration-200",
              dragOverDay === dayIdx && "bg-interactive/10"
            )}
            style={{
              gridColumn: dayIdx + 2,
              gridRow: `1 / ${TOTAL_HOURS + 1}`,
            }}
            onDragOver={(e) => {
              if (!onDayDrop) return;
              e.preventDefault();
              e.dataTransfer.dropEffect = "copy";
              setDragOverDay(dayIdx);
            }}
            onDragLeave={() => setDragOverDay(null)}
            onDrop={(e) => {
              e.preventDefault();
              setDragOverDay(null);
              const driverJson = e.dataTransfer.getData("application/vtv-driver");
              if (driverJson && onDayDrop) {
                onDayDrop(weekDays[dayIdx], driverJson);
              }
            }}
          >
            {/* Hour row borders */}
            {hours.map((hour) => (
              <div
                key={`cell-${dayIdx}-${hour}`}
                className="h-(--spacing-row) border-b border-border-subtle"
              />
            ))}

            {/* Events overlay */}
            {eventsByDay.get(dayIdx)?.map((event) => {
              const startMin =
                event.start.getHours() * 60 + event.start.getMinutes();
              const endMin =
                event.end.getHours() * 60 + event.end.getMinutes();
              // COUPLING: 48px must match --spacing-row token in tokens.css (3rem = 48px at 16px base)
              const ROW_HEIGHT_PX = 48;
              const topPx =
                ((startMin - START_HOUR * 60) / 60) * ROW_HEIGHT_PX;
              const heightPx = ((endMin - startMin) / 60) * ROW_HEIGHT_PX;

              return (
                <div
                  key={event.id}
                  className="absolute inset-x-0 overflow-hidden bg-background"
                  style={{
                    top: `${topPx}px`,
                    height: `${heightPx}px`,
                  }}
                >
                  <CalendarEventCard event={event} />
                </div>
              );
            })}
          </div>
        ))}
      </div>
    </div>
  );
}
