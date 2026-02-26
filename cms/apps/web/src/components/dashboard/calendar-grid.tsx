"use client";

import { useState } from "react";
import type { CalendarEvent, CalendarViewMode } from "@/types/dashboard";
import { CalendarHeader } from "./calendar-header";
import { WeekView } from "./week-view";
import { MonthView } from "./month-view";
import { ThreeMonthView } from "./three-month-view";
import { YearView } from "./year-view";

interface CalendarGridProps {
  events: CalendarEvent[];
  onDayDrop?: (date: Date, driverJson: string) => void;
  onEventClick?: (event: CalendarEvent) => void;
  onDriverClick?: (event: CalendarEvent) => void;
}

export function CalendarGrid({ events, onDayDrop, onEventClick, onDriverClick }: CalendarGridProps) {
  const [view, setView] = useState<CalendarViewMode>("week");
  const [currentDate, setCurrentDate] = useState(() => new Date());

  return (
    <div className="flex h-full flex-col overflow-hidden rounded-lg border border-card-border bg-card-bg">
      <CalendarHeader
        currentDate={currentDate}
        view={view}
        onViewChange={setView}
        onDateChange={setCurrentDate}
      />
      <div className="min-h-0 flex-1 overflow-auto">
        {view === "week" && (
          <WeekView currentDate={currentDate} events={events} onDayDrop={onDayDrop} onEventClick={onEventClick} onDriverClick={onDriverClick} />
        )}
        {view === "month" && (
          <MonthView currentDate={currentDate} events={events} onDayDrop={onDayDrop} onEventClick={onEventClick} />
        )}
        {view === "3month" && (
          <ThreeMonthView currentDate={currentDate} events={events} onDayDrop={onDayDrop} onEventClick={onEventClick} />
        )}
        {view === "year" && (
          <YearView currentDate={currentDate} events={events} />
        )}
      </div>
    </div>
  );
}
