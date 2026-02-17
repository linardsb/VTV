"use client";

import { useLocale, useTranslations } from "next-intl";
import { cn } from "@/lib/utils";
import type { CalendarEvent as CalendarEventType } from "@/types/dashboard";

interface CalendarEventCardProps {
  event: CalendarEventType;
}

const categoryStyles = {
  maintenance: "bg-blue-400/10 border-l-2 border-l-blue-400",
  "route-change": "bg-amber-400/10 border-l-2 border-l-amber-400",
  "driver-shift": "bg-emerald-500/10 border-l-2 border-l-emerald-500",
  "service-alert": "bg-red-500/10 border-l-2 border-l-red-500",
} as const;

const priorityStyles = {
  high: "bg-status-critical/10 text-status-critical",
  medium: "bg-status-delayed/10 text-status-delayed",
  low: "bg-status-ontime/10 text-status-ontime",
} as const;

function formatTime(date: Date, locale: string): string {
  return date.toLocaleTimeString(locale, { hour: "2-digit", minute: "2-digit", hour12: false });
}

export function CalendarEventCard({ event }: CalendarEventCardProps) {
  const t = useTranslations("dashboard");
  const locale = useLocale();

  return (
    <div
      className={cn(
        "h-full cursor-pointer overflow-hidden rounded-md p-(--spacing-cell) text-xs transition-colors duration-200 hover:opacity-80",
        categoryStyles[event.category]
      )}
    >
      <p className="truncate font-medium text-foreground">{t(event.title)}</p>
      <p className="text-foreground-muted">
        {formatTime(event.start, locale)} – {formatTime(event.end, locale)}
      </p>
      <span
        className={cn(
          "mt-(--spacing-tight) inline-flex items-center rounded-full px-1.5 py-0.5 text-[10px] font-medium",
          priorityStyles[event.priority]
        )}
      >
        {t(`priority.${event.priority}`)}
      </span>
    </div>
  );
}
