"use client";

import { useLocale, useTranslations } from "next-intl";
import { CheckCircle2, Circle } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  HoverCard,
  HoverCardContent,
  HoverCardTrigger,
} from "@/components/ui/hover-card";
import { Separator } from "@/components/ui/separator";
import type { CalendarEvent } from "@/types/dashboard";
import { getEventDotColor } from "./event-styles";

interface EventHoverCardProps {
  event: CalendarEvent;
  children: React.ReactNode;
}

const categoryI18nKey: Record<string, string> = {
  maintenance: "maintenance",
  "route-change": "routeChange",
  "driver-shift": "driverShift",
  "service-alert": "serviceAlert",
};

const priorityStyles = {
  high: "bg-status-critical/10 text-status-critical",
  medium: "bg-status-delayed/10 text-status-delayed",
  low: "bg-status-ontime/10 text-status-ontime",
} as const;

function formatTime(date: Date, locale: string): string {
  return date.toLocaleTimeString(locale, {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

function isAllDay(start: Date, end: Date): boolean {
  return (
    start.getHours() === 0 &&
    start.getMinutes() === 0 &&
    end.getHours() === 23 &&
    end.getMinutes() === 59
  );
}

const MAX_VISIBLE_GOALS = 5;

export function EventHoverCard({ event, children }: EventHoverCardProps) {
  const t = useTranslations("dashboard");
  const locale = useLocale();

  const hasDescription = Boolean(event.description?.trim());
  const goalItems = event.goals?.items ?? [];
  const hasGoals = goalItems.length > 0;
  const completedGoals = goalItems.filter((g) => g.completed).length;
  const visibleGoals = goalItems.slice(0, MAX_VISIBLE_GOALS);
  const overflowGoals = goalItems.length - MAX_VISIBLE_GOALS;

  const dotColor = getEventDotColor(event.title, event.category);
  const categoryKey = categoryI18nKey[event.category] ?? "driverShift";

  return (
    <HoverCard openDelay={300} closeDelay={100}>
      <HoverCardTrigger asChild>{children}</HoverCardTrigger>
      <HoverCardContent
        side="top"
        sideOffset={8}
        align="center"
        className="w-72 p-(--spacing-card)"
      >
        {/* Title + Category */}
        <div className="flex flex-col gap-(--spacing-tight)">
          <p className="text-sm font-semibold text-foreground">
            {event.title}
          </p>
          <div className="flex items-center gap-(--spacing-inline)">
            <div className={cn("size-2 shrink-0 rounded-full", dotColor)} />
            <span className="text-xs text-foreground-muted">
              {t(`events.${categoryKey}`)}
            </span>
          </div>
        </div>

        <Separator className="my-(--spacing-tight)" />

        {/* Time */}
        <div className="flex items-center justify-between">
          <span className="text-xs text-foreground-muted">
            {t("hover.time")}
          </span>
          <span className="text-xs font-medium text-foreground">
            {isAllDay(event.start, event.end)
              ? t("hover.allDay")
              : `${formatTime(event.start, locale)} – ${formatTime(event.end, locale)}`}
          </span>
        </div>

        {/* Priority */}
        <div className="mt-(--spacing-tight) flex items-center justify-between">
          <span className="text-xs text-foreground-muted">
            {t("hover.priority")}
          </span>
          <span
            className={cn(
              "inline-flex items-center rounded-none px-1.5 py-0.5 text-[10px] font-medium",
              priorityStyles[event.priority]
            )}
          >
            {t(`priority.${event.priority}`)}
          </span>
        </div>

        {/* Description (conditional) */}
        {hasDescription && (
          <>
            <Separator className="my-(--spacing-tight)" />
            <div className="flex flex-col gap-(--spacing-tight)">
              <span className="text-xs text-foreground-muted">
                {t("hover.description")}
              </span>
              <p className="line-clamp-3 text-xs text-foreground">
                {event.description}
              </p>
            </div>
          </>
        )}

        {/* Goals (conditional) */}
        {hasGoals && (
          <>
            <Separator className="my-(--spacing-tight)" />
            <div className="flex flex-col gap-(--spacing-tight)">
              <span className="text-xs text-foreground-muted">
                {t("hover.goals")} ({completedGoals}/{goalItems.length})
              </span>
              <ul className="flex flex-col gap-0.5">
                {visibleGoals.map((goal, idx) => (
                  <li
                    key={idx}
                    className="flex items-center gap-(--spacing-inline)"
                  >
                    {goal.completed ? (
                      <CheckCircle2 className="size-3 shrink-0 text-status-ontime" />
                    ) : (
                      <Circle className="size-3 shrink-0 text-foreground-muted" />
                    )}
                    <span
                      className={cn(
                        "text-xs",
                        goal.completed
                          ? "text-foreground-muted line-through"
                          : "text-foreground"
                      )}
                    >
                      {goal.text}
                    </span>
                  </li>
                ))}
              </ul>
              {overflowGoals > 0 && (
                <span className="text-[10px] text-foreground-muted">
                  +{overflowGoals} {t("calendar.moreEvents", { count: overflowGoals })}
                </span>
              )}
            </div>
          </>
        )}
      </HoverCardContent>
    </HoverCard>
  );
}
