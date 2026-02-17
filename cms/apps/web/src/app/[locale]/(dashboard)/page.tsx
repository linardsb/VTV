"use client";

import { useTranslations, useLocale } from "next-intl";
import Link from "next/link";
import { Bus, Clock, AlertTriangle, Gauge, ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { MetricCard } from "@/components/dashboard/metric-card";
import { CalendarGrid } from "@/components/dashboard/calendar-grid";
import {
  ResizablePanelGroup,
  ResizablePanel,
  ResizableHandle,
} from "@/components/ui/resizable";
import { MOCK_METRICS, MOCK_EVENTS } from "@/lib/mock-dashboard-data";

const METRIC_ICONS = [Bus, Clock, AlertTriangle, Gauge] as const;
const METRIC_KEYS = [
  "activeVehicles",
  "onTimePerformance",
  "delayedRoutes",
  "fleetUtilization",
] as const;

export default function DashboardPage() {
  const t = useTranslations("dashboard");
  const locale = useLocale();

  return (
    <div className="space-y-(--spacing-section)">
      <div className="flex items-center justify-between">
        <h1 className="font-heading text-heading font-semibold text-foreground">
          {t("title")}
        </h1>
        <Button asChild variant="outline" className="cursor-pointer">
          <Link href={`/${locale}/routes`}>
            {t("manageRoutes")}
            <ArrowRight className="ml-2 size-4" aria-hidden="true" />
          </Link>
        </Button>
      </div>

      <ResizablePanelGroup orientation="vertical" className="min-h-[calc(100vh-6rem)]">
        {/* Metrics panel */}
        <ResizablePanel defaultSize={20} minSize={10}>
          <div className="grid grid-cols-1 gap-(--spacing-grid) sm:grid-cols-2 lg:grid-cols-4">
            {MOCK_METRICS.map((metric, i) => (
              <MetricCard
                key={METRIC_KEYS[i]}
                icon={METRIC_ICONS[i]}
                title={t(`metrics.${METRIC_KEYS[i]}`)}
                value={metric.value}
                delta={metric.delta}
                deltaType={metric.deltaType}
                subtitle={t("metrics.comparedToLastMonth")}
              />
            ))}
          </div>
        </ResizablePanel>

        <ResizableHandle withHandle />

        {/* Calendar panel */}
        <ResizablePanel defaultSize={80} minSize={30}>
          <div className="h-full pt-(--spacing-grid)">
            <CalendarGrid events={MOCK_EVENTS} />
          </div>
        </ResizablePanel>
      </ResizablePanelGroup>
    </div>
  );
}
