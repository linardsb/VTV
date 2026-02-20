"use client";

import { useState } from "react";
import "leaflet/dist/leaflet.css";
import { MapContainer, TileLayer } from "react-leaflet";
import { useTranslations } from "next-intl";
import type { BusPosition } from "@/types/route";
import { BusMarker } from "./bus-marker";

interface RouteMapProps {
  buses: BusPosition[];
  selectedRouteId: string | null;
  onSelectRoute: (routeId: string) => void;
}

export function RouteMap({ buses, selectedRouteId, onSelectRoute }: RouteMapProps) {
  const t = useTranslations("routes.map");
  const [mapInstance] = useState(() => `map-${Date.now()}`);
  return (
    <div className="relative h-full min-h-[50vh] w-full bg-surface">
      <div className="absolute left-3 top-3 z-[1000] rounded-md bg-surface/90 px-3 py-1.5 text-sm font-medium shadow-sm backdrop-blur-sm">
        {t("title")} - {buses.length} {t("vehicles")}
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
