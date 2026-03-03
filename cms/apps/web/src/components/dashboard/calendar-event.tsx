"use client";

import { useLocale, useTranslations } from "next-intl";
import { cn } from "@/lib/utils";
import type { CalendarEvent as CalendarEventType } from "@/types/dashboard";
import { GoalProgressBadge } from "./goal-progress-badge";
import { getEventCardStyle } from "./event-styles";

interface CalendarEventCardProps {
  event: CalendarEventType;
  onClick?: () => void;
  onDriverClick?: () => void;
}

const priorityStyles = {
  high: "bg-status-critical/10 text-status-critical",
  medium: "bg-status-delayed/10 text-status-delayed",
  low: "bg-status-ontime/10 text-status-ontime",
} as const;

function formatTime(date: Date, locale: string): string {
  return date.toLocaleTimeString(locale, { hour: "2-digit", minute: "2-digit", hour12: false });
}

function EventTitle({ title, onDriverClick }: { title: string; onDriverClick?: () => void }) {
  const dashIndex = title.indexOf(" - ");
  if (dashIndex === -1 || !onDriverClick) {
    return <p className="truncate font-medium text-foreground">{title}</p>;
  }
  const driverName = title.slice(0, dashIndex);
  const rest = title.slice(dashIndex);
  return (
    <p className="truncate font-medium text-foreground">
      <span
        role="button"
        tabIndex={0}
        className="cursor-pointer underline decoration-foreground-subtle/40 underline-offset-2 transition-colors duration-200 hover:text-interactive hover:decoration-interactive"
        onClick={(e) => {
          e.stopPropagation();
          onDriverClick();
        }}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.stopPropagation();
            onDriverClick();
          }
        }}
      >
        {driverName}
      </span>
      {rest}
    </p>
  );
}

export function CalendarEventCard({ event, onClick, onDriverClick }: CalendarEventCardProps) {
  const t = useTranslations("dashboard");
  const locale = useLocale();

  return (
    <div
      className={cn(
        "h-full cursor-pointer overflow-hidden rounded-md p-(--spacing-cell) text-xs transition-colors duration-200 hover:opacity-80",
        getEventCardStyle(event.title, event.category)
      )}
      onClick={onClick}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") onClick?.();
      }}
      role={onClick ? "button" : undefined}
      tabIndex={onClick ? 0 : undefined}
    >
      <EventTitle title={event.title} onDriverClick={onDriverClick} />
      <p className="text-foreground-muted">
        {formatTime(event.start, locale)} – {formatTime(event.end, locale)}
      </p>
      <div className="mt-(--spacing-tight) flex items-center gap-(--spacing-tight)">
        <span
          className={cn(
            "inline-flex items-center rounded-none px-1.5 py-0.5 text-[10px] font-medium",
            priorityStyles[event.priority]
          )}
        >
          {t(`priority.${event.priority}`)}
        </span>
        {event.goals && event.goals.items.length > 0 && (
          <GoalProgressBadge goals={event.goals} variant="compact" />
        )}
      </div>
    </div>
  );
}
