"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import { useSession } from "next-auth/react";
import { useTranslations } from "next-intl";
import { RefreshCw } from "lucide-react";
import { toast } from "sonner";
import dynamic from "next/dynamic";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { fetchFleetPositions } from "@/lib/fleet-sdk";
import type { VehiclePositionWithTelemetry } from "@/types/fleet";

const FleetMap = dynamic(
  () => import("@/components/fleet/fleet-map").then((m) => m.FleetMap),
  {
    ssr: false,
    loading: () => <Skeleton className="h-full w-full" />,
  },
);

const REFRESH_INTERVAL = 15_000;

export default function FleetMapPage() {
  const { status } = useSession();
  const t = useTranslations("fleet.map");

  const [positions, setPositions] = useState<VehiclePositionWithTelemetry[]>(
    [],
  );
  const [isLoading, setIsLoading] = useState(true);
  const [selectedDeviceId, setSelectedDeviceId] = useState<string | null>(null);
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const loadPositions = useCallback(async () => {
    try {
      const data = await fetchFleetPositions("fleet");
      setPositions(data);
      setLastRefresh(new Date());
    } catch {
      toast.error(t("noData"));
    } finally {
      setIsLoading(false);
    }
  }, [t]);

  useEffect(() => {
    if (status !== "authenticated") return;
    void loadPositions();
    intervalRef.current = setInterval(() => {
      void loadPositions();
    }, REFRESH_INTERVAL);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [loadPositions, status]);

  const handleRefresh = () => {
    setIsLoading(true);
    void loadPositions();
  };

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border px-(--spacing-page) py-(--spacing-card)">
        <div>
          <h1 className="text-lg font-heading font-semibold text-foreground">
            {t("title")}
          </h1>
          {lastRefresh && (
            <p className="text-xs text-foreground-subtle">
              {t("lastUpdate")}: {lastRefresh.toLocaleTimeString()}
            </p>
          )}
        </div>
        <Button
          variant="outline"
          size="sm"
          className="cursor-pointer"
          onClick={handleRefresh}
          disabled={isLoading}
        >
          <RefreshCw
            className={cn("mr-1 size-4", isLoading && "animate-spin")}
          />
          {t("title")}
        </Button>
      </div>

      {/* Content: sidebar + map */}
      <div className="flex flex-1 overflow-hidden">
        {/* Device sidebar */}
        <aside className="hidden md:flex w-56 shrink-0 flex-col border-r border-border overflow-y-auto">
          <div className="p-(--spacing-card) space-y-1">
            {positions.map((pos) => (
              <button
                key={pos.vehicle_id}
                type="button"
                onClick={() => setSelectedDeviceId(pos.vehicle_id)}
                className={cn(
                  "w-full text-left px-3 py-2 text-sm transition-colors cursor-pointer",
                  selectedDeviceId === pos.vehicle_id
                    ? "bg-nav-active-bg text-nav-active-text font-semibold"
                    : "text-foreground-muted hover:bg-nav-hover-bg hover:text-foreground",
                )}
              >
                <p className="font-mono text-xs truncate">{pos.vehicle_id}</p>
                {pos.speed_kmh !== null && (
                  <p className="text-xs text-foreground-subtle">
                    {pos.speed_kmh} km/h
                  </p>
                )}
              </button>
            ))}
            {positions.length === 0 && !isLoading && (
              <p className="px-3 py-2 text-xs text-foreground-subtle">
                {t("noDevices")}
              </p>
            )}
          </div>
        </aside>

        {/* Map */}
        <div className="flex-1 relative">
          {isLoading && positions.length === 0 ? (
            <div className="flex items-center justify-center h-full">
              <Skeleton className="h-full w-full" />
            </div>
          ) : (
            <FleetMap
              positions={positions}
              selectedDeviceId={selectedDeviceId}
              onSelectDevice={setSelectedDeviceId}
            />
          )}
          {/* Mobile device count badge */}
          <div className="md:hidden absolute bottom-3 left-3 z-[1000]">
            <Badge variant="outline" className="bg-surface/90 backdrop-blur-sm">
              {t("vehicles", { count: positions.length })}
            </Badge>
          </div>
        </div>
      </div>
    </div>
  );
}
