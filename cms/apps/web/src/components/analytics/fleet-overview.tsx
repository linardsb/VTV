"use client";

import { useTranslations } from "next-intl";
import { BarChart, DonutChart } from "@tremor/react";
import { Badge } from "@/components/ui/badge";
import type { FleetSummaryResponse } from "@/types/analytics";

interface FleetOverviewProps {
  data: FleetSummaryResponse;
}

const STATUS_COLORS = [
  "var(--color-status-ontime)",
  "var(--color-foreground-muted)",
  "var(--color-status-delayed)",
];

const TYPE_COLORS = [
  "var(--color-transport-bus)",
  "var(--color-transport-trolleybus)",
  "var(--color-transport-tram)",
];

export function FleetOverview({ data }: FleetOverviewProps) {
  const t = useTranslations("analytics.fleet");

  const typeLabels: Record<string, string> = {
    bus: t("bus"),
    trolleybus: t("trolleybus"),
    tram: t("tram"),
  };

  const barData = data.by_type.map((item) => ({
    type: typeLabels[item.vehicle_type] ?? item.vehicle_type,
    [t("active")]: item.active,
    [t("inactive")]: item.inactive,
    [t("maintenance")]: item.in_maintenance,
  }));

  const donutData = [
    { name: t("active"), value: data.active_vehicles },
    { name: t("inactive"), value: data.inactive_vehicles },
    { name: t("maintenance"), value: data.in_maintenance },
  ];

  return (
    <div className="space-y-(--spacing-section)">
      <div className="grid grid-cols-1 gap-(--spacing-grid) lg:grid-cols-2">
        <div className="border border-card-border bg-card-bg p-(--spacing-card)">
          <h3 className="mb-(--spacing-card) font-heading text-sm font-semibold text-foreground">
            {t("byType")}
          </h3>
          <BarChart
            data={barData}
            index="type"
            categories={[t("active"), t("inactive"), t("maintenance")]}
            colors={TYPE_COLORS}
            stack
            className="h-64"
            showLegend
            showGridLines={false}
            aria-label={t("byType")}
          />
        </div>
        <div className="border border-card-border bg-card-bg p-(--spacing-card)">
          <h3 className="mb-(--spacing-card) font-heading text-sm font-semibold text-foreground">
            {t("byStatus")}
          </h3>
          <DonutChart
            data={donutData}
            index="name"
            category="value"
            colors={STATUS_COLORS}
            label={String(data.total_vehicles)}
            showLabel
            className="h-64"
            aria-label={t("byStatus")}
          />
        </div>
      </div>

      <div className="flex flex-wrap gap-(--spacing-grid)">
        <div className="border border-card-border bg-card-bg p-(--spacing-card)">
          <p className="text-sm text-foreground-muted">{t("unassigned")}</p>
          <p className="font-heading text-lg font-semibold text-foreground">
            {data.unassigned_vehicles}
          </p>
        </div>
        <div className="border border-card-border bg-card-bg p-(--spacing-card)">
          <p className="text-sm text-foreground-muted">{t("avgMileage")}</p>
          <p className="font-heading text-lg font-semibold text-foreground">
            {Math.round(data.average_mileage_km).toLocaleString()} km
          </p>
        </div>
      </div>

      {(data.maintenance_due_7d > 0 || data.registration_expiring_30d > 0) && (
        <div className="space-y-(--spacing-inline)">
          <h3 className="font-heading text-sm font-semibold text-foreground">
            {t("alerts")}
          </h3>
          <div className="flex flex-wrap gap-(--spacing-inline)">
            {data.maintenance_due_7d > 0 && (
              <Badge className="bg-status-delayed/10 text-status-delayed rounded-none border-0">
                {data.maintenance_due_7d} — {t("maintenanceDue")}
              </Badge>
            )}
            {data.registration_expiring_30d > 0 && (
              <Badge className="bg-status-critical/10 text-status-critical rounded-none border-0">
                {data.registration_expiring_30d} — {t("registrationExpiring")}
              </Badge>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
