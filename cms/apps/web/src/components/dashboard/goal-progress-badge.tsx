"use client";

import { cn } from "@/lib/utils";
import type { EventGoals } from "@/types/event";

export type GoalStatus = "not-started" | "in-progress" | "completed";

export function getGoalStatus(goals: EventGoals): GoalStatus {
  const total = goals.items.length;
  if (total === 0) return "not-started";
  const done = goals.items.filter((item) => item.completed).length;
  if (done === 0) return "not-started";
  if (done === total) return "completed";
  return "in-progress";
}

export function getCompletionCounts(goals: EventGoals): {
  done: number;
  total: number;
} {
  const total = goals.items.length;
  const done = goals.items.filter((item) => item.completed).length;
  return { done, total };
}

const statusStyles: Record<GoalStatus, string> = {
  "not-started": "text-foreground-muted bg-foreground/10",
  "in-progress": "text-status-delayed bg-status-delayed/15",
  completed: "text-status-ontime bg-status-ontime/15",
};

const barColors: Record<GoalStatus, string> = {
  "not-started": "bg-foreground/20",
  "in-progress": "bg-status-delayed",
  completed: "bg-status-ontime",
};

interface GoalProgressBadgeProps {
  goals: EventGoals;
  /** "compact" = fraction text only, "bar" = fraction + mini progress bar */
  variant?: "compact" | "bar";
}

export function GoalProgressBadge({
  goals,
  variant = "compact",
}: GoalProgressBadgeProps) {
  const status = getGoalStatus(goals);
  const { done, total } = getCompletionCounts(goals);

  if (total === 0) return null;

  const pct = Math.round((done / total) * 100);

  if (variant === "compact") {
    return (
      <span
        className={cn(
          "inline-flex items-center rounded-full px-1.5 py-0.5 text-[10px] font-medium",
          statusStyles[status],
        )}
      >
        {done}/{total}
      </span>
    );
  }

  return (
    <div className="flex flex-col gap-0.5">
      <span
        className={cn(
          "inline-flex items-center rounded-full px-1.5 py-0.5 text-[10px] font-medium",
          statusStyles[status],
        )}
      >
        {done}/{total}
      </span>
      <div className="h-1 w-full overflow-hidden rounded-full bg-foreground/10">
        <div
          className={cn(
            "h-full rounded-full transition-all duration-200",
            barColors[status],
          )}
          style={{ width: `${String(pct)}%` }}
        />
      </div>
    </div>
  );
}
