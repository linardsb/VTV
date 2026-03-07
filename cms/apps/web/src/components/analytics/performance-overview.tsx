"use client";

import { useCallback, useState } from "react";
import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { authFetch } from "@/lib/auth-fetch";
import { cn } from "@/lib/utils";
import type { OnTimePerformanceResponse } from "@/types/analytics";

interface PerformanceOverviewProps {
  data: OnTimePerformanceResponse;
}

const API_BASE = process.env.NEXT_PUBLIC_AGENT_URL ?? "http://localhost:8123";

function onTimeColor(pct: number): string {
  if (pct >= 90) return "text-status-ontime";
  if (pct >= 75) return "text-status-delayed";
  return "text-status-critical";
}

function onTimeProgressColor(pct: number): string {
  if (pct >= 90) return "[&>div]:bg-status-ontime";
  if (pct >= 75) return "[&>div]:bg-status-delayed";
  return "[&>div]:bg-status-critical";
}

export function PerformanceOverview({ data }: PerformanceOverviewProps) {
  const t = useTranslations("analytics.performance");

  const [filterDate, setFilterDate] = useState("");
  const [filterFrom, setFilterFrom] = useState("");
  const [filterUntil, setFilterUntil] = useState("");
  const [filteredData, setFilteredData] =
    useState<OnTimePerformanceResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const display = filteredData ?? data;

  const handleApplyFilters = useCallback(async () => {
    const params = new URLSearchParams();
    if (filterDate) params.set("date", filterDate);
    if (filterFrom) params.set("time_from", filterFrom);
    if (filterUntil) params.set("time_until", filterUntil);

    setLoading(true);
    setError(null);
    try {
      const res = await authFetch(
        `${API_BASE}/api/v1/analytics/on-time-performance?${params.toString()}`
      );
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json: OnTimePerformanceResponse = await res.json();
      setFilteredData(json);
    } catch {
      setError(t("transitUnavailable"));
    } finally {
      setLoading(false);
    }
  }, [filterDate, filterFrom, filterUntil, t]);

  return (
    <div className="space-y-(--spacing-section)">
      <div className="flex flex-wrap items-end gap-(--spacing-grid)">
        <div>
          <label
            htmlFor="perf-date"
            className="mb-1 block text-xs text-foreground-muted"
          >
            {t("filterDate")}
          </label>
          <Input
            id="perf-date"
            type="date"
            value={filterDate}
            onChange={(e) => setFilterDate(e.target.value)}
            className="w-[10rem]"
          />
        </div>
        <div>
          <label
            htmlFor="perf-from"
            className="mb-1 block text-xs text-foreground-muted"
          >
            {t("filterTimeFrom")}
          </label>
          <Input
            id="perf-from"
            type="time"
            value={filterFrom}
            onChange={(e) => setFilterFrom(e.target.value)}
            className="w-[8rem]"
          />
        </div>
        <div>
          <label
            htmlFor="perf-until"
            className="mb-1 block text-xs text-foreground-muted"
          >
            {t("filterTimeUntil")}
          </label>
          <Input
            id="perf-until"
            type="time"
            value={filterUntil}
            onChange={(e) => setFilterUntil(e.target.value)}
            className="w-[8rem]"
          />
        </div>
        <Button
          onClick={handleApplyFilters}
          disabled={loading}
          className="cursor-pointer"
        >
          {loading ? "..." : t("applyFilters")}
        </Button>
      </div>

      {error && <p className="text-sm text-foreground-muted">{error}</p>}

      <div className="flex items-baseline gap-(--spacing-grid)">
        <p
          className={cn(
            "font-heading text-4xl font-bold",
            onTimeColor(display.network_on_time_percentage)
          )}
        >
          {display.network_on_time_percentage}%
        </p>
        <p className="text-sm text-foreground-muted">
          {display.service_date} &middot; {display.service_type} &middot;{" "}
          {display.total_routes} routes &middot;{" "}
          {t("seconds", {
            value: Math.round(display.network_average_delay_seconds),
          })}{" "}
          avg
        </p>
      </div>

      {display.routes.length === 0 ? (
        <p className="text-sm text-foreground-muted">{t("noRoutes")}</p>
      ) : (
        <div className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t("route")}</TableHead>
                <TableHead className="text-right">{t("scheduled")}</TableHead>
                <TableHead className="text-right">{t("tracked")}</TableHead>
                <TableHead className="text-right">{t("onTime")}</TableHead>
                <TableHead className="text-right">{t("late")}</TableHead>
                <TableHead className="text-right">{t("early")}</TableHead>
                <TableHead className="w-[10rem]">
                  {t("onTimePercent")}
                </TableHead>
                <TableHead className="text-right">{t("avgDelay")}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {display.routes.map((route) => (
                <TableRow key={route.route_id}>
                  <TableCell className="font-medium">
                    {route.route_short_name}
                  </TableCell>
                  <TableCell className="text-right">
                    {route.scheduled_trips}
                  </TableCell>
                  <TableCell className="text-right">
                    {route.tracked_trips}
                  </TableCell>
                  <TableCell className="text-right">
                    {route.on_time_count}
                  </TableCell>
                  <TableCell className="text-right">
                    {route.late_count}
                  </TableCell>
                  <TableCell className="text-right">
                    {route.early_count}
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center gap-(--spacing-inline)">
                      <span
                        className={cn(
                          "w-12 text-right text-sm font-medium",
                          onTimeColor(route.on_time_percentage)
                        )}
                      >
                        {route.on_time_percentage}%
                      </span>
                      <Progress
                        value={route.on_time_percentage}
                        className={cn(
                          "h-2 flex-1 bg-surface-secondary",
                          onTimeProgressColor(route.on_time_percentage)
                        )}
                      />
                    </div>
                  </TableCell>
                  <TableCell className="text-right">
                    {t("seconds", {
                      value: Math.round(route.average_delay_seconds),
                    })}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}
