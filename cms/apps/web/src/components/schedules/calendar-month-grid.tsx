"use client";

import { useState, useMemo } from "react";
import { useTranslations } from "next-intl";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

/** Accepts a full Calendar or just the fields the grid needs (for live form preview). */
interface CalendarData {
  monday: boolean;
  tuesday: boolean;
  wednesday: boolean;
  thursday: boolean;
  friday: boolean;
  saturday: boolean;
  sunday: boolean;
  start_date: string;
  end_date: string;
}

interface CalendarMonthGridProps {
  calendar: CalendarData;
}

const DAY_KEYS = ["sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday"] as const;
const WEEK_HEADERS = ["sun", "mon", "tue", "wed", "thu", "fri", "sat"] as const;

interface DayCell {
  date: Date;
  inMonth: boolean;
  isActive: boolean;
  isToday: boolean;
}

function computeInitialMonth(startDate: string, endDate: string): { year: number; month: number } {
  const today = new Date();
  const start = new Date(startDate + "T00:00:00");
  const end = new Date(endDate + "T00:00:00");
  const ref = today >= start && today <= end ? today : start;
  return { year: ref.getFullYear(), month: ref.getMonth() };
}

export function CalendarMonthGrid({ calendar }: CalendarMonthGridProps) {
  const t = useTranslations("schedules.calendars");
  const tDays = useTranslations("schedules.days");

  const initial = computeInitialMonth(calendar.start_date, calendar.end_date);
  const [viewYear, setViewYear] = useState(initial.year);
  const [viewMonth, setViewMonth] = useState(initial.month);

  const daysInMonth = useMemo(() => {
    const todayStr = new Date().toDateString();
    const startDate = new Date(calendar.start_date + "T00:00:00");
    const endDate = new Date(calendar.end_date + "T00:00:00");

    const firstDay = new Date(viewYear, viewMonth, 1);
    const lastDay = new Date(viewYear, viewMonth + 1, 0);
    const startPad = firstDay.getDay(); // 0=Sun

    const days: DayCell[] = [];

    // Padding days from previous month
    for (let i = 0; i < startPad; i++) {
      const d = new Date(viewYear, viewMonth, -startPad + i + 1);
      days.push({ date: d, inMonth: false, isActive: false, isToday: false });
    }

    // Days in current month
    for (let d = 1; d <= lastDay.getDate(); d++) {
      const date = new Date(viewYear, viewMonth, d);
      const dayOfWeek = date.getDay();
      const dayKey = DAY_KEYS[dayOfWeek];
      const inRange = date >= startDate && date <= endDate;
      const dayEnabled = Boolean(calendar[dayKey as keyof CalendarData]);
      const isActive = inRange && dayEnabled;
      const isToday = date.toDateString() === todayStr;
      days.push({ date, inMonth: true, isActive, isToday });
    }

    // Padding days to complete the last week
    const remainder = days.length % 7;
    if (remainder > 0) {
      const remaining = 7 - remainder;
      for (let i = 1; i <= remaining; i++) {
        const d = new Date(viewYear, viewMonth + 1, i);
        days.push({ date: d, inMonth: false, isActive: false, isToday: false });
      }
    }

    return days;
  }, [viewYear, viewMonth, calendar]);

  const monthLabel = useMemo(
    () =>
      new Intl.DateTimeFormat(undefined, { year: "numeric", month: "long" }).format(
        new Date(viewYear, viewMonth)
      ),
    [viewYear, viewMonth]
  );

  function prevMonthNav() {
    if (viewMonth === 0) {
      setViewYear((y) => y - 1);
      setViewMonth(11);
    } else {
      setViewMonth((m) => m - 1);
    }
  }

  function nextMonthNav() {
    if (viewMonth === 11) {
      setViewYear((y) => y + 1);
      setViewMonth(0);
    } else {
      setViewMonth((m) => m + 1);
    }
  }

  return (
    <div className="space-y-(--spacing-tight)">
      <div className="flex items-center justify-between">
        <p className="text-xs font-medium text-label-text uppercase tracking-wide">
          {t("monthGrid")}
        </p>
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="sm"
            className="size-7 p-0 cursor-pointer"
            onClick={prevMonthNav}
            aria-label={t("prevMonth")}
          >
            <ChevronLeft className="size-4" />
          </Button>
          <span className="text-xs font-medium text-foreground min-w-[120px] text-center">
            {monthLabel}
          </span>
          <Button
            variant="ghost"
            size="sm"
            className="size-7 p-0 cursor-pointer"
            onClick={nextMonthNav}
            aria-label={t("nextMonth")}
          >
            <ChevronRight className="size-4" />
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-7 gap-px rounded-md border border-border overflow-hidden bg-border">
        {/* Week day headers */}
        {WEEK_HEADERS.map((day) => (
          <div
            key={day}
            className="bg-surface py-1 text-center text-[10px] font-medium text-foreground-muted uppercase"
          >
            {tDays(day)}
          </div>
        ))}
        {/* Day cells */}
        <TooltipProvider delayDuration={200}>
          {daysInMonth.map((day, i) => (
            <Tooltip key={i}>
              <TooltipTrigger asChild>
                <div
                  className={cn(
                    "flex items-center justify-center py-1.5 text-xs transition-colors",
                    !day.inMonth && "bg-surface text-foreground-subtle",
                    day.inMonth && !day.isActive && "bg-background text-foreground-muted",
                    day.inMonth && day.isActive && "bg-status-ontime/15 text-status-ontime font-medium",
                    day.isToday && "ring-1 ring-inset ring-interactive"
                  )}
                >
                  {day.date.getDate()}
                </div>
              </TooltipTrigger>
              <TooltipContent side="top" className="text-xs">
                {day.isActive ? t("gridActive") : t("gridInactive")}
              </TooltipContent>
            </Tooltip>
          ))}
        </TooltipProvider>
      </div>

      {/* Legend */}
      <div className="flex items-center gap-1.5 text-[10px] text-foreground-muted">
        <span className="inline-block size-2.5 rounded-sm ring-1 ring-interactive" />
        <span>{t("today")}</span>
        <span className="ml-2 inline-block size-2.5 rounded-sm bg-status-ontime/15" />
        <span>{t("gridActive")}</span>
      </div>
    </div>
  );
}
