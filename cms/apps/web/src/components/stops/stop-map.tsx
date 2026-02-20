"use client";

import { useEffect, useMemo, useRef } from "react";
import "leaflet/dist/leaflet.css";
import L from "leaflet";
import {
  MapContainer,
  TileLayer,
  CircleMarker,
  Marker,
  Popup,
  useMap,
  useMapEvents,
} from "react-leaflet";
import { useTranslations } from "next-intl";
import type { Stop } from "@/types/stop";

interface StopMapProps {
  stops: Stop[];
  selectedStopId: number | null;
  onSelectStop: (stop: Stop) => void;
  editable?: boolean;
  onStopMoved?: (stopId: number, lat: number, lon: number) => void;
  placementMode?: boolean;
  onMapClick?: (lat: number, lon: number) => void;
}

function createDragIcon(selected: boolean): L.DivIcon {
  const size = selected ? 20 : 16;
  const color = selected ? "#0F172A" : "#0369A1";
  return L.divIcon({
    className: "",
    html: `<div style="
      width:${size}px;height:${size}px;
      border-radius:50%;
      background:${color};
      border:2px solid white;
      box-shadow:0 2px 6px rgba(0,0,0,0.3);
      cursor:grab;
    "></div>`,
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
  });
}

/** Imperatively fly the map to the selected stop (no setState). */
function FlyToSelected({
  stops,
  selectedStopId,
}: {
  stops: Stop[];
  selectedStopId: number | null;
}) {
  const map = useMap();
  const prevSelectedId = useRef<number | null>(null);

  useEffect(() => {
    if (selectedStopId !== null && selectedStopId !== prevSelectedId.current) {
      const stop = stops.find((s) => s.id === selectedStopId);
      if (stop?.stop_lat !== null && stop?.stop_lon !== null && stop) {
        map.flyTo([stop.stop_lat, stop.stop_lon], 15, { duration: 0.8 });
      }
    }
    prevSelectedId.current = selectedStopId;
  }, [map, stops, selectedStopId]);

  return null;
}

/** Handles click-to-place when in placement mode. */
function MapClickHandler({
  active,
  onMapClick,
}: {
  active: boolean;
  onMapClick: (lat: number, lon: number) => void;
}) {
  useMapEvents({
    click(e) {
      if (active) {
        onMapClick(e.latlng.lat, e.latlng.lng);
      }
    },
  });
  return null;
}

export function StopMap({
  stops,
  selectedStopId,
  onSelectStop,
  editable = false,
  onStopMoved,
  placementMode = false,
  onMapClick,
}: StopMapProps) {
  const t = useTranslations("stops.map");

  const stopsWithCoords = useMemo(
    () =>
      stops.filter(
        (s): s is Stop & { stop_lat: number; stop_lon: number } =>
          s.stop_lat !== null && s.stop_lon !== null,
      ),
    [stops],
  );

  const dragIconSelected = useMemo(() => createDragIcon(true), []);
  const dragIconNormal = useMemo(() => createDragIcon(false), []);

  return (
    <div className="relative h-full min-h-[50vh] w-full bg-surface">
      {/* Overlay label */}
      <div className="absolute left-3 top-3 z-[1000] rounded-md bg-surface/90 px-3 py-1.5 text-sm font-medium shadow-sm backdrop-blur-sm">
        {t("title")} - {stopsWithCoords.length} {t("stops")}
      </div>

      {/* Placement mode hint */}
      {placementMode && (
        <div className="absolute left-1/2 top-3 z-[1000] -translate-x-1/2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow-lg">
          {t("placementHint")}
        </div>
      )}

      <MapContainer
        center={[56.9496, 24.1052]}
        zoom={12}
        className={`h-full w-full ${placementMode ? "cursor-crosshair" : ""}`}
        zoomControl={true}
        attributionControl={true}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <FlyToSelected stops={stops} selectedStopId={selectedStopId} />

        {onMapClick && (
          <MapClickHandler active={placementMode} onMapClick={onMapClick} />
        )}

        {stopsWithCoords.map((stop) => {
          const isSelected = selectedStopId === stop.id;

          // Editable mode: render draggable Markers
          if (editable && onStopMoved) {
            return (
              <Marker
                key={stop.id}
                position={[stop.stop_lat, stop.stop_lon]}
                icon={isSelected ? dragIconSelected : dragIconNormal}
                draggable={true}
                eventHandlers={{
                  click: () => onSelectStop(stop),
                  dragend: (e) => {
                    const marker = e.target as L.Marker;
                    const pos = marker.getLatLng();
                    onStopMoved(stop.id, pos.lat, pos.lng);
                  },
                }}
              >
                <Popup>
                  <div className="text-sm">
                    <p className="font-semibold">{stop.stop_name}</p>
                    <p className="font-mono text-xs text-foreground-muted">
                      {stop.gtfs_stop_id}
                    </p>
                  </div>
                </Popup>
              </Marker>
            );
          }

          // Read-only mode: CircleMarkers
          return (
            <CircleMarker
              key={stop.id}
              center={[stop.stop_lat, stop.stop_lon]}
              radius={isSelected ? 8 : 6}
              pathOptions={{
                fillColor: isSelected ? "#0F172A" : "#0369A1",
                color: isSelected ? "#0F172A" : "#0369A1",
                weight: isSelected ? 2 : 1,
                opacity: 1,
                fillOpacity: 0.8,
              }}
              eventHandlers={{
                click: () => onSelectStop(stop),
              }}
            >
              <Popup>
                <div className="text-sm">
                  <p className="font-semibold">{stop.stop_name}</p>
                  <p className="font-mono text-xs text-foreground-muted">
                    {stop.gtfs_stop_id}
                  </p>
                </div>
              </Popup>
            </CircleMarker>
          );
        })}
      </MapContainer>

      {stopsWithCoords.length === 0 && !placementMode && (
        <div className="absolute inset-0 z-[1000] flex items-center justify-center bg-surface/80">
          <p className="text-foreground-muted">{t("noData")}</p>
        </div>
      )}
    </div>
  );
}
