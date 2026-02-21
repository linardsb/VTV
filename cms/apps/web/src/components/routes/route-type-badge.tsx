"use client";

import { Bus, Zap, Train, Ship, Cable, Mountain } from "lucide-react";
import { useTranslations } from "next-intl";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { getRouteTypeLabel } from "@/types/route";

const typeConfig: Record<
  string,
  { icon: typeof Bus; className: string }
> = {
  bus: {
    icon: Bus,
    className: "bg-transport-bus/10 text-transport-bus border-transport-bus/20",
  },
  trolleybus: {
    icon: Zap,
    className: "bg-transport-trolleybus/10 text-transport-trolleybus border-transport-trolleybus/20",
  },
  tram: {
    icon: Train,
    className: "bg-transport-tram/10 text-transport-tram border-transport-tram/20",
  },
  subway: {
    icon: Train,
    className: "bg-primary/10 text-primary border-primary/20",
  },
  rail: {
    icon: Train,
    className: "bg-primary/10 text-primary border-primary/20",
  },
  ferry: {
    icon: Ship,
    className: "bg-info/10 text-info border-info/20",
  },
  cableTram: {
    icon: Cable,
    className: "bg-primary/10 text-primary border-primary/20",
  },
  gondola: {
    icon: Cable,
    className: "bg-primary/10 text-primary border-primary/20",
  },
  funicular: {
    icon: Mountain,
    className: "bg-primary/10 text-primary border-primary/20",
  },
  monorail: {
    icon: Train,
    className: "bg-primary/10 text-primary border-primary/20",
  },
  other: {
    icon: Bus,
    className: "bg-muted text-foreground-muted border-border",
  },
};

interface RouteTypeBadgeProps {
  type: number;
  className?: string;
}

export function RouteTypeBadge({ type, className }: RouteTypeBadgeProps) {
  const t = useTranslations("routes.filters");
  const label = getRouteTypeLabel(type);
  const config = typeConfig[label] ?? typeConfig.other;
  const Icon = config.icon;

  return (
    <Badge
      variant="outline"
      className={cn(
        "gap-(--spacing-tight) font-medium",
        config.className,
        className
      )}
    >
      <Icon className="size-3" aria-hidden="true" />
      {t(label)}
    </Badge>
  );
}
