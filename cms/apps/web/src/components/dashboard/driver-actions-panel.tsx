"use client";

import { useState, useCallback } from "react";
import { useTranslations, useLocale } from "next-intl";
import { useSession } from "next-auth/react";
import { toast } from "sonner";
import {
  Clock,
  CalendarOff,
  Thermometer,
  GraduationCap,
  Target,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type { CalendarEvent } from "@/types/dashboard";
import type { EventCreate } from "@/types/event";
import { createEvent } from "@/lib/events-sdk";
import { useDriverEvents } from "@/hooks/use-driver-events";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Separator } from "@/components/ui/separator";
import { GoalProgressBadge } from "./goal-progress-badge";

interface DriverActionsPanelProps {
  driverId: number | null;
  driverName: string;
  date: Date | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onEventClick: (event: CalendarEvent) => void;
  onEventCreated: () => void;
}

const SCHEDULE_ROLES = ["admin", "editor", "dispatcher"];

const SHIFT_TIMES: Record<string, { start: string; end: string; nextDay: boolean }> = {
  morning: { start: "05:00", end: "13:00", nextDay: false },
  afternoon: { start: "13:00", end: "21:00", nextDay: false },
  evening: { start: "17:00", end: "01:00", nextDay: true },
  night: { start: "22:00", end: "06:00", nextDay: true },
};

function buildDatetime(date: Date, time: string, nextDay: boolean): string {
  const [hours, minutes] = time.split(":").map(Number);
  const d = new Date(date);
  if (nextDay) d.setDate(d.getDate() + 1);
  d.setHours(hours, minutes, 0, 0);
  return d.toISOString();
}

function formatTime(date: Date, locale: string): string {
  return date.toLocaleTimeString(locale, { hour: "2-digit", minute: "2-digit", hour12: false });
}

import { getEventCardStyle } from "./event-styles";

function DriverEventCard({
  event,
  locale,
  onClickGoals,
  tActions,
}: {
  event: CalendarEvent;
  locale: string;
  onClickGoals: () => void;
  tActions: (key: string, values?: Record<string, string>) => string;
}) {
  const isAllDay =
    event.start.getHours() === 0 &&
    event.start.getMinutes() === 0 &&
    event.end.getHours() === 23 &&
    event.end.getMinutes() === 59;

  return (
    <div
      className={cn(
        "flex items-center justify-between rounded-md p-(--spacing-cell)",
        getEventCardStyle(event.title, event.category),
      )}
    >
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium text-foreground">
          {event.title}
        </p>
        <p className="text-xs text-foreground-muted">
          {isAllDay
            ? tActions("allDay")
            : tActions("eventTime", {
                start: formatTime(event.start, locale),
                end: formatTime(event.end, locale),
              })}
        </p>
      </div>
      <div className="flex shrink-0 items-center gap-(--spacing-tight)">
        {event.goals && event.goals.items.length > 0 && (
          <GoalProgressBadge goals={event.goals} variant="compact" />
        )}
        {event.goals && event.goals.items.length > 0 && (
          <button
            type="button"
            onClick={onClickGoals}
            className="cursor-pointer rounded-md p-1 text-foreground-muted transition-colors duration-200 hover:bg-surface hover:text-interactive"
            title={tActions("viewGoals")}
          >
            <Target className="size-3.5" />
          </button>
        )}
      </div>
    </div>
  );
}

function ActionCard({
  icon,
  title,
  description,
  onClick,
  disabled,
}: {
  icon: React.ReactNode;
  title: string;
  description: string;
  onClick: () => void;
  disabled: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={cn(
        "flex w-full items-center gap-(--spacing-inline) rounded-lg border border-border-subtle p-(--spacing-card) text-left transition-colors duration-200 hover:border-border hover:bg-surface cursor-pointer",
        disabled && "pointer-events-none opacity-50",
      )}
    >
      <div className="flex size-8 shrink-0 items-center justify-center rounded-md bg-interactive/10 text-interactive">
        {icon}
      </div>
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium text-foreground">{title}</p>
        <p className="text-xs text-foreground-muted">{description}</p>
      </div>
    </button>
  );
}

