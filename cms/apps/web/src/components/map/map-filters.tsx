"use client";

import { useTranslations } from "next-intl";
import { cn } from "@/lib/utils";
import type { GTFSFeed } from "@/types/gtfs";
import type { ConnectionMode } from "@/hooks/use-vehicle-positions";

interface MapFiltersProps {
  feeds: GTFSFeed[];
  feedColors: Record<string, string>;
  enabledFeedIds: Set<string>;
  onToggleFeed: (feedId: string) => void;
  onToggleAllFeeds: () => void;
  selectedRouteType: number | null;
  onRouteTypeChange: (type: number | null) => void;
  vehicleCount: number;
  connectionMode: ConnectionMode;
}

const ROUTE_TYPE_OPTIONS: { type: number | null; key: string }[] = [
  { type: null, key: "allTypes" },
  { type: 3, key: "bus" },
  { type: 11, key: "trolleybus" },
  { type: 0, key: "tram" },
];

export function MapFilters({
  feeds,
  feedColors,
  enabledFeedIds,
  onToggleFeed,
  onToggleAllFeeds,
  selectedRouteType,
  onRouteTypeChange,
  vehicleCount,
  connectionMode,
}: MapFiltersProps) {
  const t = useTranslations("map");

  const enabledFeeds = feeds.filter((f) => f.enabled);
  const allSelected = enabledFeedIds.size === enabledFeeds.length;

  return (
    <div
      className="absolute left-0 right-0 top-0 z-[1000] flex flex-wrap items-center gap-(--spacing-inline) bg-surface/90 px-(--spacing-card) py-(--spacing-tight) shadow-sm backdrop-blur-sm"
      data-testid="map-filters"
    >
      {/* Connection badge */}
      <div
        className="flex items-center gap-(--spacing-tight) text-xs"
        data-testid="connection-badge"
      >
        <span
          className={cn(
            "inline-block size-2 rounded-full",
            connectionMode === "ws"
              ? "bg-status-ontime"
              : connectionMode === "polling"
                ? "bg-status-delayed"
                : "animate-pulse bg-status-delayed",
          )}
          aria-hidden="true"
        />
        <span className="font-medium text-foreground">
          {connectionMode === "ws"
            ? t("liveStream")
            : connectionMode === "polling"
              ? t("pollingFallback")
              : t("wsConnecting")}
        </span>
      </div>

      {/* Separator */}
      <div className="h-4 w-px bg-border" aria-hidden="true" />

      {/* Vehicle count */}
      <span className="text-xs tabular-nums text-foreground-muted">
        {t("vehicles", { count: vehicleCount })}
      </span>

      {/* Separator */}
      <div className="h-4 w-px bg-border" aria-hidden="true" />

      {/* Feed toggle chips */}
      <div className="flex flex-wrap items-center gap-(--spacing-tight)">
        <button
          type="button"
          onClick={onToggleAllFeeds}
          className={cn(
            "cursor-pointer px-2 py-0.5 text-xs font-medium transition-colors duration-150",
            allSelected
              ? "bg-interactive text-interactive-foreground"
              : "bg-surface-secondary text-foreground-muted hover:bg-muted",
          )}
          aria-pressed={allSelected}
        >
          {t("filters.allFeeds")}
        </button>
        {enabledFeeds.map((feed) => {
          const isActive = enabledFeedIds.has(feed.feed_id);
          return (
            <button
              key={feed.feed_id}
              type="button"
              onClick={() => onToggleFeed(feed.feed_id)}
              className={cn(
                "flex cursor-pointer items-center gap-(--spacing-tight) px-2 py-0.5 text-xs font-medium transition-colors duration-150",
                isActive
                  ? "bg-interactive text-interactive-foreground"
                  : "bg-surface-secondary text-foreground-muted hover:bg-muted",
              )}
              aria-pressed={isActive}
            >
              <span
                className="inline-block size-2 rounded-full"
                style={{ backgroundColor: feedColors[feed.feed_id] ?? "#888" }}
                aria-hidden="true"
              />
              {feed.operator_name}
            </button>
          );
        })}
      </div>

      {/* Separator */}
      <div className="h-4 w-px bg-border" aria-hidden="true" />

      {/* Route type filter */}
      <div className="flex items-center gap-(--spacing-tight)">
        {ROUTE_TYPE_OPTIONS.map((opt) => (
          <button
            key={opt.key}
            type="button"
            onClick={() => onRouteTypeChange(opt.type)}
            className={cn(
              "cursor-pointer px-2 py-0.5 text-xs font-medium transition-colors duration-150",
              selectedRouteType === opt.type
                ? "bg-interactive text-interactive-foreground"
                : "bg-surface-secondary text-foreground-muted hover:bg-muted",
            )}
            aria-pressed={selectedRouteType === opt.type}
          >
            {t(`filters.${opt.key}`)}
          </button>
        ))}
      </div>
    </div>
  );
}
