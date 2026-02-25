"use client";

import type { ReactNode } from "react";
import { useTranslations } from "next-intl";
import {
  Building2,
  Route,
  Calendar,
  Navigation,
  MapPin,
  Radio,
  RefreshCw,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Separator } from "@/components/ui/separator";
import type { GTFSStats, GTFSFeed } from "@/types/gtfs";

/* ---- Module-scope helper components (React 19: no nested definitions) ---- */

function StatCard({
  icon,
  count,
  label,
}: {
  icon: ReactNode;
  count: number;
  label: string;
}) {
  return (
    <div className="rounded-lg border border-border p-(--spacing-card) flex flex-col items-center gap-(--spacing-tight)">
      <div className="text-foreground-muted">{icon}</div>
      <span className="text-2xl font-bold font-heading text-foreground">
        {count.toLocaleString()}
      </span>
      <span className="text-xs text-foreground-muted">{label}</span>
    </div>
  );
}

function FeedCard({
  feed,
  enabledLabel,
  disabledLabel,
  intervalLabel,
}: {
  feed: GTFSFeed;
  enabledLabel: string;
  disabledLabel: string;
  intervalLabel: string;
}) {
  return (
    <div className="rounded-lg border border-border p-(--spacing-card) flex items-center justify-between">
      <div className="flex items-center gap-(--spacing-inline)">
        <Radio className="size-4 text-foreground-muted" aria-hidden="true" />
        <div>
          <p className="text-sm font-medium text-foreground">
            {feed.operator_name}
          </p>
          <p className="text-xs text-foreground-muted">
            {feed.feed_id} &middot;{" "}
            {intervalLabel}
          </p>
        </div>
      </div>
      <Badge
        variant={feed.enabled ? "default" : "outline"}
        className={feed.enabled ? "text-status-ontime" : "text-foreground-muted"}
      >
        {feed.enabled ? enabledLabel : disabledLabel}
      </Badge>
    </div>
  );
}

/* ---- Main component ---- */

interface DataOverviewProps {
  stats: GTFSStats | null;
  feeds: GTFSFeed[];
  isLoading: boolean;
  onRefresh: () => void;
}

export function DataOverview({
  stats,
  feeds,
  isLoading,
  onRefresh,
}: DataOverviewProps) {
  const t = useTranslations("gtfs.overview");

  return (
    <div className="space-y-(--spacing-grid) p-(--spacing-card)">
      {/* Stats section */}
      <div className="space-y-(--spacing-card)">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-foreground">
            {t("dataTitle")}
          </h3>
          <Button
            variant="ghost"
            size="sm"
            className="cursor-pointer"
            onClick={onRefresh}
            disabled={isLoading}
          >
            <RefreshCw
              className={`size-4 mr-1 ${isLoading ? "animate-spin" : ""}`}
              aria-hidden="true"
            />
            {t("refreshButton")}
          </Button>
        </div>

        {isLoading || !stats ? (
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-(--spacing-grid)">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-24 rounded-lg" />
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-(--spacing-grid)">
            <StatCard
              icon={<Building2 className="size-5" aria-hidden="true" />}
              count={stats.agencies}
              label={t("agencies")}
            />
            <StatCard
              icon={<Route className="size-5" aria-hidden="true" />}
              count={stats.routes}
              label={t("routes")}
            />
            <StatCard
              icon={<Calendar className="size-5" aria-hidden="true" />}
              count={stats.calendars}
              label={t("calendars")}
            />
            <StatCard
              icon={<Navigation className="size-5" aria-hidden="true" />}
              count={stats.trips}
              label={t("trips")}
            />
            <StatCard
              icon={<MapPin className="size-5" aria-hidden="true" />}
              count={stats.stops}
              label={t("stops")}
            />
          </div>
        )}
      </div>

      <Separator />

      {/* Feeds section */}
      <div className="space-y-(--spacing-card)">
        <h3 className="text-sm font-semibold text-foreground">
          {t("feedsTitle")}
        </h3>

        {isLoading ? (
          <Skeleton className="h-16 rounded-lg" />
        ) : feeds.length === 0 ? (
          <p className="text-sm text-foreground-muted">{t("noFeeds")}</p>
        ) : (
          <div className="space-y-(--spacing-inline)">
            {feeds.map((feed) => (
              <FeedCard
                key={feed.feed_id}
                feed={feed}
                enabledLabel={t("feedEnabled")}
                disabledLabel={t("feedDisabled")}
                intervalLabel={t("pollInterval", {
                  seconds: feed.poll_interval_seconds,
                })}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
