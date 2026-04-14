"use client";

import { useEffect, useMemo, useRef } from "react";
import "leaflet/dist/leaflet.css";
import L from "leaflet";
import { MapContainer, TileLayer, Marker, Popup, useMap } from "react-leaflet";
import type { ShareVehiclePosition } from "@/types/share";

const RIGA_CENTER: [number, number] = [56.9496, 24.1052];
const CARTO_TILE =
  "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png";
const CARTO_ATTR =
  '&copy; <a href="https://www.openstreetmap.org/copyright" rel="noopener noreferrer" target="_blank">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions" rel="noopener noreferrer" target="_blank">CARTO</a>';

interface ShareMapProps {
  position: ShareVehiclePosition | null;
}

function RecenterMap({ lat, lng }: { lat: number; lng: number }) {
  const map = useMap();
  const prevRef = useRef<string>("");

  useEffect(() => {
    const key = `${lat},${lng}`;
    if (key !== prevRef.current) {
      prevRef.current = key;
      map.setView([lat, lng], map.getZoom());
    }
  }, [map, lat, lng]);

  return null;
}

function buildVehicleIcon(
  routeShortName: string | null,
  bearing: number | null,
): L.DivIcon {
  const hasName = routeShortName && routeShortName.length > 0;
  const size = 24;
  const w = hasName ? (routeShortName.length > 2 ? 32 : 28) : size;
  return L.divIcon({
    className: "",
    iconSize: [w, size],
    iconAnchor: [w / 2, size / 2],
    popupAnchor: [0, -size / 2],
    html: `<div style="
      min-width: ${w}px;
      height: ${size}px;
      border-radius: ${size / 2}px;
      background-color: #0391F2;
      color: white;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 11px;
      font-weight: 700;
      padding: 0 4px;
      box-shadow: 0 2px 6px rgba(0,0,0,0.3);
      font-family: 'Source Sans 3', system-ui, sans-serif;
      ${bearing != null ? `transform: rotate(${bearing}deg);` : ""}
    ">${hasName ? routeShortName : "●"}</div>`,
  });
}

export function ShareMap({ position }: ShareMapProps) {
  const center: [number, number] = position
    ? [position.latitude, position.longitude]
    : RIGA_CENTER;

  const icon = useMemo(
    () =>
      position
        ? buildVehicleIcon(position.route_short_name, position.bearing)
        : null,
    [position],
  );

  return (
    <MapContainer
      center={center}
      zoom={15}
      className="h-full w-full"
      zoomControl={false}
    >
      <TileLayer url={CARTO_TILE} attribution={CARTO_ATTR} />
      {position && icon && (
        <>
          <Marker
            position={[position.latitude, position.longitude]}
            icon={icon}
          >
            <Popup>
              <div className="min-w-[140px] p-(--spacing-card)">
                {position.route_short_name && (
                  <span className="text-sm font-bold">
                    {position.route_short_name}
                  </span>
                )}
                <span className="ml-2 text-xs text-foreground-muted">
                  {position.vehicle_id}
                </span>
              </div>
            </Popup>
          </Marker>
          <RecenterMap lat={position.latitude} lng={position.longitude} />
        </>
      )}
    </MapContainer>
  );
}
