"use client";

import { useTranslations } from "next-intl";
import { BarChart, DonutChart } from "@tremor/react";
import { Badge } from "@/components/ui/badge";
import type { DriverSummaryResponse } from "@/types/analytics";

interface DriverOverviewProps {
  data: DriverSummaryResponse;
}

const STATUS_COLORS = [
  "var(--color-status-ontime)",
  "var(--color-interactive)",
  "var(--color-status-delayed)",
  "var(--color-status-critical)",
];

export function DriverOverview({ data }: DriverOverviewProps) {
  const t = useTranslations("analytics.drivers");

  const shiftLabels: Record<string, string> = {
    morning: t("morning"),
    afternoon: t("afternoon"),
    evening: t("evening"),
    night: t("night"),
  };

  const barData = data.by_shift.map((item) => ({
    shift: shiftLabels[item.shift] ?? item.shift,
    [t("available")]: item.available,
    [t("onDuty")]: item.on_duty,
    [t("onLeave")]: item.on_leave,
    [t("sick")]: item.sick,
  }));

  const donutData = [
    { name: t("available"), value: data.available_drivers },
    { name: t("onDuty"), value: data.on_duty_drivers },
    { name: t("onLeave"), value: data.on_leave_drivers },
    { name: t("sick"), value: data.sick_drivers },
  ];

  return (
    <div className="space-y-(--spacing-section)">
      <div className="grid grid-cols-1 gap-(--spacing-grid) lg:grid-cols-2">
        <div className="border border-card-border bg-card-bg p-(--spacing-card)">
          <h3 className="mb-(--spacing-card) font-heading text-sm font-semibold text-foreground">
            {t("byShift")}
          </h3>
          <BarChart
            data={barData}
            index="shift"
            categories={[t("available"), t("onDuty"), t("onLeave"), t("sick")]}
            colors={STATUS_COLORS}
            stack
            className="h-64"
            showLegend
            showGridLines={false}
            aria-label={t("byShift")}
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
            label={String(data.total_drivers)}
            showLabel
            className="h-64"
            aria-label={t("byStatus")}
          />
        </div>
      </div>

      {(data.license_expiring_30d > 0 || data.medical_expiring_30d > 0) && (
        <div className="space-y-(--spacing-inline)">
          <h3 className="font-heading text-sm font-semibold text-foreground">
            {t("alerts")}
          </h3>
          <div className="flex flex-wrap gap-(--spacing-inline)">
            {data.license_expiring_30d > 0 && (
              <Badge className="bg-status-delayed/10 text-status-delayed rounded-none border-0">
                {data.license_expiring_30d} — {t("licenseExpiring")}
              </Badge>
            )}
            {data.medical_expiring_30d > 0 && (
              <Badge className="bg-status-critical/10 text-status-critical rounded-none border-0">
                {data.medical_expiring_30d} — {t("medicalExpiring")}
              </Badge>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
