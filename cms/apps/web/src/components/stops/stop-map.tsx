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
// Note: Marker is only used by EditingMarker (single draggable marker).
// Bulk stops use lightweight CircleMarker (SVG) to avoid DOM crash with 1600+ markers.
import { useTranslations } from "next-intl";
import type { Stop } from "@/types/stop";

interface StopMapProps {
  stops: Stop[];
  selectedStopId: number | null;
  onSelectStop: (stop: Stop) => void;
  onEditStop?: (stop: Stop) => void;
  placementMode?: boolean;
  onMapClick?: (lat: number, lon: number) => void;
  editingStopId?: number | null;
  editingCoords?: { lat: number; lon: number } | null;
  onEditingCoordsChange?: (lat: number, lon: number) => void;
  /** "all" | "0" (stop) | "1" (station) — grays out non-matching markers */
  locationTypeFilter?: string;
}

function createEditingIcon(): L.DivIcon {
  return L.divIcon({
    className: "",
    html: `<div style="
      width:24px;height:24px;
      border-radius:50%;
      background:#0369A1;
      border:3px solid white;
      box-shadow:0 0 0 2px #0369A1, 0 4px 12px rgba(0,0,0,0.4);
      cursor:grab;
    "></div>`,
    iconSize: [24, 24],
    iconAnchor: [12, 12],
  });
}

/** Watches for container resize and recalculates tile positions. */
function InvalidateSize() {
  const map = useMap();
  useEffect(() => {
    const container = map.getContainer();
    const observer = new ResizeObserver(() => {
      map.invalidateSize();
    });
    observer.observe(container);
    const timer = setTimeout(() => map.invalidateSize(), 200);
    return () => {
      observer.disconnect();
      clearTimeout(timer);
    };
  }, [map]);
  return null;
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

/** Imperatively zoom the map to editing coordinates at street level. */
function ZoomToEditing({
  coords,
  editingStopId,
}: {
  coords: { lat: number; lon: number } | null;
  editingStopId: number | null;
}) {
  const map = useMap();
  const hasZoomed = useRef(false);

  useEffect(() => {
    if (coords && !hasZoomed.current) {
      map.flyTo([coords.lat, coords.lon], 18, { duration: 0.8 });
      hasZoomed.current = true;
    }
    if (!coords && !editingStopId) {
      hasZoomed.current = false;
    }
  }, [map, coords, editingStopId]);

  return null;
}

/** Sets crosshair cursor directly on the Leaflet container when in placement mode. */
function PlacementCursor({ active }: { active: boolean }) {
  const map = useMap();
  useEffect(() => {
    const container = map.getContainer();
    if (active) {
      container.style.cursor = "crosshair";
    } else {
      container.style.cursor = "";
    }
    return () => {
      container.style.cursor = "";
    };
  }, [map, active]);
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

/** Draggable marker shown while the form is open for create/edit. */
function EditingMarker({
  coords,
  onDragEnd,
}: {
  coords: { lat: number; lon: number };
  onDragEnd: (lat: number, lon: number) => void;
}) {
  const icon = useMemo(() => createEditingIcon(), []);

  return (
    <Marker
      position={[coords.lat, coords.lon]}
      icon={icon}
      draggable={true}
      eventHandlers={{
        dragend: (e) => {
          const marker = e.target as L.Marker;
          const pos = marker.getLatLng();
          onDragEnd(pos.lat, pos.lng);
        },
      }}
    />
  );
}

export function StopMap({
  stops,
  selectedStopId,
  onSelectStop,
  onEditStop,
  placementMode = false,
  onMapClick,
  editingStopId,
  editingCoords,
  onEditingCoordsChange,
  locationTypeFilter = "all",
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

  const visibleStopCount = useMemo(() => {
    if (locationTypeFilter === "all") return stopsWithCoords.length;
    const typeNum = Number(locationTypeFilter);
    return stopsWithCoords.filter((s) => s.location_type === typeNum).length;
  }, [stopsWithCoords, locationTypeFilter]);

  return (
    <div className="relative h-full min-h-[50vh] w-full bg-surface">
      {/* Overlay label */}
      <div className="absolute left-3 top-3 z-[1000] rounded-md bg-surface/90 px-3 py-1.5 text-sm font-medium shadow-sm backdrop-blur-sm">
        {t("title")} - {visibleStopCount} {t("stops")}
      </div>

      {/* Placement mode hint */}
      {placementMode && (
        <div className="absolute left-1/2 top-3 z-[1000] -translate-x-1/2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow-lg">
          {t("placementHint")}
        </div>
      )}

      {/* Drag hint when editing */}
      {editingCoords && !placementMode && (
        <div className="absolute left-1/2 top-3 z-[1000] -translate-x-1/2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow-lg">
          {t("dragHint")}
        </div>
      )}

      <MapContainer
        center={[56.9496, 24.1052]}
        zoom={13}
        maxZoom={19}
        className="h-full w-full"
        zoomControl={true}
        attributionControl={true}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/">CARTO</a>'
          url="https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png"
          subdomains="abcd"
        />
        <InvalidateSize />
        <FlyToSelected stops={stops} selectedStopId={selectedStopId} />
        <PlacementCursor active={placementMode} />

        {onMapClick && (
          <MapClickHandler active={placementMode} onMapClick={onMapClick} />
        )}

        {/* Zoom to editing location */}
        {editingCoords && (
          <ZoomToEditing coords={editingCoords} editingStopId={editingStopId ?? null} />
        )}

        {/* Draggable editing marker (visible during form open) */}
        {editingCoords && onEditingCoordsChange && (
          <EditingMarker
            coords={editingCoords}
            onDragEnd={onEditingCoordsChange}
          />
        )}

        {/* All stops as lightweight SVG CircleMarkers (clickable, not draggable).
            Only the EditingMarker above is draggable — avoids 1600+ DOM Marker crash. */}
        {stopsWithCoords.map((stop) => {
          // Skip the stop being edited — it's rendered by EditingMarker above
          if (editingStopId === stop.id) return null;

          // Hide stops that don't match the active location type filter
          if (
            locationTypeFilter !== "all" &&
            stop.location_type !== Number(locationTypeFilter)
          ) {
            return null;
          }

          const isSelected = selectedStopId === stop.id;

          return (
            <CircleMarker
              key={stop.id}
              center={[stop.stop_lat, stop.stop_lon]}
              radius={isSelected ? 8 : 6}
              pathOptions={{
                fillColor: isSelected ? "#0F172A" : "#0369A1",
                color: "#FFFFFF",
                weight: 2,
                opacity: 1,
                fillOpacity: 0.9,
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
                  {onEditStop && (
                    <button
                      type="button"
                      className="mt-1.5 w-full rounded bg-primary px-2 py-1 text-xs font-medium text-primary-foreground hover:bg-primary/90"
                      onClick={(e) => {
                        e.stopPropagation();
                        onEditStop(stop);
                      }}
                    >
                      {t("edit")}
                    </button>
                  )}
                </div>
              </Popup>
            </CircleMarker>
          );
        })}
      </MapContainer>

    </div>
  );
}
