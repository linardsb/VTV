"use client";

import { useState, useMemo, useCallback } from "react";
import dynamic from "next/dynamic";
import { useSession } from "next-auth/react";
import useSWR from "swr";
import { Skeleton } from "@/components/ui/skeleton";
import { useVehiclePositions } from "@/hooks/use-vehicle-positions";
import { MapFilters } from "@/components/map/map-filters";
import { VehicleDetailDialog } from "@/components/map/vehicle-detail-dialog";
import { fetchFeeds } from "@/lib/gtfs-sdk";
import { fetchRoutes } from "@/lib/schedules-sdk";
import { toHexColor } from "@/lib/color-utils";
import type { BusPosition, Route } from "@/types/route";
import type { GTFSFeed } from "@/types/gtfs";

/** Deterministic feed border colors (hex — used in Leaflet divIcon). */
const FEED_BORDER_COLORS = [
  "#0391F2", "#06757E", "#8E24AA", "#FB8C00", "#E53935", "#43A047",
];

function MapSkeleton() {
  return (
    <div className="flex h-full w-full items-center justify-center bg-surface">
      <div className="flex flex-col items-center gap-2">
        <Skeleton className="h-8 w-32" />
        <Skeleton className="h-4 w-24" />
      </div>
    </div>
  );
}

const VehicleMap = dynamic(
  () =>
    import("@/components/map/vehicle-map").then((m) => ({
      default: m.VehicleMap,
    })),
  { ssr: false, loading: () => <MapSkeleton /> },
);

/** Fetch all routes (paginated) for route color map. */
async function fetchAllRoutes(): Promise<Route[]> {
  const first = await fetchRoutes({ page: 1, page_size: 100 });
  const totalPages = Math.ceil(first.total / 100);
  if (totalPages <= 1) return first.items;
  const collected = [...first.items];
  for (let p = 2; p <= totalPages; p++) {
    const result = await fetchRoutes({ page: p, page_size: 100 });
    collected.push(...result.items);
  }
  return collected;
}

export default function MapPage() {
  const { status } = useSession();
  const isAuthenticated = status === "authenticated";

  // SWR for feeds — avoids setState-in-useEffect lint issue
  const { data: feeds = [] } = useSWR<GTFSFeed[]>(
    isAuthenticated ? "map-feeds" : null,
    () => fetchFeeds(),
    { revalidateOnFocus: false },
  );

  // SWR for all routes (route color map)
  const { data: allRoutes = [] } = useSWR<Route[]>(
    isAuthenticated ? "map-all-routes" : null,
    () => fetchAllRoutes(),
    { revalidateOnFocus: false },
  );

  // UI state
  const [disabledFeedIds, setDisabledFeedIds] = useState<Set<string>>(new Set());
  const [selectedRouteType, setSelectedRouteType] = useState<number | null>(null);
  const [selectedVehicle, setSelectedVehicle] = useState<BusPosition | null>(null);
  const [detailOpen, setDetailOpen] = useState(false);

  // Effective enabled feed IDs: all enabled feeds minus user-disabled
  const enabledFeedIds = useMemo(() => {
    const allEnabled = feeds.filter((f) => f.enabled).map((f) => f.feed_id);
    if (disabledFeedIds.size === 0) return new Set(allEnabled);
    return new Set(allEnabled.filter((id) => !disabledFeedIds.has(id)));
  }, [feeds, disabledFeedIds]);

  // Build route color lookup: gtfs_route_id → #hex
  const routeColorMap = useMemo(() => {
    const map: Record<string, string> = {};
    for (const r of allRoutes) {
      if (r.route_color) {
        map[r.gtfs_route_id] = toHexColor(r.route_color);
      }
    }
    return map;
  }, [allRoutes]);

  // Feed border color map: feedId → hex color
  const feedColorMap = useMemo(() => {
    const enabledFeeds = feeds.filter((f) => f.enabled);
    const colorMap: Record<string, string> = {};
    enabledFeeds.forEach((feed, idx) => {
      colorMap[feed.feed_id] =
        FEED_BORDER_COLORS[idx % FEED_BORDER_COLORS.length];
    });
    return colorMap;
  }, [feeds]);

  // Live vehicle positions — all feeds, no route filter
  const { vehicles, connectionMode } = useVehiclePositions({
    colorMap: routeColorMap,
    routeFilter: null,
    feedFilter: null,
  });

  // Filtered vehicle count for the filter bar
  const filteredVehicleCount = useMemo(() => {
    let filtered = vehicles;
    const enabledFeedCount = feeds.filter((f) => f.enabled).length;
    if (enabledFeedIds.size < enabledFeedCount) {
      filtered = filtered.filter((v) => enabledFeedIds.has(v.feedId));
    }
    if (selectedRouteType !== null) {
      filtered = filtered.filter((v) => {
        if (selectedRouteType === 0)
          return v.routeType === 0 || (v.routeType >= 900 && v.routeType <= 999);
        if (selectedRouteType === 11)
          return v.routeType === 11 || (v.routeType >= 800 && v.routeType <= 899);
        if (selectedRouteType === 3)
          return v.routeType === 3 || (v.routeType >= 700 && v.routeType <= 799);
        return v.routeType === selectedRouteType;
      });
    }
    return filtered.length;
  }, [vehicles, enabledFeedIds, selectedRouteType, feeds]);

  // Feed toggle handlers
  const handleToggleFeed = useCallback((feedId: string) => {
    setDisabledFeedIds((prev) => {
      const next = new Set(prev);
      if (next.has(feedId)) {
        next.delete(feedId);
      } else {
        next.add(feedId);
      }
      return next;
    });
  }, []);

  const handleToggleAllFeeds = useCallback(() => {
    setDisabledFeedIds(new Set());
  }, []);

  const handleVehicleClick = useCallback((vehicle: BusPosition) => {
    setSelectedVehicle(vehicle);
    setDetailOpen(true);
  }, []);

  const handleDetailClose = useCallback(() => {
    setDetailOpen(false);
    setSelectedVehicle(null);
  }, []);

  return (
    <div className="relative -m-(--spacing-page) flex h-dvh flex-col">
      {/* Filter bar */}
      <MapFilters
        feeds={feeds}
        feedColors={feedColorMap}
        enabledFeedIds={enabledFeedIds}
        onToggleFeed={handleToggleFeed}
        onToggleAllFeeds={handleToggleAllFeeds}
        selectedRouteType={selectedRouteType}
        onRouteTypeChange={setSelectedRouteType}
        vehicleCount={filteredVehicleCount}
        connectionMode={connectionMode}
      />

      {/* Map fills remaining space */}
      <div className="flex-1 pt-8">
        <VehicleMap
          vehicles={vehicles}
          feeds={feeds}
          feedColors={feedColorMap}
          enabledFeedIds={enabledFeedIds}
          selectedRouteType={selectedRouteType}
          connectionMode={connectionMode}
          onVehicleClick={handleVehicleClick}
        />
      </div>

      {/* Vehicle detail dialog */}
      <VehicleDetailDialog
        vehicle={selectedVehicle}
        open={detailOpen}
        onClose={handleDetailClose}
      />
    </div>
  );
}
