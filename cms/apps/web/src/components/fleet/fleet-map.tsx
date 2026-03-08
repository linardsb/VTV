"use client";

import { useMemo, useEffect, useRef, useId } from "react";
import "leaflet/dist/leaflet.css";
import L from "leaflet";
import { MapContainer, TileLayer, Marker, Popup, useMap } from "react-leaflet";
import { useTranslations } from "next-intl";
import type { VehiclePositionWithTelemetry } from "@/types/fleet";

interface FleetMapProps {
  positions: VehiclePositionWithTelemetry[];
  selectedDeviceId: string | null;
  onSelectDevice: (vehicleId: string) => void;
}

const STATUS_ICON_COLORS: Record<string, string> = {
  hardware: "#06757E",
  "gtfs-rt": "#0391F2",
};

function createDeviceIcon(source: string, isSelected: boolean): L.DivIcon {
  const color = STATUS_ICON_COLORS[source] ?? "#60607D";
  const size = isSelected ? 32 : 24;
  const anchor = size / 2;
  return L.divIcon({
    className: "",
    iconSize: [size, size],
    iconAnchor: [anchor, anchor],
    html: `<div style="width:${size}px;height:${size}px;border-radius:50%;background:${color};border:${isSelected ? 3 : 2}px solid white;box-shadow:0 2px 4px rgba(0,0,0,0.3);"></div>`,
  });
}

function FitBounds({
  bounds,
  trigger,
}: {
  bounds: L.LatLngBounds | null;
  trigger: string;
}) {
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

export function FleetMap({
  positions,
  selectedDeviceId,
  onSelectDevice,
}: FleetMapProps) {
  const t = useTranslations("fleet.map");

  const bounds = useMemo(() => {
    if (positions.length === 0) return null;
    const lats = positions.map((p) => p.latitude);
    const lngs = positions.map((p) => p.longitude);
    return L.latLngBounds(
      [Math.min(...lats), Math.min(...lngs)],
      [Math.max(...lats), Math.max(...lngs)],
    );
  }, [positions]);

  const mapId = useId();
  const boundsKey = useMemo(
    () => `fleet-${positions.length}-${mapId}`,
    [positions.length, mapId],
  );

  if (positions.length === 0) {
    return (
      <div className="flex flex-1 items-center justify-center bg-surface p-(--spacing-page)">
        <p className="text-sm text-foreground-muted">{t("noDevices")}</p>
      </div>
    );
  }

  return (
    <div className="relative isolate h-full min-h-[50vh] w-full bg-surface">
      <div className="absolute left-3 top-3 z-[1000] bg-surface/90 px-3 py-1.5 text-sm font-medium shadow-sm backdrop-blur-sm">
        {t("vehicles", { count: positions.length })}
      </div>

      <MapContainer
        center={[56.9496, 24.1052]}
        zoom={12}
        className="h-full w-full"
        zoomControl={false}
      >
        <TileLayer
          attribution='&copy; <a href="https://carto.com/">CARTO</a>'
          url="https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png"
        />
        <FitBounds bounds={bounds} trigger={boundsKey} />
        {positions.map((pos) => (
          <Marker
            key={pos.vehicle_id}
            position={[pos.latitude, pos.longitude]}
            icon={createDeviceIcon(pos.source, pos.vehicle_id === selectedDeviceId)}
            eventHandlers={{
              click: () => onSelectDevice(pos.vehicle_id),
            }}
          >
            <Popup>
              <div className="space-y-1 text-xs">
                <p className="font-semibold">{pos.vehicle_id}</p>
                {pos.speed_kmh !== null && (
                  <p>
                    {t("speed")}: {pos.speed_kmh} km/h
                  </p>
                )}
                <p>
                  {t("lastUpdate")}:{" "}
                  {new Date(pos.recorded_at).toLocaleTimeString()}
                </p>
              </div>
            </Popup>
          </Marker>
        ))}
      </MapContainer>
    </div>
  );
}
