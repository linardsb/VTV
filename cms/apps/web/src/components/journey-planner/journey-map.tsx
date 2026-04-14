"use client";

import { useEffect } from "react";
import {
  MapContainer,
  TileLayer,
  Polyline,
  CircleMarker,
  Tooltip,
  useMap,
} from "react-leaflet";
import type { LatLngExpression } from "leaflet";
import "leaflet/dist/leaflet.css";
import type { JourneyItinerary, TransportMode } from "@/types/journey";

/** Decode a Google-encoded polyline string into [lat, lng] pairs. */
function decodePolyline(encoded: string): [number, number][] {
  const coords: [number, number][] = [];
  let index = 0;
  let lat = 0;
  let lng = 0;

  while (index < encoded.length) {
    let shift = 0;
    let result = 0;
    let byte: number;
    do {
      byte = encoded.charCodeAt(index++) - 63;
      result |= (byte & 0x1f) << shift;
      shift += 5;
    } while (byte >= 0x20);
    lat += result & 1 ? ~(result >> 1) : result >> 1;

    shift = 0;
    result = 0;
    do {
      byte = encoded.charCodeAt(index++) - 63;
      result |= (byte & 0x1f) << shift;
      shift += 5;
    } while (byte >= 0x20);
    lng += result & 1 ? ~(result >> 1) : result >> 1;

    coords.push([lat / 1e5, lng / 1e5]);
  }
  return coords;
}

/** Map transport mode to a polyline color (hex for Leaflet). */
function modeColor(mode: TransportMode): string {
  switch (mode) {
    case "BUS":
      return "#0391F2";
    case "TROLLEYBUS":
      return "#06757E";
    case "TRAM":
      return "#8E24AA";
    case "RAIL":
    case "SUBWAY":
      return "#43A047";
    case "WALK":
      return "#9E9E9E";
    case "BICYCLE":
      return "#FF9800";
    default:
      return "#757575";
  }
}

/** Auto-fit map bounds to the itinerary polylines. */
function FitBounds({ itinerary }: { itinerary: JourneyItinerary | null }) {
  const map = useMap();

  useEffect(() => {
    if (!itinerary) return;
    const allCoords: [number, number][] = [];
    for (const leg of itinerary.legs) {
      if (leg.polyline) {
        allCoords.push(...decodePolyline(leg.polyline));
      } else {
        allCoords.push([leg.from_lat, leg.from_lon]);
        allCoords.push([leg.to_lat, leg.to_lon]);
      }
    }
    if (allCoords.length > 0) {
      map.fitBounds(allCoords, { padding: [40, 40] });
    }
  }, [itinerary, map]);

  return null;
}

interface JourneyMapProps {
  itinerary: JourneyItinerary | null;
}

/** Default center: Riga. */
const DEFAULT_CENTER: LatLngExpression = [56.9496, 24.1052];

export function JourneyMap({ itinerary }: JourneyMapProps) {
  return (
    <MapContainer
      center={DEFAULT_CENTER}
      zoom={13}
      className="h-full w-full"
      scrollWheelZoom
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright" rel="noopener noreferrer">OSM</a>'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      <FitBounds itinerary={itinerary} />
      {itinerary?.legs.map((leg, i) => {
        const positions: LatLngExpression[] = leg.polyline
          ? decodePolyline(leg.polyline)
          : [
              [leg.from_lat, leg.from_lon],
              [leg.to_lat, leg.to_lon],
            ];
        const color = modeColor(leg.mode);
        const dashArray = leg.mode === "WALK" ? "6 8" : undefined;

        return (
          <Polyline
            key={i}
            positions={positions}
            pathOptions={{
              color,
              weight: leg.mode === "WALK" ? 3 : 5,
              opacity: 0.85,
              dashArray,
            }}
          />
        );
      })}
      {/* Origin marker */}
      {itinerary && itinerary.legs.length > 0 && (
        <CircleMarker
          center={[itinerary.legs[0].from_lat, itinerary.legs[0].from_lon]}
          radius={8}
          pathOptions={{ color: "#06757E", fillColor: "#06757E", fillOpacity: 1 }}
        >
          <Tooltip>{itinerary.legs[0].from_name}</Tooltip>
        </CircleMarker>
      )}
      {/* Destination marker */}
      {itinerary && itinerary.legs.length > 0 && (
        <CircleMarker
          center={[
            itinerary.legs[itinerary.legs.length - 1].to_lat,
            itinerary.legs[itinerary.legs.length - 1].to_lon,
          ]}
          radius={8}
          pathOptions={{ color: "#DD3039", fillColor: "#DD3039", fillOpacity: 1 }}
        >
          <Tooltip>
            {itinerary.legs[itinerary.legs.length - 1].to_name}
          </Tooltip>
        </CircleMarker>
      )}
    </MapContainer>
  );
}
