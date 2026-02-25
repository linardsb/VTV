"use client";

import { useEffect, useMemo, useRef, useState } from "react";
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
  /** Opens the detail Sheet — called from popup "Details" button */
  onViewDetail?: (stop: Stop) => void;
  onEditStop?: (stop: Stop) => void;
  placementMode?: boolean;
  onMapClick?: (lat: number, lon: number) => void;
  editingStopId?: number | null;
  editingCoords?: { lat: number; lon: number } | null;
  onEditingCoordsChange?: (lat: number, lon: number) => void;
  /** "all" | "0" (stop) | "1" (station) | "terminal" — filters markers */
  locationTypeFilter?: string;
  /** Set of stop IDs that are terminals (last stop of a trip) */
  terminalStopIds?: Set<number>;
  /** Incremented when a table row is clicked — triggers the popup to open on the selected stop */
  popupTrigger?: number;
}

/**
 * Marker hex colors — must use raw hex because Leaflet renders via SVG/Canvas.
 * These correspond to semantic tokens in tokens.css:
 * - MARKER_BLUE = --color-interactive = --color-blue-600
 * - MARKER_GREEN = --color-stop-terminus = --color-emerald-500
 * - MARKER_DARK = --color-brand = --color-navy-800
 */
const MARKER_BLUE = "#0369A1";
const MARKER_GREEN = "#16a34a";
const MARKER_DARK = "#0F172A";

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
      animation: vtv-pulse 1.5s ease-in-out infinite;
    "></div>
    <style>
      @keyframes vtv-pulse {
        0%, 100% { box-shadow: 0 0 0 2px #0369A1, 0 4px 12px rgba(0,0,0,0.4); }
        50% { box-shadow: 0 0 0 6px rgba(3,105,161,0.3), 0 4px 12px rgba(0,0,0,0.4); }
      }
    </style>`,
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

/** Close all open popups when the edit button is clicked. */
function ClosePopupOnEdit({ trigger }: { trigger: number }) {
  const map = useMap();
  useEffect(() => {
    if (trigger > 0) {
      map.closePopup();
    }
  }, [map, trigger]);
  return null;
}

/** Opens the popup on the selected stop's CircleMarker after the fly animation completes. */
function OpenPopupForSelected({
  stops,
  selectedStopId,
  trigger,
}: {
  stops: Stop[];
  selectedStopId: number | null;
  trigger: number;
}) {
  const map = useMap();

  useEffect(() => {
    if (trigger === 0 || selectedStopId === null) return;

    const stop = stops.find((s) => s.id === selectedStopId);
    if (!stop || stop.stop_lat === null || stop.stop_lon === null) return;

    const targetLat = stop.stop_lat;
    const targetLon = stop.stop_lon;

    const openPopup = () => {
      map.eachLayer((layer) => {
        if (
          layer instanceof L.CircleMarker &&
          !(layer instanceof L.Circle)
        ) {
          const pos = layer.getLatLng();
          if (
            Math.abs(pos.lat - targetLat) < 0.00001 &&
            Math.abs(pos.lng - targetLon) < 0.00001
          ) {
            layer.openPopup();
          }
        }
      });
    };

    // Wait for fly animation to finish before opening popup
    map.once("moveend", openPopup);

    return () => {
      map.off("moveend", openPopup);
    };
  }, [map, stops, selectedStopId, trigger]);

  return null;
}

export function StopMap({
  stops,
  selectedStopId,
  onSelectStop,
  onViewDetail,
  onEditStop,
  placementMode = false,
  onMapClick,
  editingStopId,
  editingCoords,
  onEditingCoordsChange,
  locationTypeFilter = "all",
  terminalStopIds = new Set<number>(),
  popupTrigger = 0,
}: StopMapProps) {
  const t = useTranslations("stops.map");
  const [editTrigger, setEditTrigger] = useState(0);

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
    if (locationTypeFilter === "terminal") {
      return stopsWithCoords.filter((s) => terminalStopIds.has(s.id)).length;
    }
    const typeNum = Number(locationTypeFilter);
    return stopsWithCoords.filter((s) => s.location_type === typeNum).length;
  }, [stopsWithCoords, locationTypeFilter, terminalStopIds]);

  return (
    <div className="relative isolate h-full min-h-[50vh] w-full bg-surface">
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
        <OpenPopupForSelected stops={stops} selectedStopId={selectedStopId} trigger={popupTrigger} />
        <PlacementCursor active={placementMode} />
        <ClosePopupOnEdit trigger={editTrigger} />

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
          if (locationTypeFilter === "terminal") {
            if (!terminalStopIds.has(stop.id)) return null;
          } else if (
            locationTypeFilter !== "all" &&
            stop.location_type !== Number(locationTypeFilter)
          ) {
            return null;
          }

          const isSelected = selectedStopId === stop.id;
          const isTerminal = terminalStopIds.has(stop.id);

          return (
            <CircleMarker
              key={stop.id}
              center={[stop.stop_lat, stop.stop_lon]}
              radius={isSelected ? 8 : 6}
              pathOptions={{
                fillColor: isSelected
                  ? MARKER_DARK
                  : locationTypeFilter === "terminal" || isTerminal
                    ? MARKER_GREEN
                    : stop.location_type === 1
                      ? MARKER_GREEN
                      : MARKER_BLUE,
                color: "#FFFFFF",
                weight: 2,
                opacity: 1,
                fillOpacity: 0.9,
              }}
              eventHandlers={{
                click: () => {
                  /* Popup opens automatically — detail panel opens via buttons inside */
                },
              }}
            >
              <Popup closeButton={false}>
                <div className="text-sm min-w-[160px]">
                  <p className="font-semibold">{stop.stop_name}</p>
                  {stop.stop_desc && (
                    <p className="text-xs text-foreground-muted">{stop.stop_desc}</p>
                  )}
                  <p className="font-mono text-xs text-foreground-muted">
                    {stop.gtfs_stop_id}
                  </p>
                  <div className="mt-2 flex gap-1.5">
                    <button
                      type="button"
                      className="flex-1 rounded border border-border bg-surface px-2 py-1 text-xs font-medium hover:bg-surface-raised cursor-pointer"
                      onClick={(e) => {
                        e.stopPropagation();
                        setEditTrigger((n) => n + 1);
                        if (onViewDetail) {
                          onViewDetail(stop);
                        } else {
                          onSelectStop(stop);
                        }
                      }}
                    >
                      {t("details")}
                    </button>
                    {onEditStop && (
                      <button
                        type="button"
                        className="flex-1 rounded bg-primary px-2 py-1 text-xs font-medium text-primary-foreground hover:bg-primary/90 cursor-pointer"
                        onClick={(e) => {
                          e.stopPropagation();
                          setEditTrigger((n) => n + 1);
                          onEditStop(stop);
                        }}
                      >
                        {t("edit")}
                      </button>
                    )}
                  </div>
                </div>
              </Popup>
            </CircleMarker>
          );
        })}
      </MapContainer>

    </div>
  );
}