export function DriverActionsPanel({
  driverId,
  driverName,
  date,
  open,
  onOpenChange,
  onEventClick,
  onEventCreated,
}: DriverActionsPanelProps) {
  const tDrop = useTranslations("dashboard.dropAction");
  const tActions = useTranslations("dashboard.driverActions");
  const locale = useLocale();
  const { data: session } = useSession();

  const [isSaving, setIsSaving] = useState(false);

  const userRole: string = (session?.user?.role as string) ?? "";
  const canSchedule = SCHEDULE_ROLES.includes(userRole);

  const { events: driverEvents, isLoading, refetch } = useDriverEvents(
    open ? driverId : null,
    date,
  );

  const formattedDate = date
    ? date.toLocaleDateString(locale, {
        weekday: "long",
        year: "numeric",
        month: "long",
        day: "numeric",
      })
    : "";

  const handleCreate = useCallback(
    async (eventData: EventCreate) => {
      setIsSaving(true);
      try {
        await createEvent(eventData);
        toast.success(tDrop("created"));
        onEventCreated();
        await refetch();
      } catch {
        toast.error(tDrop("createError"));
      } finally {
        setIsSaving(false);
      }
    },
    [tDrop, onEventCreated, refetch],
  );

  function handleAssignShift() {
    if (!driverId || !date) return;
    const times = SHIFT_TIMES.morning;
    void handleCreate({
      title: `${driverName} - ${tDrop("shiftMorning")}`,
      start_datetime: buildDatetime(date, times.start, false),
      end_datetime: buildDatetime(date, times.end, times.nextDay),
      priority: "medium",
      category: "driver-shift",
      driver_id: driverId,
    });
  }

  function handleMarkLeave() {
    if (!driverId || !date) return;
    void handleCreate({
      title: tDrop("eventTitleLeave", { name: driverName }),
      start_datetime: buildDatetime(date, "00:00", false),
      end_datetime: buildDatetime(date, "23:59", false),
      priority: "low",
      category: "driver-shift",
      driver_id: driverId,
    });
  }

  function handleMarkSick() {
    if (!driverId || !date) return;
    void handleCreate({
      title: tDrop("eventTitleSick", { name: driverName }),
      start_datetime: buildDatetime(date, "00:00", false),
      end_datetime: buildDatetime(date, "23:59", false),
      priority: "high",
      category: "driver-shift",
      driver_id: driverId,
    });
  }

  function handleScheduleTraining() {
    if (!driverId || !date) return;
    void handleCreate({
      title: tDrop("eventTitleTraining", { name: driverName }),
      start_datetime: buildDatetime(date, "09:00", false),
      end_datetime: buildDatetime(date, "11:00", false),
      priority: "medium",
      category: "maintenance",
      driver_id: driverId,
    });
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[36rem]">
        <DialogHeader>
          <DialogTitle>{tActions("title")}</DialogTitle>
          <DialogDescription>
            {tActions("subtitle", { name: driverName, date: formattedDate })}
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-col gap-(--spacing-grid)">
          {/* Driver events for this day */}
          <div>
            <p className="mb-(--spacing-tight) text-sm font-medium text-foreground">
              {tActions("todayEvents")}
            </p>
            {isLoading ? (
              <div className="flex flex-col gap-(--spacing-tight)">
                {[1, 2].map((i) => (
                  <div
                    key={`skeleton-${String(i)}`}
                    className="h-12 animate-pulse rounded-md bg-surface"
                  />
                ))}
              </div>
            ) : driverEvents.length === 0 ? (
              <p className="py-(--spacing-card) text-center text-sm text-foreground-muted">
                {tActions("noEvents")}
              </p>
            ) : (
              <div className="flex flex-col gap-(--spacing-tight)">
                {driverEvents.map((event) => (
                  <DriverEventCard
                    key={event.id}
                    event={event}
                    locale={locale}
                    onClickGoals={() => {
                      onOpenChange(false);
                      onEventClick(event);
                    }}
                    tActions={tActions}
                  />
                ))}
              </div>
            )}
          </div>

          {/* Quick actions — only for scheduling roles */}
          {canSchedule && (
            <>
              <Separator />
              <div>
                <p className="mb-(--spacing-tight) text-sm font-medium text-foreground">
                  {tActions("addAction")}
                </p>
                <div className="flex flex-col gap-(--spacing-tight)">
                  <ActionCard
                    icon={<Clock className="size-4" />}
                    title={tDrop("assignShift")}
                    description={tDrop("assignShiftDesc", { shift: tDrop("shiftMorning") })}
                    onClick={handleAssignShift}
                    disabled={isSaving}
                  />
                  <ActionCard
                    icon={<CalendarOff className="size-4" />}
                    title={tDrop("markLeave")}
                    description={tDrop("markLeaveDesc")}
                    onClick={handleMarkLeave}
                    disabled={isSaving}
                  />
                  <ActionCard
                    icon={<Thermometer className="size-4" />}
                    title={tDrop("markSick")}
                    description={tDrop("markSickDesc")}
                    onClick={handleMarkSick}
                    disabled={isSaving}
                  />
                  <ActionCard
                    icon={<GraduationCap className="size-4" />}
                    title={tDrop("scheduleTraining")}
                    description={tDrop("scheduleTrainingDesc")}
                    onClick={handleScheduleTraining}
                    disabled={isSaving}
                  />
                </div>
              </div>
            </>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
