"use client";

import { useMemo, useState } from "react";
import { useTranslations } from "next-intl";
import { cn } from "@/lib/utils";
import type { CalendarEvent } from "@/types/dashboard";
import { CalendarEventCard } from "./calendar-event";
import { EventHoverCard } from "./event-hover-card";
import { LiveTimeline } from "./live-timeline";

interface WeekViewProps {
  currentDate: Date;
  events: CalendarEvent[];
  onDayDrop?: (date: Date, driverJson: string) => void;
  onEventClick?: (event: CalendarEvent) => void;
  onDriverClick?: (event: CalendarEvent) => void;
}

const START_HOUR = 0;
const END_HOUR = 24;
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

/** A timed event clipped to a single day's visible range */
interface TimedSlice {
  event: CalendarEvent;
  /** Minutes from midnight, clipped to [START_HOUR*60, END_HOUR*60] */
  startMin: number;
  /** Minutes from midnight, clipped to [START_HOUR*60, END_HOUR*60] */
  endMin: number;
}

interface LayoutedSlice {
  slice: TimedSlice;
  column: number;
  totalColumns: number;
}

/** Assign side-by-side columns to overlapping timed event slices */
function layoutEvents(slices: TimedSlice[]): LayoutedSlice[] {
  if (slices.length === 0) return [];

  const sorted = [...slices].sort(
    (a, b) => a.startMin - b.startMin || (b.endMin - b.startMin) - (a.endMin - a.startMin)
  );

  const columns: { end: number; slices: TimedSlice[] }[] = [];
  const sliceColumns = new Map<TimedSlice, number>();

  for (const slice of sorted) {
    let placed = false;
    for (let c = 0; c < columns.length; c++) {
      if (slice.startMin >= columns[c].end) {
        columns[c].end = slice.endMin;
        columns[c].slices.push(slice);
        sliceColumns.set(slice, c);
        placed = true;
        break;
      }
    }
    if (!placed) {
      sliceColumns.set(slice, columns.length);
      columns.push({
        end: slice.endMin,
        slices: [slice],
      });
    }
  }

  // For each slice, find how many columns overlap at that time
  return sorted.map((slice) => {
    let maxCols = 1;
    for (const other of sorted) {
      if (other.startMin < slice.endMin && other.endMin > slice.startMin) {
        const col = sliceColumns.get(other)!;
        if (col + 1 > maxCols) maxCols = col + 1;
      }
    }
    return {
      slice,
      column: sliceColumns.get(slice)!,
      totalColumns: maxCols,
    };
  });
}

export function WeekView({ currentDate, events, onDayDrop, onEventClick, onDriverClick }: WeekViewProps) {
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
    const map = new Map<number, TimedSlice[]>();
    for (let i = 0; i < 7; i++) {
      map.set(i, []);
    }

    for (const event of events) {
      // If event ends exactly at midnight, it doesn't extend into that day
      const effectiveEnd = (event.end.getHours() === 0 && event.end.getMinutes() === 0)
        ? new Date(event.end.getTime() - 1)
        : event.end;

      for (let i = 0; i < 7; i++) {
        const dayStart = new Date(weekDays[i]);
        dayStart.setHours(0, 0, 0, 0);
        const dayEnd = new Date(dayStart);
        dayEnd.setHours(23, 59, 59, 999);

        // Check if event overlaps with this day
        if (event.start <= dayEnd && effectiveEnd > dayStart) {
          // Clip the event's time to this day's visible range (START_HOUR-END_HOUR)
          const dayVisibleStart = new Date(weekDays[i]);
          dayVisibleStart.setHours(START_HOUR, 0, 0, 0);
          const dayVisibleEnd = new Date(weekDays[i]);
          dayVisibleEnd.setHours(END_HOUR, 0, 0, 0);

          const clipStartMs = Math.max(event.start.getTime(), dayVisibleStart.getTime());
          const clipEndMs = Math.min(effectiveEnd.getTime(), dayVisibleEnd.getTime());

          if (clipEndMs > clipStartMs) {
            const clippedStart = new Date(clipStartMs);
            const clippedEnd = new Date(clipEndMs);
            map.get(i)!.push({
              event,
              startMin: clippedStart.getHours() * 60 + clippedStart.getMinutes(),
              endMin: clippedEnd.getHours() * 60 + clippedEnd.getMinutes(),
            });
          }
        }
      }
    }

    return map;
  }, [events, weekDays]);

  return (
    <div className="overflow-auto">
      {/* Day header row — sticky while scrolling */}
      <div className="sticky top-0 z-20 grid grid-cols-[4rem_repeat(7,1fr)] border-b border-border bg-surface">
        <div className="p-(--spacing-cell)" />
        {weekDays.map((day, i) => {
          const isToday = isSameDay(day, today);
          return (
            <div
              key={i}
              className={cn(
                "border-l border-border-subtle px-2 py-1.5 text-center",
                dragOverDay === i && "bg-interactive/10"
              )}
            >
              <p
                className={cn(
                  "text-[11px] font-medium uppercase text-foreground-muted",
                  isToday && "text-interactive"
                )}
              >
                {t(`weekdays.${WEEKDAY_KEYS[i]}`)}
              </p>
              <p
                className={cn(
                  "text-xl font-semibold leading-tight",
                  isToday
                    ? "text-interactive"
                    : "text-foreground"
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

        {/* Day columns with timed events */}
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
            aria-dropeffect={onDayDrop ? "copy" : undefined}
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

            {/* Timed events overlay — side-by-side for overlaps */}
            {layoutEvents(eventsByDay.get(dayIdx) ?? []).map(({ slice, column, totalColumns }) => {
              // COUPLING: 48px must match --spacing-row token in tokens.css (3rem = 48px at 16px base)
              const ROW_HEIGHT_PX = 48;
              const topPx =
                ((slice.startMin - START_HOUR * 60) / 60) * ROW_HEIGHT_PX;
              const heightPx =
                ((slice.endMin - slice.startMin) / 60) * ROW_HEIGHT_PX;
              const widthPct = 100 / totalColumns;
              const leftPct = column * widthPct;

              return (
                <EventHoverCard key={`${slice.event.id}-${dayIdx}`} event={slice.event}>
                  <div
                    className="absolute overflow-hidden rounded-md bg-surface"
                    style={{
                      top: `${topPx}px`,
                      height: `${heightPx}px`,
                      left: `${leftPct}%`,
                      width: `${widthPct}%`,
                    }}
                  >
                    <CalendarEventCard
                      event={slice.event}
                      onClick={onEventClick ? () => onEventClick(slice.event) : undefined}
                      onDriverClick={onDriverClick ? () => onDriverClick(slice.event) : undefined}
                    />
                  </div>
                </EventHoverCard>
              );
            })}
          </div>
        ))}
      </div>
    </div>
  );
}
