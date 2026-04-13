"use client";

import { useEffect, useMemo, useRef } from "react";
import "leaflet/dist/leaflet.css";
import "leaflet.markercluster/dist/MarkerCluster.css";
import "leaflet.markercluster/dist/MarkerCluster.Default.css";
import L from "leaflet";
import { MapContainer, TileLayer, Marker, useMap } from "react-leaflet";
import MarkerClusterGroup from "react-leaflet-cluster";
import { useTranslations } from "next-intl";
import type { BusPosition } from "@/types/route";
import type { GTFSFeed } from "@/types/gtfs";
import type { ConnectionMode } from "@/hooks/use-vehicle-positions";
import { FeedHealthOverlay } from "@/components/routes/feed-health-overlay";

interface VehicleMapProps {
  vehicles: BusPosition[];
  feeds: GTFSFeed[];
  feedColors: Record<string, string>;
  enabledFeedIds: Set<string>;
  selectedRouteType: number | null;
  connectionMode: ConnectionMode;
  onVehicleClick: (vehicle: BusPosition) => void;
}

/** Auto-fit bounds when vehicles change significantly. Module scope per React 19. */
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

/** Create a Leaflet divIcon for a bus marker. */
function createBusIcon(bus: BusPosition): L.DivIcon {
  const hasName = bus.routeShortName && bus.routeShortName.length > 0;
  const nameLen = bus.routeShortName?.length ?? 0;
  const size = 18;
  const w = hasName ? (nameLen > 2 ? 24 : 20) : size;
  const h = size;
  return L.divIcon({
    className: "",
    iconSize: [w, h],
    iconAnchor: [w / 2, h / 2],
    popupAnchor: [0, -h / 2],
    html: `<div style="
      min-width: ${w}px;
      height: ${h}px;
      border-radius: ${h / 2}px;
      background-color: ${bus.routeColor};
      color: white;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 9px;
      font-weight: 700;
      padding: 0 3px;
      box-shadow: 0 1px 3px rgba(0,0,0,0.3);
      transition: all 200ms ease;
      font-family: 'Source Sans 3', system-ui, sans-serif;
    ">${hasName ? bus.routeShortName : ""}</div>`,
  });
}

export function VehicleMap({
  vehicles,
  feeds,
  feedColors,
  enabledFeedIds,
  selectedRouteType,
  connectionMode,
  onVehicleClick,
}: VehicleMapProps) {
  const t = useTranslations("map");

  // Filter vehicles by enabled feeds and selected route type
  const filteredVehicles = useMemo(() => {
    let filtered = vehicles;
    if (enabledFeedIds.size < feeds.filter((f) => f.enabled).length) {
      filtered = filtered.filter((v) => enabledFeedIds.has(v.feedId));
    }
    if (selectedRouteType !== null) {
      filtered = filtered.filter((v) => {
        if (selectedRouteType === 0) {
          return v.routeType === 0 || (v.routeType >= 900 && v.routeType <= 999);
        }
        if (selectedRouteType === 11) {
          return v.routeType === 11 || (v.routeType >= 800 && v.routeType <= 899);
        }
        if (selectedRouteType === 3) {
          return v.routeType === 3 || (v.routeType >= 700 && v.routeType <= 799);
        }
        if (selectedRouteType === 2) {
          return v.routeType === 2 || (v.routeType >= 100 && v.routeType <= 199);
        }
        return v.routeType === selectedRouteType;
      });
    }
    return filtered;
  }, [vehicles, enabledFeedIds, selectedRouteType, feeds]);

  // Fit bounds trigger — changes when feed selection changes
  const fitBoundsTrigger = useMemo(
    () => Array.from(enabledFeedIds).sort().join(","),
    [enabledFeedIds],
  );

  const bounds = useMemo(() => {
    if (filteredVehicles.length === 0) return null;
    const lats = filteredVehicles.map((b) => b.latitude);
    const lngs = filteredVehicles.map((b) => b.longitude);
    return L.latLngBounds(
      [Math.min(...lats), Math.min(...lngs)],
      [Math.max(...lats), Math.max(...lngs)],
    );
  }, [filteredVehicles]);

  return (
    <div className="relative h-full w-full bg-surface">
      <MapContainer
        center={[56.9496, 24.1052]}
        zoom={8}
        className="h-full w-full"
        zoomControl={true}
        attributionControl={true}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright" rel="noopener noreferrer">OpenStreetMap</a> &copy; <a href="https://carto.com/" rel="noopener noreferrer">CARTO</a>'
          url="https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png"
          subdomains="abcd"
        />
        <FitBounds bounds={bounds} trigger={fitBoundsTrigger} />
        <MarkerClusterGroup
          maxClusterRadius={50}
          spiderfyOnMaxZoom={true}
          showCoverageOnHover={false}
          zoomToBoundsOnClick={true}
          chunkedLoading={true}
        >
          {filteredVehicles.map((v) => (
            <Marker
              key={v.vehicleId}
              position={[v.latitude, v.longitude]}
              icon={createBusIcon(v)}
              eventHandlers={{ click: () => onVehicleClick(v) }}
            />
          ))}
        </MarkerClusterGroup>
      </MapContainer>

      {/* Feed health overlay */}
      {feeds.length > 0 && (
        <FeedHealthOverlay
          feeds={feeds}
          vehicles={filteredVehicles}
          feedColors={feedColors}
        />
      )}

      {/* Empty state */}
      {filteredVehicles.length === 0 && connectionMode !== "connecting" && (
        <div className="absolute inset-0 z-[1000] flex items-center justify-center bg-surface/80">
          <p className="text-foreground-muted">{t("noData")}</p>
        </div>
      )}
    </div>
  );
}
