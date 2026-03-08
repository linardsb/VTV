"use client";

import { useState, useEffect, useMemo, useRef } from "react";
import "leaflet/dist/leaflet.css";
import L from "leaflet";
import { MapContainer, TileLayer, useMap } from "react-leaflet";
import { useTranslations } from "next-intl";
import type { BusPosition } from "@/types/route";
import type { GTFSFeed } from "@/types/gtfs";
import type { ConnectionMode } from "@/hooks/use-vehicle-positions";
import { BusMarker } from "./bus-marker";
import { FeedHealthOverlay } from "./feed-health-overlay";

interface RouteMapProps {
  buses: BusPosition[];
  selectedRouteId: string | null;
  onSelectRoute: (routeId: string) => void;
  connectionMode?: ConnectionMode;
  feeds?: GTFSFeed[];
  feedColors?: Record<string, string>;
  feedSelectionKey?: string;
}

/** Auto-fit map bounds when feed selection changes. Defined at module scope per React 19 rules. */
function FitBounds({ bounds, trigger }: { bounds: L.LatLngBounds | null; trigger: string }) {
  const map = useMap();
  const prevTriggerRef = useRef(trigger);

  useEffect(() => {
    if (trigger !== prevTriggerRef.current && bounds && bounds.isValid()) {
      prevTriggerRef.current = trigger;
      map.fitBounds(bounds, { padding: [40, 40], maxZoom: 14 });
    }
  }, [map, bounds, trigger]);

  return null;
}

export function RouteMap({ buses, selectedRouteId, onSelectRoute, connectionMode = "connecting", feeds, feedColors, feedSelectionKey }: RouteMapProps) {
  const t = useTranslations("routes.map");
  const [mapInstance] = useState(() => `map-${Date.now()}`);

  const bounds = useMemo(() => {
    if (buses.length === 0) return null;
    const lats = buses.map((b) => b.latitude);
    const lngs = buses.map((b) => b.longitude);
    return L.latLngBounds(
      [Math.min(...lats), Math.min(...lngs)],
      [Math.max(...lats), Math.max(...lngs)],
    );
  }, [buses]);

  return (
    <div className="relative isolate h-full min-h-[50vh] w-full bg-surface">
      <div className="absolute left-12 top-3 z-[1000] rounded-md bg-surface/90 px-3 py-1.5 text-sm font-medium shadow-sm backdrop-blur-sm">
        {t("title")} - {buses.length} {t("vehicles")}
      </div>

      {/* Connection status badge — top right */}
      <div className="absolute right-3 top-3 z-[1000] flex items-center gap-(--spacing-tight) rounded-md bg-surface/90 px-2 py-1 text-xs shadow-sm backdrop-blur-sm transition-all duration-200">
        <span
          className={`inline-block size-2 rounded-full ${
            connectionMode === "ws"
              ? "bg-status-ontime"
              : connectionMode === "polling"
                ? "bg-status-delayed"
                : "animate-pulse bg-status-delayed"
          }`}
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

      <MapContainer
        key={mapInstance}
        center={[56.9496, 24.1052]}
        zoom={13}
        className="h-full w-full"
        zoomControl={true}
        attributionControl={true}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/">CARTO</a>'
          url="https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png"
          subdomains="abcd"
        />
        <FitBounds bounds={bounds} trigger={feedSelectionKey ?? ""} />
        {buses.map((bus) => (
          <BusMarker
            key={bus.vehicleId}
            bus={bus}
            isHighlighted={selectedRouteId === bus.routeId}
            isDimmed={false}
            onSelect={onSelectRoute}
            feedBorderColor={feedColors?.[bus.feedId]}
          />
        ))}
      </MapContainer>

      {/* Feed health overlay */}
      {feeds && feeds.length > 0 && (
        <FeedHealthOverlay
          feeds={feeds}
          vehicles={buses}
          feedColors={feedColors ?? {}}
        />
      )}

      {buses.length === 0 && (
        <div className="absolute inset-0 z-[1000] flex items-center justify-center bg-surface/80">
          <p className="text-foreground-muted">{t("noData")}</p>
        </div>
      )}
    </div>
  );
}
