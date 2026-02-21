"use client";

import { useMemo } from "react";
import { Marker, Popup } from "react-leaflet";
import L from "leaflet";
import { useTranslations } from "next-intl";
import type { BusPosition } from "@/types/route";

interface BusMarkerProps {
  bus: BusPosition;
  isHighlighted: boolean;
  isDimmed: boolean;
  onSelect: (routeId: string) => void;
}

function getDelayLabel(
  delaySeconds: number,
  t: ReturnType<typeof useTranslations>,
): { text: string; colorClass: string } {
  if (delaySeconds <= 0) {
    return {
      text: delaySeconds < 0 ? t("early") : t("onTime"),
      colorClass: "text-status-ontime",
    };
  }
  const minutes = Math.round(delaySeconds / 60);
  if (delaySeconds <= 300) {
    return {
      text: `${minutes} ${t("minutes")} ${t("late")}`,
      colorClass: "text-status-delayed",
    };
  }
  return {
    text: `${minutes} ${t("minutes")} ${t("late")}`,
    colorClass: "text-status-critical",
  };
}

export function BusMarker({ bus, isHighlighted, isDimmed, onSelect }: BusMarkerProps) {
  const t = useTranslations("routes.map");

  const icon = useMemo(() => {
    const size = isHighlighted ? 26 : 20;
    return L.divIcon({
      className: "",
      iconSize: [size, size],
      iconAnchor: [size / 2, size / 2],
      popupAnchor: [0, -size / 2],
      html: `<div style="
        width: ${size}px;
        height: ${size}px;
        border-radius: 50%;
        background-color: ${bus.routeColor};
        color: white;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: ${isHighlighted ? 10 : 8}px;
        font-weight: 700;
        border: 1.5px solid white;
        box-shadow: 0 1px 4px rgba(0,0,0,0.3);
        opacity: ${isDimmed ? 0.4 : 1};
        transition: all 200ms ease;
        font-family: 'Source Sans 3', system-ui, sans-serif;
      ">${bus.routeShortName}</div>`,
    });
  }, [bus.routeColor, bus.routeShortName, isHighlighted, isDimmed]);

  const delay = getDelayLabel(bus.delaySeconds, t);

  const eventHandlers = useMemo(
    () => ({
      click: () => {
        onSelect(bus.routeId);
      },
    }),
    [onSelect, bus.routeId],
  );

  return (
    <Marker
      position={[bus.latitude, bus.longitude]}
      icon={icon}
      eventHandlers={eventHandlers}
    >
      <Popup>
        <div className="min-w-[160px] p-(--spacing-card)">
          <div className="flex items-center gap-(--spacing-tight)">
            <span className="text-sm font-bold">{bus.routeShortName}</span>
            <span className="text-xs text-foreground-muted">{bus.vehicleId}</span>
          </div>
          <div className="mt-1">
            <span className={`text-xs font-medium ${delay.colorClass}`}>
              {delay.text}
            </span>
          </div>
          {bus.nextStopName && (
            <div className="mt-1 text-xs text-foreground-muted">
              {t("nextStop")}: {bus.nextStopName}
            </div>
          )}
        </div>
      </Popup>
    </Marker>
  );
}
