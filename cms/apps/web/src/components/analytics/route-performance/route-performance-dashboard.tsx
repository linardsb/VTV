"use client";

import { useCallback, useState } from "react";
import { useTranslations } from "next-intl";
import { useSession } from "next-auth/react";
import useSWR from "swr";
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ReferenceLine,
  ResponsiveContainer,
} from "recharts";
import { RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { ChartCard } from "@/components/analytics/route-performance/chart-card";
import {
  fetchRoutePerformance,
  fetchRouteDelayByStop,
  fetchRouteLoadTrend,
  fetchRouteAnomalies,
} from "@/lib/route-performance-sdk";
import { fetchRoutes } from "@/lib/schedules-sdk";
import type { Route } from "@/types/route";
import type {
  RoutePerformanceTrendResponse,
  RouteDelayByStopResponse,
  RouteLoadTrendResponse,
  RouteAnomalyResponse,
} from "@/types/analytics";

type TimeWindow = "7" | "14" | "30";

const chartGridStroke = "var(--color-border)";
const interactiveColor = "var(--color-interactive)";
const ontimeColor = "var(--color-status-ontime)";
const delayedColor = "var(--color-status-delayed)";
const criticalColor = "var(--color-status-critical)";
const mutedColor = "var(--color-foreground-muted)";

const tooltipStyle = {
  borderRadius: 0,
  border: "1px solid var(--color-border)",
  fontSize: 12,
};

const tickStyle = { fontSize: 10 };

interface RoutePerformanceDashboardProps {
  locale: string;
}

async function routeListFetcher(): Promise<Route[]> {
  const result = await fetchRoutes({ page_size: 100 });
  return result.items;
}

interface PerformanceBundle {
  perf: RoutePerformanceTrendResponse | null;
  delay: RouteDelayByStopResponse | null;
  load: RouteLoadTrendResponse | null;
  anomaly: RouteAnomalyResponse | null;
}

async function performanceFetcher([, routeId, window]: [
  string,
  string,
  TimeWindow,
]): Promise<PerformanceBundle> {
  const results = await Promise.allSettled([
    fetchRoutePerformance(routeId, window),
    fetchRouteDelayByStop(routeId, window),
    fetchRouteLoadTrend(routeId, window),
    fetchRouteAnomalies(routeId, window),
  ]);

  return {
    perf: results[0].status === "fulfilled" ? results[0].value : null,
    delay: results[1].status === "fulfilled" ? results[1].value : null,
    load: results[2].status === "fulfilled" ? results[2].value : null,
    anomaly: results[3].status === "fulfilled" ? results[3].value : null,
  };
}

export function RoutePerformanceDashboard({
  locale,
}: RoutePerformanceDashboardProps) {
  void locale;
  const t = useTranslations("analytics.routePerformance");
  const { status } = useSession();

  const [selectedRouteId, setSelectedRouteId] = useState<string>("");
  const [timeWindow, setTimeWindow] = useState<TimeWindow>("7");

  const { data: routes } = useSWR<Route[]>(
    status === "authenticated" ? "route-perf-routes" : null,
    routeListFetcher,
  );

  const perfKey =
    status === "authenticated" && selectedRouteId
      ? (["route-perf-data", selectedRouteId, timeWindow] as [
          string,
          string,
          TimeWindow,
        ])
      : null;

  const {
    data: bundle,
    isLoading: perfLoading,
    mutate: refreshPerf,
  } = useSWR<PerformanceBundle>(perfKey, performanceFetcher, {
    refreshInterval: 0,
  });

  const handleRefresh = useCallback(() => {
    void refreshPerf();
  }, [refreshPerf]);

  const hasData =
    bundle &&
    (bundle.perf !== null ||
      bundle.delay !== null ||
      bundle.load !== null ||
      bundle.anomaly !== null);

  return (
    <div className="flex flex-col gap-(--spacing-section) p-(--spacing-page)">
      {/* Header */}
      <div className="flex flex-col gap-(--spacing-inline) sm:flex-row sm:items-center sm:justify-between">
        <h1 className="font-heading text-xl font-semibold text-foreground">
          {t("title")}
        </h1>
        <div className="flex items-center gap-(--spacing-inline)">
          <Select value={selectedRouteId} onValueChange={setSelectedRouteId}>
            <SelectTrigger className="w-[200px] cursor-pointer">
              <SelectValue placeholder={t("selectRoute")} />
            </SelectTrigger>
            <SelectContent>
              {(routes ?? []).map((route) => (
                <SelectItem
                  key={route.gtfs_route_id}
                  value={route.gtfs_route_id}
                  className="cursor-pointer"
                >
                  {route.route_short_name} — {route.route_long_name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <div className="flex gap-(--spacing-tight)">
            {(["7", "14", "30"] as const).map((w) => (
              <Button
                key={w}
                variant={timeWindow === w ? "default" : "outline"}
                size="sm"
                className="cursor-pointer"
                onClick={() => setTimeWindow(w)}
              >
                {t(`window${w}d` as "window7d" | "window14d" | "window30d")}
              </Button>
            ))}
          </div>

          {selectedRouteId && (
            <Button
              variant="outline"
              size="sm"
              className="cursor-pointer"
              onClick={handleRefresh}
              aria-label={t("refresh")}
            >
              <RefreshCw className="size-4" />
            </Button>
          )}
        </div>
      </div>

      {/* Empty state — no route selected */}
      {!selectedRouteId && (
        <div className="flex min-h-[400px] items-center justify-center text-foreground-muted">
          <p>{t("noRouteSelected")}</p>
        </div>
      )}

      {/* Loading state */}
      {selectedRouteId && perfLoading && (
        <div className="grid grid-cols-1 gap-(--spacing-grid) md:grid-cols-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={`perf-skel-${i}`} className="h-[280px] w-full" />
          ))}
        </div>
      )}

      {/* No data state */}
      {selectedRouteId && !perfLoading && !hasData && (
        <div className="flex min-h-[400px] flex-col items-center justify-center gap-(--spacing-inline) text-foreground-muted">
          <p>{t("noData")}</p>
          <Button
            variant="outline"
            size="sm"
            className="cursor-pointer"
            onClick={handleRefresh}
          >
            <RefreshCw className="mr-1 size-4" />
            {t("refresh")}
          </Button>
        </div>
      )}

      {/* Charts */}
      {selectedRouteId && !perfLoading && hasData && (
        <>
          {/* KPI Summary */}
          <div className="grid grid-cols-2 gap-(--spacing-grid) md:grid-cols-4">
            <div className="border border-card-border bg-card-bg p-(--spacing-card)">
              <p className="text-xs font-medium uppercase tracking-wide text-foreground-muted">
                {t("onTimePercent")}
              </p>
              <p className="font-heading text-2xl font-semibold text-foreground">
                {bundle?.perf
                  ? `${bundle.perf.overall_on_time_percentage.toFixed(1)}%`
                  : "—"}
              </p>
            </div>
            <div className="border border-card-border bg-card-bg p-(--spacing-card)">
              <p className="text-xs font-medium uppercase tracking-wide text-foreground-muted">
                {t("avgDelay")}
              </p>
              <p className="font-heading text-2xl font-semibold text-foreground">
                {bundle?.perf
                  ? `${bundle.perf.overall_average_delay_seconds.toFixed(0)}s`
                  : "—"}
              </p>
            </div>
            <div className="border border-card-border bg-card-bg p-(--spacing-card)">
              <p className="text-xs font-medium uppercase tracking-wide text-foreground-muted">
                {t("loadFactor")}
              </p>
              <p className="font-heading text-2xl font-semibold text-foreground">
                {bundle?.load && bundle.load.data.length > 0
                  ? `${(bundle.load.data[bundle.load.data.length - 1].load_factor * 100).toFixed(0)}%`
                  : "—"}
              </p>
            </div>
            <div className="border border-card-border bg-card-bg p-(--spacing-card)">
              <p className="text-xs font-medium uppercase tracking-wide text-foreground-muted">
                {t("anomalyCount")}
              </p>
              <p className="font-heading text-2xl font-semibold text-foreground">
                {bundle?.anomaly ? bundle.anomaly.total_anomalies : "—"}
              </p>
            </div>
          </div>

          {/* Chart Grid */}
          <div className="grid grid-cols-1 gap-(--spacing-grid) md:grid-cols-2">
            {/* On-Time Trend */}
            <ChartCard
              title={t("onTimeTrend")}
              currentValue={
                bundle?.perf
                  ? `${bundle.perf.overall_on_time_percentage.toFixed(1)}%`
                  : undefined
              }
            >
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={bundle?.perf?.data ?? []}>
                  <CartesianGrid
                    strokeDasharray="3 3"
                    stroke={chartGridStroke}
                  />
                  <XAxis
                    dataKey="date"
                    tick={tickStyle}
                    axisLine={false}
                    tickLine={false}
                  />
                  <YAxis
                    domain={[0, 100]}
                    tick={tickStyle}
                    axisLine={false}
                    tickLine={false}
                  />
                  <Tooltip contentStyle={tooltipStyle} />
                  <ReferenceLine
                    y={90}
                    stroke={ontimeColor}
                    strokeDasharray="5 5"
                    label={{ value: "90%", position: "right", fontSize: 10 }}
                  />
                  <Line
                    type="monotone"
                    dataKey="on_time_percentage"
                    stroke={interactiveColor}
                    strokeWidth={2}
                    dot={false}
                    name={t("onTimePercent")}
                  />
                </LineChart>
              </ResponsiveContainer>
            </ChartCard>

            {/* Delay by Stop */}
            <ChartCard title={t("delayByStop")}>
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={bundle?.delay?.stops ?? []}>
                  <CartesianGrid
                    strokeDasharray="3 3"
                    stroke={chartGridStroke}
                  />
                  <XAxis
                    dataKey="stop_name"
                    tick={tickStyle}
                    axisLine={false}
                    tickLine={false}
                    interval={0}
                    angle={-45}
                    textAnchor="end"
                    height={60}
                  />
                  <YAxis
                    tick={tickStyle}
                    axisLine={false}
                    tickLine={false}
                  />
                  <Tooltip contentStyle={tooltipStyle} />
                  <Bar
                    dataKey="average_delay_seconds"
                    fill={delayedColor}
                    name={t("avgDelay")}
                  />
                </BarChart>
              </ResponsiveContainer>
            </ChartCard>

            {/* Load Trend */}
            <ChartCard title={t("loadTrend")}>
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={bundle?.load?.data ?? []}>
                  <CartesianGrid
                    strokeDasharray="3 3"
                    stroke={chartGridStroke}
                  />
                  <XAxis
                    dataKey="date"
                    tick={tickStyle}
                    axisLine={false}
                    tickLine={false}
                  />
                  <YAxis
                    domain={[0, 1]}
                    tickFormatter={(v: number) => `${(v * 100).toFixed(0)}%`}
                    tick={tickStyle}
                    axisLine={false}
                    tickLine={false}
                  />
                  <Tooltip contentStyle={tooltipStyle} />
                  <Area
                    type="monotone"
                    dataKey="load_factor"
                    stroke={interactiveColor}
                    fill={interactiveColor}
                    fillOpacity={0.1}
                    name={t("loadFactor")}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </ChartCard>

            {/* Anomaly Trend */}
            <ChartCard
              title={t("anomalyTrend")}
              currentValue={
                bundle?.anomaly
                  ? String(bundle.anomaly.total_anomalies)
                  : undefined
              }
            >
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={bundle?.anomaly?.data ?? []}>
                  <CartesianGrid
                    strokeDasharray="3 3"
                    stroke={chartGridStroke}
                  />
                  <XAxis
                    dataKey="date"
                    tick={tickStyle}
                    axisLine={false}
                    tickLine={false}
                  />
                  <YAxis
                    tick={tickStyle}
                    axisLine={false}
                    tickLine={false}
                  />
                  <Tooltip contentStyle={tooltipStyle} />
                  <Legend />
                  <Area
                    type="monotone"
                    dataKey="off_route"
                    stackId="anomalies"
                    stroke={criticalColor}
                    fill={criticalColor}
                    fillOpacity={0.6}
                    name={t("offRoute")}
                  />
                  <Area
                    type="monotone"
                    dataKey="stuck"
                    stackId="anomalies"
                    stroke={delayedColor}
                    fill={delayedColor}
                    fillOpacity={0.6}
                    name={t("stuck")}
                  />
                  <Area
                    type="monotone"
                    dataKey="gps_gap"
                    stackId="anomalies"
                    stroke={mutedColor}
                    fill={mutedColor}
                    fillOpacity={0.6}
                    name={t("gpsGap")}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </ChartCard>
          </div>
        </>
      )}
    </div>
  );
}
