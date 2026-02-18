"use client";

import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

interface MetricCardProps {
  icon: ReactNode;
  title: string;
  value: string;
  delta: string;
  deltaType: "positive" | "negative" | "neutral";
  subtitle: string;
}

const deltaStyles = {
  positive: "bg-status-ontime/10 text-status-ontime",
  negative: "bg-status-critical/10 text-status-critical",
  neutral: "bg-border text-foreground-muted",
} as const;

export function MetricCard({
  icon,
  title,
  value,
  delta,
  deltaType,
  subtitle,
}: MetricCardProps) {
  return (
    <div className="rounded-lg border border-border bg-surface-raised p-(--spacing-card) transition-shadow duration-200 hover:shadow-md">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-(--spacing-inline)">
          {icon}
          <span className="text-sm text-foreground-muted">{title}</span>
        </div>
        <span
          className={cn(
            "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium",
            deltaStyles[deltaType]
          )}
        >
          {delta}
        </span>
      </div>
      <p className="mt-(--spacing-inline) font-heading text-heading font-semibold text-foreground">
        {value}
      </p>
      <p className="mt-(--spacing-tight) text-xs text-foreground-muted">{subtitle}</p>
    </div>
  );
}
