"use client";

import { Bus, Zap, Train } from "lucide-react";
import { useTranslations } from "next-intl";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { ROUTE_TYPE_MAP, type RouteType } from "@/types/route";

const typeConfig = {
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
} as const;

interface RouteTypeBadgeProps {
  type: RouteType;
  className?: string;
}

export function RouteTypeBadge({ type, className }: RouteTypeBadgeProps) {
  const t = useTranslations("routes.filters");
  const label = ROUTE_TYPE_MAP[type];
  const config = typeConfig[label];
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
