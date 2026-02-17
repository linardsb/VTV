"use client";

import { Bus, Zap, Train } from "lucide-react";
import { useTranslations } from "next-intl";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { ROUTE_TYPE_MAP, type RouteType } from "@/types/route";

const typeConfig = {
  bus: {
    icon: Bus,
    className: "bg-blue-600/10 text-blue-600 border-blue-600/20",
  },
  trolleybus: {
    icon: Zap,
    className: "bg-emerald-500/10 text-emerald-500 border-emerald-500/20",
  },
  tram: {
    icon: Train,
    className: "bg-purple-600/10 text-purple-600 border-purple-600/20",
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
