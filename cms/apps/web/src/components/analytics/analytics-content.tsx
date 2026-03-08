"use client";

import { Truck, Users, Clock, AlertTriangle, RefreshCw } from "lucide-react";
import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs";
import { MetricCard } from "@/components/dashboard/metric-card";
import { useAnalyticsOverview } from "@/hooks/use-analytics";
import { FleetOverview } from "./fleet-overview";
import { DriverOverview } from "./driver-overview";
import { PerformanceOverview } from "./performance-overview";

interface AnalyticsContentProps {
  locale: string;
}

function kpiDeltaType(
  value: number,
  goodThreshold: number,
  warnThreshold: number
): "positive" | "neutral" | "negative" {
  if (value >= goodThreshold) return "positive";
  if (value >= warnThreshold) return "neutral";
  return "negative";
}

export function AnalyticsContent({ locale }: AnalyticsContentProps) {
  void locale;
  const t = useTranslations("analytics");
  const { data, isLoading, error, refresh } = useAnalyticsOverview();

  if (isLoading) {
    return (
      <div className="space-y-(--spacing-section) p-(--spacing-page)">
        <h1 className="font-heading text-xl font-bold text-foreground">
          {t("title")}
        </h1>
        <div className="grid grid-cols-1 gap-(--spacing-grid) sm:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={`kpi-${i}`} className="h-24" />
          ))}
        </div>
        <Skeleton className="h-80" />
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="space-y-(--spacing-section) p-(--spacing-page)">
        <h1 className="font-heading text-xl font-bold text-foreground">
          {t("title")}
        </h1>
        <div className="border border-card-border bg-card-bg p-(--spacing-card)">
          <p className="text-sm text-foreground-muted">
            {error ?? t("error")}
          </p>
          <Button
            variant="outline"
            size="sm"
            className="mt-(--spacing-inline) cursor-pointer"
            onClick={() => void refresh()}
          >
            <RefreshCw className="mr-1 size-4" />
            {t("refresh")}
          </Button>
        </div>
      </div>
    );
  }

  const alertCount =
    data.fleet.maintenance_due_7d +
    data.fleet.registration_expiring_30d +
    data.drivers.license_expiring_30d +
    data.drivers.medical_expiring_30d;

  const trackedTrips = data.on_time.routes.reduce(
    (sum, r) => sum + r.tracked_trips,
    0
  );

  return (
    <div className="space-y-(--spacing-section) p-(--spacing-page)">
      <div className="flex items-center justify-between">
        <h1 className="font-heading text-xl font-bold text-foreground">
          {t("title")}
        </h1>
        <Button
          variant="outline"
          size="sm"
          className="cursor-pointer"
          onClick={() => void refresh()}
          aria-label={t("refresh")}
        >
          <RefreshCw className="mr-1 size-4" />
          {t("refresh")}
        </Button>
      </div>

      <div className="grid grid-cols-1 gap-(--spacing-grid) sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard
          icon={<Truck className="size-4 text-interactive" />}
          title={t("kpi.activeVehicles")}
          value={String(data.fleet.active_vehicles)}
          subtitle={t("kpi.activeVehiclesOf", {
            total: data.fleet.total_vehicles,
          })}
          accentColor="border-l-interactive"
        />
        <MetricCard
          icon={<Users className="size-4 text-status-ontime" />}
          title={t("kpi.onDutyDrivers")}
          value={String(data.drivers.on_duty_drivers)}
          subtitle={t("kpi.onDutyDriversOf", {
            total: data.drivers.total_drivers,
          })}
          accentColor="border-l-status-ontime"
        />
        <MetricCard
          icon={<Clock className="size-4 text-interactive" />}
          title={t("kpi.networkOnTime")}
          value={`${data.on_time.network_on_time_percentage}%`}
          delta={`${data.on_time.network_on_time_percentage}%`}
          deltaType={kpiDeltaType(
            data.on_time.network_on_time_percentage,
            90,
            75
          )}
          subtitle={t("kpi.networkOnTimeTrips", { count: trackedTrips })}
          accentColor="border-l-status-ontime"
        />
        <MetricCard
          icon={<AlertTriangle className="size-4 text-status-critical" />}
          title={t("kpi.urgentAlerts")}
          value={String(alertCount)}
          delta={alertCount > 0 ? String(alertCount) : "0"}
          deltaType={alertCount > 0 ? "negative" : "positive"}
          subtitle={t("kpi.urgentAlertsDesc")}
          accentColor={alertCount > 0 ? "border-l-status-critical" : "border-l-status-ontime"}
        />
      </div>

      <Tabs defaultValue="fleet">
        <TabsList>
          <TabsTrigger value="fleet" className="cursor-pointer">
            {t("tabs.fleet")}
          </TabsTrigger>
          <TabsTrigger value="drivers" className="cursor-pointer">
            {t("tabs.drivers")}
          </TabsTrigger>
          <TabsTrigger value="performance" className="cursor-pointer">
            {t("tabs.performance")}
          </TabsTrigger>
        </TabsList>
        <TabsContent value="fleet" className="mt-(--spacing-card)">
          <FleetOverview data={data.fleet} />
        </TabsContent>
        <TabsContent value="drivers" className="mt-(--spacing-card)">
          <DriverOverview data={data.drivers} />
        </TabsContent>
        <TabsContent value="performance" className="mt-(--spacing-card)">
          <PerformanceOverview data={data.on_time} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
