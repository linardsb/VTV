"use client";

import { useMemo, useEffect, useRef, useCallback } from "react";
import "leaflet/dist/leaflet.css";
import L from "leaflet";
import {
  MapContainer,
  TileLayer,
  Polygon,
  Marker,
  Popup,
  useMap,
  useMapEvents,
} from "react-leaflet";
import { useTranslations } from "next-intl";
import type { Geofence } from "@/types/geofence";

interface GeofenceMapProps {
  geofences: Geofence[];
  selectedGeofenceId: number | null;
  onSelectGeofence: (id: number) => void;
  editMode?: boolean;
  editCoordinates?: number[][];
  onCoordinatesChange?: (coords: number[][]) => void;
}

const ZONE_COLORS: Record<string, string> = {
  depot: "#0391F2",
  terminal: "#06757E",
  restricted: "#DD3039",
  customer: "#D4A017",
  custom: "#60607D",
};

const vertexIcon = L.divIcon({
  className: "",
  iconSize: [12, 12],
  iconAnchor: [6, 6],
  html: '<div style="width:12px;height:12px;background:#0391F2;border:2px solid white;box-shadow:0 1px 3px rgba(0,0,0,0.3);"></div>',
});

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

function EditClickHandler({
  onAddPoint,
}: {
  onAddPoint: (lat: number, lng: number) => void;
}) {
  useMapEvents({
    click: (e) => {
      onAddPoint(e.latlng.lat, e.latlng.lng);
    },
  });
  return null;
}

/** Convert [lon, lat] backend coords to [lat, lng] Leaflet coords */
function toLatLng(coords: number[][]): L.LatLngExpression[] {
  return coords.map(([lon, lat]) => [lat, lon] as L.LatLngExpression);
}

export function GeofenceMap({
  geofences,
  selectedGeofenceId,
  onSelectGeofence,
  editMode = false,
  editCoordinates,
  onCoordinatesChange,
}: GeofenceMapProps) {
  const t = useTranslations("geofences.map");

  const allCoords = useMemo(() => {
    const coords: L.LatLng[] = [];
    for (const g of geofences) {
      for (const [lon, lat] of g.coordinates) {
        coords.push(L.latLng(lat, lon));
      }
    }
    return coords;
  }, [geofences]);

  const bounds = useMemo(() => {
    if (allCoords.length === 0) return null;
    return L.latLngBounds(allCoords);
  }, [allCoords]);

  const boundsKey = useMemo(
    () => `gf-${geofences.length}-${selectedGeofenceId}`,
    [geofences.length, selectedGeofenceId],
  );

  const handleAddPoint = useCallback(
    (lat: number, lng: number) => {
      if (!editMode || !onCoordinatesChange) return;
      const current = editCoordinates ?? [];
      // Store as [lon, lat] for backend compatibility
      onCoordinatesChange([...current, [lng, lat]]);
    },
    [editMode, editCoordinates, onCoordinatesChange],
  );

  const editLatLngs = useMemo(() => {
    if (!editCoordinates || editCoordinates.length === 0) return [];
    return toLatLng(editCoordinates);
  }, [editCoordinates]);

  return (
    <div className="relative isolate h-full min-h-[300px] w-full bg-surface">
      {editMode && (
        <div className="absolute left-3 top-3 z-[1000] bg-surface/90 px-3 py-1.5 text-xs font-medium shadow-sm backdrop-blur-sm">
          {editCoordinates && editCoordinates.length >= 3
            ? t("polygonComplete")
            : t("clickToPlace")}
        </div>
      )}

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

        {/* Display existing geofences */}
        {geofences.map((geofence) => {
          const color =
            geofence.color ?? ZONE_COLORS[geofence.zone_type] ?? "#60607D";
          const isSelected = geofence.id === selectedGeofenceId;
          return (
            <Polygon
              key={geofence.id}
              positions={toLatLng(geofence.coordinates)}
              pathOptions={{
                color,
                fillColor: color,
                fillOpacity: isSelected ? 0.35 : 0.2,
                weight: isSelected ? 3 : 2,
              }}
              eventHandlers={{
                click: () => onSelectGeofence(geofence.id),
              }}
            >
              <Popup>
                <div className="text-xs space-y-1">
                  <p className="font-semibold">{geofence.name}</p>
                  <p>{geofence.zone_type}</p>
                </div>
              </Popup>
            </Polygon>
          );
        })}

        {/* Edit mode: drawing polygon */}
        {editMode && (
          <>
            <EditClickHandler onAddPoint={handleAddPoint} />
            {editLatLngs.length >= 3 && (
              <Polygon
                positions={editLatLngs}
                pathOptions={{
                  color: "#0391F2",
                  fillColor: "#0391F2",
                  fillOpacity: 0.2,
                  weight: 2,
                  dashArray: "5 5",
                }}
              />
            )}
            {editCoordinates?.map(([lon, lat], idx) => (
              <Marker
                key={`vertex-${idx}`}
                position={[lat, lon]}
                icon={vertexIcon}
              />
            ))}
          </>
        )}
      </MapContainer>
    </div>
  );
}
