"use client";

import { useMemo } from "react";
import { useTranslations } from "next-intl";
import type { GTFSFeed } from "@/types/gtfs";
import type { BusPosition } from "@/types/route";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

interface FeedHealthOverlayProps {
  feeds: GTFSFeed[];
  vehicles: BusPosition[];
  feedColors: Record<string, string>;
}

export function FeedHealthOverlay({
  feeds,
  vehicles,
  feedColors,
}: FeedHealthOverlayProps) {
  const t = useTranslations("routes.feed");

  const feedStats = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const v of vehicles) {
      counts[v.feedId] = (counts[v.feedId] ?? 0) + 1;
    }
    return feeds
      .filter((f) => f.enabled)
      .map((feed) => ({
        feedId: feed.feed_id,
        operatorName: feed.operator_name,
        count: counts[feed.feed_id] ?? 0,
        color: feedColors[feed.feed_id] ?? "#888",
      }));
  }, [feeds, vehicles, feedColors]);

  if (feedStats.length === 0) return null;

  return (
    <div className="absolute left-12 top-14 z-[1000] flex flex-col gap-(--spacing-tight) rounded-md bg-surface/90 px-2 py-1.5 shadow-sm backdrop-blur-sm">
      <TooltipProvider delayDuration={200}>
        {feedStats.map((feed) => {
          const abbreviated =
            feed.operatorName.length > 12
              ? feed.operatorName.slice(0, 11) + "\u2026"
              : feed.operatorName;

          return (
            <Tooltip key={feed.feedId}>
              <TooltipTrigger asChild>
                <div className="flex cursor-default items-center gap-(--spacing-tight)">
                  <span
                    className="inline-block size-2.5 shrink-0 rounded-full"
                    style={{ backgroundColor: feed.color }}
                    aria-hidden="true"
                  />
                  <span className="text-xs text-foreground">
                    {abbreviated}
                  </span>
                  <span className="text-xs tabular-nums text-foreground-muted">
                    {feed.count}
                  </span>
                  <span
                    className={`inline-block size-1.5 rounded-full ${
                      feed.count > 0
                        ? "bg-status-ontime"
                        : "bg-status-delayed"
                    }`}
                    aria-label={feed.count > 0 ? t("healthy") : t("stale")}
                  />
                </div>
              </TooltipTrigger>
              <TooltipContent side="right" className="text-xs">
                <p className="font-medium">{feed.operatorName}</p>
                <p className="text-foreground-muted">
                  {t("vehicles", { count: feed.count })}
                </p>
              </TooltipContent>
            </Tooltip>
          );
        })}
      </TooltipProvider>
    </div>
  );
}
