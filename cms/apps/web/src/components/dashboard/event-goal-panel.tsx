"use client";

import { useState, useCallback } from "react";
import { useTranslations } from "next-intl";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import type { CalendarEvent } from "@/types/dashboard";
import type { EventGoals, GoalItem } from "@/types/event";
import { updateEvent } from "@/lib/events-sdk";
import type { GoalStatus } from "./goal-progress-badge";
import { Checkbox } from "@/components/ui/checkbox";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";

function formatTime(date: Date): string {
  return date.toLocaleTimeString(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

const statusTextStyles: Record<GoalStatus, string> = {
  "not-started": "text-foreground-muted",
  "in-progress": "text-status-delayed",
  completed: "text-status-ontime",
};

const barColorStyles: Record<GoalStatus, string> = {
  "not-started": "bg-foreground/20",
  "in-progress": "bg-status-delayed",
  completed: "bg-status-ontime",
};

function GoalItemRow({
  item,
  index,
  onToggle,
}: {
  item: GoalItem;
  index: number;
  onToggle: (index: number) => void;
}) {
  return (
    <label className="flex cursor-pointer items-center gap-(--spacing-inline) py-(--spacing-tight)">
      <Checkbox
        checked={item.completed}
        onCheckedChange={() => onToggle(index)}
      />
      <span
        className={cn(
          "text-sm",
          item.completed
            ? "text-foreground-muted line-through"
            : "text-foreground",
        )}
      >
        {item.text}
      </span>
    </label>
  );
}

interface EventGoalPanelProps {
  event: CalendarEvent | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onGoalsUpdated: () => void;
}

export function EventGoalPanel({
  event,
  open,
  onOpenChange,
  onGoalsUpdated,
}: EventGoalPanelProps) {
  const t = useTranslations("dashboard.goals");

  const [goalItems, setGoalItems] = useState<GoalItem[]>(
    event?.goals?.items ?? [],
  );
  const [isSaving, setIsSaving] = useState(false);

  const hasGoals = goalItems.length > 0;
  const localDone = goalItems.filter((item) => item.completed).length;
  const localTotal = goalItems.length;
  const pct =
    localTotal > 0 ? Math.round((localDone / localTotal) * 100) : 0;
  const status: GoalStatus =
    localTotal === 0
      ? "not-started"
      : localDone === 0
        ? "not-started"
        : localDone === localTotal
          ? "completed"
          : "in-progress";
  const statusTextClass = statusTextStyles[status];
  const barColorClass = barColorStyles[status];

  const handleToggle = useCallback((index: number) => {
    setGoalItems((prev) =>
      prev.map((item, i) =>
        i === index ? { ...item, completed: !item.completed } : item,
      ),
    );
  }, []);

  const handleSave = useCallback(async () => {
    if (!event?.goals) return;
    setIsSaving(true);
    try {
      const updatedGoals: EventGoals = {
        ...event.goals,
        items: goalItems,
      };
      await updateEvent(Number(event.id), { goals: updatedGoals });
      toast.success(t("updateSuccess"));
      onGoalsUpdated();
      onOpenChange(false);
    } catch {
      toast.error(t("updateError"));
    } finally {
      setIsSaving(false);
    }
  }, [event, goalItems, t, onGoalsUpdated, onOpenChange]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[32rem]">
        <DialogHeader>
          <DialogTitle>{t("eventDetail")}</DialogTitle>
          <DialogDescription className="sr-only">
            {event?.title ?? ""}
          </DialogDescription>
        </DialogHeader>

        {event && (
          <div className="flex flex-col gap-(--spacing-grid)">
            {/* Event info */}
            <div>
              <p className="text-sm font-medium text-foreground">
                {event.title}
              </p>
              <p className="text-xs text-foreground-muted">
                {event.start.toLocaleDateString()} ·{" "}
                {formatTime(event.start)} – {formatTime(event.end)}
              </p>
              {event.description && (
                <p className="mt-(--spacing-tight) text-xs text-foreground-muted">
                  {event.description}
                </p>
              )}
            </div>

            {/* Goal progress summary */}
            {hasGoals && (
              <>
                <Separator />
                <div>
                  <div className="mb-(--spacing-tight) flex items-center justify-between">
                    <p className="text-sm font-medium text-foreground">
                      {t("goalProgress")}
                    </p>
                    <span
                      className={cn("text-xs font-medium", statusTextClass)}
                    >
                      {t("progress", {
                        done: localDone,
                        total: localTotal,
                      })}
                    </span>
                  </div>

                  {/* Progress bar */}
                  <div className="h-2 w-full overflow-hidden rounded-full bg-foreground/10">
                    <div
                      className={cn(
                        "h-full rounded-full transition-all duration-200",
                        barColorClass,
                      )}
                      style={{ width: `${String(pct)}%` }}
                    />
                  </div>
                </div>

                {/* Goal checklist */}
                <div className="flex flex-col">
                  {goalItems.map((item, index) => (
                    <GoalItemRow
                      key={`goal-${String(index)}`}
                      item={item}
                      index={index}
                      onToggle={handleToggle}
                    />
                  ))}
                </div>

                {/* Transport/route info if present */}
                {(event.goals?.transport_type ||
                  event.goals?.vehicle_id) && (
                  <div className="flex flex-wrap gap-(--spacing-tight) text-xs text-foreground-muted">
                    {event.goals.transport_type && (
                      <span className="rounded-full bg-foreground/10 px-2 py-0.5">
                        {event.goals.transport_type}
                      </span>
                    )}
                    {event.goals.vehicle_id && (
                      <span className="rounded-full bg-foreground/10 px-2 py-0.5">
                        {event.goals.vehicle_id}
                      </span>
                    )}
                  </div>
                )}
              </>
            )}

            {/* No goals fallback */}
            {!hasGoals && (
              <p className="py-4 text-center text-sm text-foreground-muted">
                {t("noGoals")}
              </p>
            )}

            {/* Actions */}
            <div className="flex justify-end gap-(--spacing-inline)">
              {hasGoals ? (
                <Button
                  size="sm"
                  onClick={handleSave}
                  disabled={isSaving}
                  className="cursor-pointer"
                >
                  {isSaving ? t("saving") : t("save")}
                </Button>
              ) : (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => onOpenChange(false)}
                  className="cursor-pointer"
                >
                  {t("close")}
                </Button>
              )}
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
