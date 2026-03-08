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
  /** Hex color for feed differentiation border ring. */
  feedBorderColor?: string;
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
    const hasName = bus.routeShortName && bus.routeShortName.length > 0;
    const nameLen = bus.routeShortName?.length ?? 0;
    const size = isHighlighted ? 22 : 18;
    const w = hasName ? (isHighlighted ? (nameLen > 2 ? 28 : 24) : (nameLen > 2 ? 24 : 20)) : size;
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
        font-size: ${isHighlighted ? 10 : 9}px;
        font-weight: 700;
        padding: 0 3px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.3);
        opacity: ${isDimmed ? 0.4 : 1};
        transition: all 200ms ease;
        font-family: 'Source Sans 3', system-ui, sans-serif;
      ">${hasName ? bus.routeShortName : ''}</div>`,
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
