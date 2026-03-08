"use client";

import { useMemo } from "react";
import { useTranslations } from "next-intl";
import {
  LineChart,
  Line,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { Skeleton } from "@/components/ui/skeleton";
import type { TelemetryHistoryPoint } from "@/types/fleet";

interface TelemetryDashboardProps {
  data: TelemetryHistoryPoint[];
  isLoading: boolean;
}

interface ChartCardProps {
  title: string;
  currentValue: string;
  children: React.ReactNode;
}

function ChartCard({ title, currentValue, children }: ChartCardProps) {
  return (
    <div className="border border-border p-(--spacing-card)">
      <div className="flex items-start justify-between mb-(--spacing-card)">
        <p className="text-xs font-medium text-foreground-muted uppercase tracking-wide">
          {title}
        </p>
        <p className="text-lg font-heading font-semibold text-foreground">
          {currentValue}
        </p>
      </div>
      <div className="h-[180px]">{children}</div>
    </div>
  );
}

function formatTime(timestamp: string): string {
  return new Date(timestamp).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function TelemetryDashboard({
  data,
  isLoading,
}: TelemetryDashboardProps) {
  const t = useTranslations("fleet.telemetry");

  const chartData = useMemo(
    () =>
      data.map((point) => ({
        time: formatTime(point.recorded_at),
        speed: point.obd_data?.speed_kmh ?? null,
        rpm: point.obd_data?.rpm ?? null,
        fuel: point.obd_data?.fuel_level_pct ?? null,
        coolant: point.obd_data?.coolant_temp_c ?? null,
        engineLoad: point.obd_data?.engine_load_pct ?? null,
        battery: point.obd_data?.battery_voltage ?? null,
      })),
    [data],
  );

  const latest = chartData.length > 0 ? chartData[chartData.length - 1] : null;

  if (isLoading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 gap-(--spacing-card)">
        {Array.from({ length: 6 }).map((_, i) => (
          <Skeleton key={`chart-skel-${i}`} className="h-[260px] w-full" />
        ))}
      </div>
    );
  }

  if (data.length === 0) {
    return (
      <div className="flex items-center justify-center p-(--spacing-page)">
        <p className="text-sm text-foreground-muted">{t("noData")}</p>
      </div>
    );
  }

  const lineColor = "var(--color-interactive)";
  const gridColor = "var(--color-border)";

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-(--spacing-card)">
      {/* Speed */}
      <ChartCard
        title={t("speed")}
        currentValue={latest?.speed !== null ? `${latest?.speed}` : "-"}
      >
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke={gridColor} />
            <XAxis dataKey="time" tick={{ fontSize: 10 }} stroke={gridColor} />
            <YAxis tick={{ fontSize: 10 }} stroke={gridColor} />
            <Tooltip />
            <Line
              type="monotone"
              dataKey="speed"
              stroke={lineColor}
              strokeWidth={2}
              dot={false}
              connectNulls
            />
          </LineChart>
        </ResponsiveContainer>
      </ChartCard>

      {/* RPM */}
      <ChartCard
        title={t("rpm")}
        currentValue={latest?.rpm !== null ? `${latest?.rpm}` : "-"}
      >
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke={gridColor} />
            <XAxis dataKey="time" tick={{ fontSize: 10 }} stroke={gridColor} />
            <YAxis tick={{ fontSize: 10 }} stroke={gridColor} />
            <Tooltip />
            <Line
              type="monotone"
              dataKey="rpm"
              stroke={lineColor}
              strokeWidth={2}
              dot={false}
              connectNulls
            />
          </LineChart>
        </ResponsiveContainer>
      </ChartCard>

      {/* Fuel Level */}
      <ChartCard
        title={t("fuelLevel")}
        currentValue={latest?.fuel !== null ? `${latest?.fuel}%` : "-"}
      >
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke={gridColor} />
            <XAxis dataKey="time" tick={{ fontSize: 10 }} stroke={gridColor} />
            <YAxis tick={{ fontSize: 10 }} stroke={gridColor} domain={[0, 100]} />
            <Tooltip />
            <Area
              type="monotone"
              dataKey="fuel"
              stroke={lineColor}
              fill={lineColor}
              fillOpacity={0.1}
              strokeWidth={2}
              connectNulls
            />
          </AreaChart>
        </ResponsiveContainer>
      </ChartCard>

      {/* Coolant Temperature */}
      <ChartCard
        title={t("coolantTemp")}
        currentValue={latest?.coolant !== null ? `${latest?.coolant}\u00b0C` : "-"}
      >
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke={gridColor} />
            <XAxis dataKey="time" tick={{ fontSize: 10 }} stroke={gridColor} />
            <YAxis tick={{ fontSize: 10 }} stroke={gridColor} />
            <Tooltip />
            <Line
              type="monotone"
              dataKey="coolant"
              stroke={lineColor}
              strokeWidth={2}
              dot={false}
              connectNulls
            />
          </LineChart>
        </ResponsiveContainer>
      </ChartCard>

      {/* Engine Load */}
      <ChartCard
        title={t("engineLoad")}
        currentValue={latest?.engineLoad !== null ? `${latest?.engineLoad}%` : "-"}
      >
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke={gridColor} />
            <XAxis dataKey="time" tick={{ fontSize: 10 }} stroke={gridColor} />
            <YAxis tick={{ fontSize: 10 }} stroke={gridColor} domain={[0, 100]} />
            <Tooltip />
            <Area
              type="monotone"
              dataKey="engineLoad"
              stroke={lineColor}
              fill={lineColor}
              fillOpacity={0.1}
              strokeWidth={2}
              connectNulls
            />
          </AreaChart>
        </ResponsiveContainer>
      </ChartCard>

      {/* Battery Voltage */}
      <ChartCard
        title={t("battery")}
        currentValue={latest?.battery !== null ? `${latest?.battery}V` : "-"}
      >
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke={gridColor} />
            <XAxis dataKey="time" tick={{ fontSize: 10 }} stroke={gridColor} />
            <YAxis tick={{ fontSize: 10 }} stroke={gridColor} />
            <Tooltip />
            <Line
              type="monotone"
              dataKey="battery"
              stroke={lineColor}
              strokeWidth={2}
              dot={false}
              connectNulls
            />
          </LineChart>
        </ResponsiveContainer>
      </ChartCard>
    </div>
  );
}
