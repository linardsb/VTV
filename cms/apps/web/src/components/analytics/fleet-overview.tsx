"use client";

import { useTranslations } from "next-intl";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
} from "recharts";
import { AlertTriangle, Truck, Wrench } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import type { FleetSummaryResponse } from "@/types/analytics";

interface FleetOverviewProps {
  data: FleetSummaryResponse;
}

const COLORS = {
  active: "#4ead8a",
  inactive: "#94a3b8",
  maintenance: "#f59e0b",
};

const DONUT_COLORS = [COLORS.active, COLORS.inactive, COLORS.maintenance];

export function FleetOverview({ data }: FleetOverviewProps) {
  const t = useTranslations("analytics.fleet");

  const typeLabels: Record<string, string> = {
    bus: t("bus"),
    trolleybus: t("trolleybus"),
    tram: t("tram"),
  };

  const barData = data.by_type.map((item) => ({
    type: typeLabels[item.vehicle_type] ?? item.vehicle_type,
    active: item.active,
    inactive: item.inactive,
    maintenance: item.in_maintenance,
  }));

  const donutData = [
    { name: t("active"), value: data.active_vehicles },
    { name: t("inactive"), value: data.inactive_vehicles },
    { name: t("maintenance"), value: data.in_maintenance },
  ];

  const utilizationPct =
    data.total_vehicles > 0
      ? Math.round((data.active_vehicles / data.total_vehicles) * 100)
      : 0;

  return (
    <div className="space-y-(--spacing-section)">
      {/* Summary stat cards — compact */}
      <div className="grid grid-cols-2 gap-(--spacing-grid) lg:grid-cols-4">
        <div className="border-l-4 border-l-interactive border border-card-border bg-card-bg px-3 py-2">
          <div className="flex items-center justify-between">
            <span className="text-xs text-foreground-muted">{t("active")}</span>
            <Truck className="size-3.5 text-interactive" />
          </div>
          <p className="font-heading text-lg font-bold text-foreground leading-tight">
            {data.active_vehicles}
            <span className="text-xs font-normal text-foreground-muted">
              {" "}
              / {data.total_vehicles}
            </span>
          </p>
        </div>
        <div className="border-l-4 border-l-foreground-muted border border-card-border bg-card-bg px-3 py-2">
          <span className="text-xs text-foreground-muted">{t("inactive")}</span>
          <p className="font-heading text-lg font-bold text-foreground leading-tight">
            {data.inactive_vehicles}
            <span className="text-xs font-normal text-foreground-muted">
              {" "}
              ({t("unassigned")}: {data.unassigned_vehicles})
            </span>
          </p>
        </div>
        <div className="border-l-4 border-l-status-delayed border border-card-border bg-card-bg px-3 py-2">
          <div className="flex items-center justify-between">
            <span className="text-xs text-foreground-muted">
              {t("maintenance")}
            </span>
            <Wrench className="size-3.5 text-status-delayed" />
          </div>
          <p className="font-heading text-lg font-bold text-foreground leading-tight">
            {data.in_maintenance}
          </p>
        </div>
        <div className="border-l-4 border-l-status-ontime border border-card-border bg-card-bg px-3 py-2">
          <span className="text-xs text-foreground-muted">
            {t("utilization")}
          </span>
          <p className="font-heading text-lg font-bold text-status-ontime leading-tight">
            {utilizationPct}%
          </p>
          <div className="mt-1 h-1.5 w-full bg-surface">
            <div
              className="h-full bg-status-ontime transition-all duration-300"
              style={{ width: `${utilizationPct}%` }}
            />
          </div>
        </div>
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 gap-(--spacing-grid) lg:grid-cols-2">
        <div className="border border-card-border bg-card-bg p-(--spacing-card)">
          <h3 className="mb-(--spacing-card) font-heading text-sm font-semibold text-foreground">
            {t("byType")}
          </h3>
          <ResponsiveContainer width="100%" height={288}>
            <BarChart data={barData} aria-label={t("byType")}>
              <XAxis
                dataKey="type"
                tick={{ fontSize: 12 }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                tick={{ fontSize: 12 }}
                axisLine={false}
                tickLine={false}
                width={40}
              />
              <Tooltip
                contentStyle={{
                  borderRadius: 0,
                  border: "1px solid #e2e8f0",
                  fontSize: 12,
                }}
              />
              <Legend
                iconType="square"
                iconSize={10}
                wrapperStyle={{ fontSize: 12 }}
              />
              <Bar
                dataKey="active"
                name={t("active")}
                stackId="a"
                fill={COLORS.active}
              />
              <Bar
                dataKey="inactive"
                name={t("inactive")}
                stackId="a"
                fill={COLORS.inactive}
              />
              <Bar
                dataKey="maintenance"
                name={t("maintenance")}
                stackId="a"
                fill={COLORS.maintenance}
              />
            </BarChart>
          </ResponsiveContainer>
        </div>
        <div className="border border-card-border bg-card-bg p-(--spacing-card)">
          <h3 className="mb-(--spacing-card) font-heading text-sm font-semibold text-foreground">
            {t("byStatus")}
          </h3>
          <ResponsiveContainer width="100%" height={288}>
            <PieChart>
              <Pie
                data={donutData}
                dataKey="value"
                nameKey="name"
                cx="50%"
                cy="50%"
                innerRadius="60%"
                outerRadius="85%"
                paddingAngle={2}
                aria-label={t("byStatus")}
              >
                {donutData.map((entry, index) => (
                  <Cell
                    key={entry.name}
                    fill={DONUT_COLORS[index % DONUT_COLORS.length]}
                  />
                ))}
              </Pie>
              <Tooltip
                contentStyle={{
                  borderRadius: 0,
                  border: "1px solid #e2e8f0",
                  fontSize: 12,
                }}
              />
              <Legend
                iconType="circle"
                iconSize={10}
                wrapperStyle={{ fontSize: 12 }}
              />
              <text
                x="50%"
                y="50%"
                textAnchor="middle"
                dominantBaseline="middle"
                className="font-heading text-2xl font-bold"
                fill="currentColor"
              >
                {data.total_vehicles}
              </text>
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Alerts */}
      {(data.maintenance_due_7d > 0 || data.registration_expiring_30d > 0) && (
        <div className="border border-status-delayed/30 bg-status-delayed/5 p-(--spacing-card)">
          <div className="flex items-center gap-(--spacing-inline) mb-(--spacing-inline)">
            <AlertTriangle className="size-4 text-status-delayed" />
            <h3 className="font-heading text-sm font-semibold text-foreground">
              {t("alerts")}
            </h3>
          </div>
          <div className="flex flex-wrap gap-(--spacing-inline)">
            {data.maintenance_due_7d > 0 && (
              <Badge className="bg-status-delayed/15 text-status-delayed rounded-none border-0">
                {data.maintenance_due_7d} — {t("maintenanceDue")}
              </Badge>
            )}
            {data.registration_expiring_30d > 0 && (
              <Badge className="bg-status-critical/15 text-status-critical rounded-none border-0">
                {data.registration_expiring_30d} — {t("registrationExpiring")}
              </Badge>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
