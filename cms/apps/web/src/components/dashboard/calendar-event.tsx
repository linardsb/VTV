"use client";

import { useLocale, useTranslations } from "next-intl";
import { cn } from "@/lib/utils";
import type { CalendarEvent as CalendarEventType } from "@/types/dashboard";
import { GoalProgressBadge } from "./goal-progress-badge";

interface CalendarEventCardProps {
  event: CalendarEventType;
  onClick?: () => void;
}

const categoryStyles = {
  maintenance: "bg-category-maintenance/10 border-l-2 border-l-category-maintenance",
  "route-change": "bg-category-route-change/10 border-l-2 border-l-category-route-change",
  "driver-shift": "bg-category-driver-shift/10 border-l-2 border-l-category-driver-shift",
  "service-alert": "bg-category-service-alert/10 border-l-2 border-l-category-service-alert",
} as const;

const priorityStyles = {
  high: "bg-status-critical/10 text-status-critical",
  medium: "bg-status-delayed/10 text-status-delayed",
  low: "bg-status-ontime/10 text-status-ontime",
} as const;

function formatTime(date: Date, locale: string): string {
  return date.toLocaleTimeString(locale, { hour: "2-digit", minute: "2-digit", hour12: false });
}

export function CalendarEventCard({ event, onClick }: CalendarEventCardProps) {
  const t = useTranslations("dashboard");
  const locale = useLocale();

  return (
    <div
      className={cn(
        "h-full cursor-pointer overflow-hidden rounded-md p-(--spacing-cell) text-xs transition-colors duration-200 hover:opacity-80",
        categoryStyles[event.category]
      )}
      onClick={onClick}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") onClick?.();
      }}
      role={onClick ? "button" : undefined}
      tabIndex={onClick ? 0 : undefined}
    >
      <p className="truncate font-medium text-foreground">{event.title}</p>
      <p className="text-foreground-muted">
        {formatTime(event.start, locale)} – {formatTime(event.end, locale)}
      </p>
      <div className="mt-(--spacing-tight) flex items-center gap-(--spacing-tight)">
        <span
          className={cn(
            "inline-flex items-center rounded-full px-1.5 py-0.5 text-[10px] font-medium",
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
