"use client";

import { useState } from "react";
import "leaflet/dist/leaflet.css";
import { MapContainer, TileLayer } from "react-leaflet";
import { useTranslations } from "next-intl";
import type { BusPosition } from "@/types/route";
import type { ConnectionMode } from "@/hooks/use-vehicle-positions";
import { BusMarker } from "./bus-marker";

interface RouteMapProps {
  buses: BusPosition[];
  selectedRouteId: string | null;
  onSelectRoute: (routeId: string) => void;
  connectionMode?: ConnectionMode;
}

export function RouteMap({ buses, selectedRouteId, onSelectRoute, connectionMode = "connecting" }: RouteMapProps) {
  const t = useTranslations("routes.map");
  const [mapInstance] = useState(() => `map-${Date.now()}`);
  return (
    <div className="relative isolate h-full min-h-[50vh] w-full bg-surface">
      <div className="absolute left-3 top-3 z-[1000] rounded-md bg-surface/90 px-3 py-1.5 text-sm font-medium shadow-sm backdrop-blur-sm">
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
        {buses.map((bus) => (
          <BusMarker
            key={bus.vehicleId}
            bus={bus}
            isHighlighted={selectedRouteId === bus.routeId}
            isDimmed={false}
            onSelect={onSelectRoute}
          />
        ))}
      </MapContainer>

      {buses.length === 0 && (
        <div className="absolute inset-0 z-[1000] flex items-center justify-center bg-surface/80">
          <p className="text-foreground-muted">{t("noData")}</p>
        </div>
      )}
    </div>
  );
}
