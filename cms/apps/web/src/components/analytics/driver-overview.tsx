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
import { AlertTriangle, Users, UserCheck, UserX } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import type { DriverSummaryResponse } from "@/types/analytics";

interface DriverOverviewProps {
  data: DriverSummaryResponse;
}

const COLORS = {
  available: "#0d9488",
  onDuty: "#2563eb",
  onLeave: "#f59e0b",
  sick: "#ef4444",
};

const STATUS_COLORS = [
  COLORS.available,
  COLORS.onDuty,
  COLORS.onLeave,
  COLORS.sick,
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
    available: item.available,
    onDuty: item.on_duty,
    onLeave: item.on_leave,
    sick: item.sick,
  }));

  const donutData = [
    { name: t("available"), value: data.available_drivers },
    { name: t("onDuty"), value: data.on_duty_drivers },
    { name: t("onLeave"), value: data.on_leave_drivers },
    { name: t("sick"), value: data.sick_drivers },
  ];

  const availabilityPct =
    data.total_drivers > 0
      ? Math.round(
          ((data.available_drivers + data.on_duty_drivers) /
            data.total_drivers) *
            100
        )
      : 0;

  return (
    <div className="space-y-(--spacing-section)">
      {/* Summary stat cards — compact */}
      <div className="grid grid-cols-2 gap-(--spacing-grid) lg:grid-cols-4">
        <div className="border-l-4 border-l-status-ontime border border-card-border bg-card-bg px-3 py-2">
          <div className="flex items-center justify-between">
            <span className="text-xs text-foreground-muted">
              {t("available")}
            </span>
            <UserCheck className="size-3.5 text-status-ontime" />
          </div>
          <p className="font-heading text-lg font-bold text-status-ontime leading-tight">
            {data.available_drivers}
          </p>
        </div>
        <div className="border-l-4 border-l-interactive border border-card-border bg-card-bg px-3 py-2">
          <div className="flex items-center justify-between">
            <span className="text-xs text-foreground-muted">{t("onDuty")}</span>
            <Users className="size-3.5 text-interactive" />
          </div>
          <p className="font-heading text-lg font-bold text-interactive leading-tight">
            {data.on_duty_drivers}
          </p>
        </div>
        <div className="border-l-4 border-l-status-delayed border border-card-border bg-card-bg px-3 py-2">
          <span className="text-xs text-foreground-muted">{t("onLeave")}</span>
          <p className="font-heading text-lg font-bold text-foreground leading-tight">
            {data.on_leave_drivers}
          </p>
        </div>
        <div className="border-l-4 border-l-status-critical border border-card-border bg-card-bg px-3 py-2">
          <div className="flex items-center justify-between">
            <span className="text-xs text-foreground-muted">{t("sick")}</span>
            <UserX className="size-3.5 text-status-critical" />
          </div>
          <p className="font-heading text-lg font-bold text-foreground leading-tight">
            {data.sick_drivers}
          </p>
        </div>
      </div>

      {/* Availability bar */}
      <div className="border border-card-border bg-card-bg p-(--spacing-card)">
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm font-medium text-foreground">
            {t("staffAvailability")}
          </span>
          <span className="font-heading text-lg font-bold text-status-ontime">
            {availabilityPct}%
          </span>
        </div>
        <div className="h-3 w-full bg-surface overflow-hidden">
          <div className="flex h-full">
            <div
              className="h-full transition-all duration-300"
              style={{
                width: `${data.total_drivers > 0 ? (data.available_drivers / data.total_drivers) * 100 : 0}%`,
                backgroundColor: COLORS.available,
              }}
            />
            <div
              className="h-full transition-all duration-300"
              style={{
                width: `${data.total_drivers > 0 ? (data.on_duty_drivers / data.total_drivers) * 100 : 0}%`,
                backgroundColor: COLORS.onDuty,
              }}
            />
            <div
              className="h-full transition-all duration-300"
              style={{
                width: `${data.total_drivers > 0 ? (data.on_leave_drivers / data.total_drivers) * 100 : 0}%`,
                backgroundColor: COLORS.onLeave,
              }}
            />
            <div
              className="h-full transition-all duration-300"
              style={{
                width: `${data.total_drivers > 0 ? (data.sick_drivers / data.total_drivers) * 100 : 0}%`,
                backgroundColor: COLORS.sick,
              }}
            />
          </div>
        </div>
        <div className="flex flex-wrap gap-(--spacing-grid) mt-2 text-xs text-foreground-muted">
          <span className="flex items-center gap-1">
            <span
              className="inline-block size-2.5"
              style={{ backgroundColor: COLORS.available }}
            />
            {t("available")}
          </span>
          <span className="flex items-center gap-1">
            <span
              className="inline-block size-2.5"
              style={{ backgroundColor: COLORS.onDuty }}
            />
            {t("onDuty")}
          </span>
          <span className="flex items-center gap-1">
            <span
              className="inline-block size-2.5"
              style={{ backgroundColor: COLORS.onLeave }}
            />
            {t("onLeave")}
          </span>
          <span className="flex items-center gap-1">
            <span
              className="inline-block size-2.5"
              style={{ backgroundColor: COLORS.sick }}
            />
            {t("sick")}
          </span>
        </div>
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 gap-(--spacing-grid) lg:grid-cols-2">
        <div className="border border-card-border bg-card-bg p-(--spacing-card)">
          <h3 className="mb-(--spacing-card) font-heading text-sm font-semibold text-foreground">
            {t("byShift")}
          </h3>
          <ResponsiveContainer width="100%" height={288}>
            <BarChart data={barData} aria-label={t("byShift")}>
              <XAxis
                dataKey="shift"
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
                dataKey="available"
                name={t("available")}
                stackId="a"
                fill={COLORS.available}
              />
              <Bar
                dataKey="onDuty"
                name={t("onDuty")}
                stackId="a"
                fill={COLORS.onDuty}
              />
              <Bar
                dataKey="onLeave"
                name={t("onLeave")}
                stackId="a"
                fill={COLORS.onLeave}
              />
              <Bar
                dataKey="sick"
                name={t("sick")}
                stackId="a"
                fill={COLORS.sick}
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
                    fill={STATUS_COLORS[index % STATUS_COLORS.length]}
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
                {data.total_drivers}
              </text>
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Alerts */}
      {(data.license_expiring_30d > 0 || data.medical_expiring_30d > 0) && (
        <div className="border border-status-critical/30 bg-status-critical/5 p-(--spacing-card)">
          <div className="flex items-center gap-(--spacing-inline) mb-(--spacing-inline)">
            <AlertTriangle className="size-4 text-status-critical" />
            <h3 className="font-heading text-sm font-semibold text-foreground">
              {t("alerts")}
            </h3>
          </div>
          <div className="flex flex-wrap gap-(--spacing-inline)">
            {data.license_expiring_30d > 0 && (
              <Badge className="bg-status-delayed/15 text-status-delayed rounded-none border-0">
                {data.license_expiring_30d} — {t("licenseExpiring")}
              </Badge>
            )}
            {data.medical_expiring_30d > 0 && (
              <Badge className="bg-status-critical/15 text-status-critical rounded-none border-0">
                {data.medical_expiring_30d} — {t("medicalExpiring")}
              </Badge>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
