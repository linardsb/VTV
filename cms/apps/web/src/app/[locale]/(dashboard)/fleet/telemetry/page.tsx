"use client";

import { useState, useCallback, useEffect } from "react";
import { useSession } from "next-auth/react";
import { useTranslations } from "next-intl";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { TelemetryDashboard } from "@/components/fleet/telemetry-dashboard";
import { fetchDevices, fetchVehicleHistory } from "@/lib/fleet-sdk";
import type {
  TrackedDevice,
  TelemetryHistoryPoint,
} from "@/types/fleet";

type TimeRange = "1h" | "6h" | "24h";

const TIME_RANGE_MS: Record<TimeRange, number> = {
  "1h": 3600_000,
  "6h": 21600_000,
  "24h": 86400_000,
};

export default function TelemetryPage() {
  const { status } = useSession();
  const t = useTranslations("fleet.telemetry");

  const [devices, setDevices] = useState<TrackedDevice[]>([]);
  const [selectedDeviceId, setSelectedDeviceId] = useState<string>("");
  const [timeRange, setTimeRange] = useState<TimeRange>("1h");
  const [telemetryData, setTelemetryData] = useState<TelemetryHistoryPoint[]>(
    [],
  );
  const [isLoading, setIsLoading] = useState(false);
  const [devicesLoaded, setDevicesLoaded] = useState(false);

  // Load device list
  const loadDeviceList = useCallback(async () => {
    try {
      const result = await fetchDevices({ page: 1, page_size: 100 });
      setDevices(result.items);
      setDevicesLoaded(true);
    } catch {
      toast.error(t("loadError"));
    }
  }, [t]);

  useEffect(() => {
    if (status !== "authenticated") return;
    void loadDeviceList();
  }, [loadDeviceList, status]);

  // Load telemetry when device or time range changes
  const loadTelemetry = useCallback(async () => {
    if (!selectedDeviceId) return;
    setIsLoading(true);
    try {
      const now = new Date();
      const from = new Date(now.getTime() - TIME_RANGE_MS[timeRange]);
      const data = await fetchVehicleHistory(
        selectedDeviceId,
        from.toISOString(),
        now.toISOString(),
        500,
      );
      setTelemetryData(data);
    } catch {
      toast.error(t("loadError"));
    } finally {
      setIsLoading(false);
    }
  }, [selectedDeviceId, timeRange, t]);

  useEffect(() => {
    if (status !== "authenticated" || !selectedDeviceId) return;
    void loadTelemetry();
  }, [loadTelemetry, status, selectedDeviceId]);

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="border-b border-border px-(--spacing-page) py-(--spacing-card)">
        <h1 className="text-lg font-heading font-semibold text-foreground">
          {t("title")}
        </h1>
        <p className="text-sm text-foreground-muted">{t("description")}</p>
      </div>

      {/* Controls */}
      <div className="flex flex-wrap items-center gap-(--spacing-card) border-b border-border px-(--spacing-page) py-(--spacing-card)">
        <div className="flex-1 min-w-[200px] max-w-[300px]">
          <p className="text-xs font-medium text-foreground-muted uppercase tracking-wide mb-1">
            {t("selectDevice")}
          </p>
          <Select
            value={selectedDeviceId}
            onValueChange={setSelectedDeviceId}
          >
            <SelectTrigger aria-label={t("selectDevice")}>
              <SelectValue placeholder={t("selectDevice")} />
            </SelectTrigger>
            <SelectContent>
              {devices.map((device) => (
                <SelectItem
                  key={device.id}
                  value={device.vehicle_id ? String(device.vehicle_id) : device.imei}
                >
                  {device.device_name ?? device.imei}
                  {device.vehicle_id
                    ? ` (Vehicle ${device.vehicle_id})`
                    : ""}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div>
          <p className="text-xs font-medium text-foreground-muted uppercase tracking-wide mb-1">
            {t("timeRange")}
          </p>
          <div className="flex gap-1">
            {(["1h", "6h", "24h"] as TimeRange[]).map((range) => (
              <Button
                key={range}
                variant={timeRange === range ? "default" : "outline"}
                size="sm"
                className={cn("cursor-pointer", timeRange === range && "pointer-events-none")}
                onClick={() => setTimeRange(range)}
              >
                {t(`last${range.replace("h", "")}h` as "last1h" | "last6h" | "last24h")}
              </Button>
            ))}
          </div>
        </div>
      </div>

      {/* Dashboard */}
      <div className="flex-1 overflow-auto p-(--spacing-page)">
        {!selectedDeviceId && devicesLoaded ? (
          <div className="flex items-center justify-center h-full">
            <p className="text-sm text-foreground-muted">{t("selectDevice")}</p>
          </div>
        ) : (
          <TelemetryDashboard data={telemetryData} isLoading={isLoading} />
        )}
      </div>
    </div>
  );
}
