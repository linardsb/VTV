"use client";

import { Bus, Clock, AlertTriangle, MapPin } from "lucide-react";
import { useTranslations } from "next-intl";
import { useDashboardMetrics } from "@/hooks/use-dashboard-metrics";
import { MetricCard } from "./metric-card";
import { Skeleton } from "@/components/ui/skeleton";

export function DashboardMetrics() {
  const { data, isLoading } = useDashboardMetrics();
  const t = useTranslations("dashboard");

  if (isLoading) {
    return (
      <div className="grid grid-cols-1 gap-(--spacing-grid) sm:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={`skeleton-${String(i)}`} className="h-24 rounded-lg" />
        ))}
      </div>
    );
  }

  if (!data) {
    return (
      <div className="grid grid-cols-1 gap-(--spacing-grid) sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard
          icon={<Bus className="size-5 text-foreground-muted" aria-hidden="true" />}
          title={t("metrics.activeVehicles")}
          value="—"
          subtitle={t("metrics.unavailable")}
        />
        <MetricCard
          icon={<Clock className="size-5 text-foreground-muted" aria-hidden="true" />}
          title={t("metrics.onTimePerformance")}
          value="—"
          subtitle={t("metrics.unavailable")}
        />
        <MetricCard
          icon={<AlertTriangle className="size-5 text-foreground-muted" aria-hidden="true" />}
          title={t("metrics.delayedRoutes")}
          value="—"
          subtitle={t("metrics.unavailable")}
        />
        <MetricCard
          icon={<MapPin className="size-5 text-foreground-muted" aria-hidden="true" />}
          title={t("metrics.activeRoutes")}
          value="—"
          subtitle={t("metrics.unavailable")}
        />
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 gap-(--spacing-grid) sm:grid-cols-2 lg:grid-cols-4">
      <MetricCard
        icon={<Bus className="size-5 text-foreground-muted" aria-hidden="true" />}
        title={t("metrics.activeVehicles")}
        value={String(data.activeVehicles)}
        subtitle={t("metrics.onRoutes", { count: data.distinctRouteCount })}
      />
      <MetricCard
        icon={<Clock className="size-5 text-foreground-muted" aria-hidden="true" />}
        title={t("metrics.onTimePerformance")}
        value={`${String(data.onTimePercentage)}%`}
        subtitle={t("metrics.vehiclesOnTime", {
          count: data.onTimeCount,
          total: data.totalVehicles,
        })}
      />
      <MetricCard
        icon={<AlertTriangle className="size-5 text-foreground-muted" aria-hidden="true" />}
        title={t("metrics.delayedRoutes")}
        value={String(data.delayedRoutes)}
        subtitle={t("metrics.ofTotalRoutes", {
          total: data.distinctRouteCount,
        })}
      />
      <MetricCard
        icon={<MapPin className="size-5 text-foreground-muted" aria-hidden="true" />}
        title={t("metrics.activeRoutes")}
        value={String(data.activeRoutes)}
        subtitle={t("metrics.totalInSystem", { total: data.totalRoutes })}
      />
    </div>
  );
}
