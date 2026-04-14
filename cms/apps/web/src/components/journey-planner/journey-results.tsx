"use client";

import { useTranslations } from "next-intl";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { JourneyItinerary, JourneyLeg, TransportMode } from "@/types/journey";

/** Map transport mode to semantic color classes. */
function modeBgClass(mode: TransportMode): string {
  switch (mode) {
    case "BUS":
      return "bg-transport-bus text-transport-bus-foreground";
    case "TROLLEYBUS":
      return "bg-transport-trolleybus text-transport-trolleybus-foreground";
    case "TRAM":
      return "bg-transport-tram text-transport-tram-foreground";
    case "RAIL":
    case "SUBWAY":
      return "bg-interactive text-interactive-foreground";
    case "WALK":
      return "bg-surface-secondary text-foreground";
    case "BICYCLE":
      return "bg-status-ontime text-status-ontime-foreground";
    default:
      return "bg-muted text-foreground-muted";
  }
}

function formatDuration(
  seconds: number,
  units: { min: string; h: string; m: string },
): string {
  const mins = Math.round(seconds / 60);
  if (mins < 60) return `${mins} ${units.min}`;
  const hrs = Math.floor(mins / 60);
  const rem = mins % 60;
  return rem > 0 ? `${hrs}${units.h} ${rem}${units.m}` : `${hrs}${units.h}`;
}

function formatTime(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function formatDistance(
  meters: number,
  units: { m: string; km: string },
): string {
  if (meters < 1000) return `${Math.round(meters)} ${units.m}`;
  return `${(meters / 1000).toFixed(1)} ${units.km}`;
}

function LegBadge({ leg }: { leg: JourneyLeg }) {
  const t = useTranslations("journeyPlanner.modes");
  const modeKey = leg.mode.toLowerCase();

  return (
    <Badge
      variant="secondary"
      className={cn("text-xs font-medium", modeBgClass(leg.mode))}
    >
      {leg.route_short_name ?? t(modeKey)}
    </Badge>
  );
}

function LegDetail({ leg }: { leg: JourneyLeg }) {
  const t = useTranslations("journeyPlanner");

  return (
    <div className="flex items-center gap-(--spacing-inline) text-xs text-foreground-muted">
      <LegBadge leg={leg} />
      <span>{formatTime(leg.start_time)}</span>
      <span className="text-foreground-subtle">→</span>
      <span>{formatTime(leg.end_time)}</span>
      <span className="text-foreground-subtle">
        ({formatDuration(leg.duration_seconds, { min: t("unitMin"), h: t("unitH"), m: t("unitM") })})
      </span>
      {leg.realtime_delay_seconds != null && leg.realtime_delay_seconds > 0 && (
        <span className="text-error">
          +{Math.round(leg.realtime_delay_seconds / 60)} {t("delayMin")}
        </span>
      )}
    </div>
  );
}

interface ItineraryCardProps {
  itinerary: JourneyItinerary;
  index: number;
  selected: boolean;
  onSelect: (index: number) => void;
}

function ItineraryCard({
  itinerary,
  index,
  selected,
  onSelect,
}: ItineraryCardProps) {
  const t = useTranslations("journeyPlanner");

  return (
    <button
      type="button"
      onClick={() => onSelect(index)}
      className={cn(
        "w-full cursor-pointer border p-(--spacing-card) text-left transition-colors",
        selected
          ? "border-interactive bg-surface"
          : "border-border bg-surface hover:border-interactive/50",
      )}
    >
      {/* Summary row */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-(--spacing-inline)">
          <span className="text-sm font-semibold text-foreground">
            {formatTime(itinerary.start_time)}
          </span>
          <span className="text-foreground-subtle">→</span>
          <span className="text-sm font-semibold text-foreground">
            {formatTime(itinerary.end_time)}
          </span>
        </div>
        <span className="text-sm font-medium text-foreground">
          {formatDuration(itinerary.duration_seconds, { min: t("unitMin"), h: t("unitH"), m: t("unitM") })}
        </span>
      </div>

      {/* Mode badges */}
      <div className="mt-(--spacing-tight) flex flex-wrap items-center gap-(--spacing-tight)">
        {itinerary.legs.map((leg, i) => (
          <LegBadge key={i} leg={leg} />
        ))}
      </div>

      {/* Meta row */}
      <div className="mt-(--spacing-tight) flex gap-(--spacing-inline) text-xs text-foreground-muted">
        {itinerary.transfers > 0 && (
          <span>
            {itinerary.transfers}{" "}
            {itinerary.transfers === 1 ? t("transfer") : t("transfers")}
          </span>
        )}
        <span>
          {t("walk")}: {formatDistance(itinerary.walk_distance_m, { m: t("unitMeters"), km: t("unitKm") })}
        </span>
      </div>

      {/* Expanded leg details */}
      {selected && (
        <div className="mt-(--spacing-card) space-y-(--spacing-tight) border-t border-border pt-(--spacing-card)">
          {itinerary.legs.map((leg, i) => (
            <div key={i} className="space-y-0.5">
              <LegDetail leg={leg} />
              <div className="pl-6 text-xs text-foreground-subtle">
                {leg.from_name} → {leg.to_name}
                {leg.num_stops != null && (
                  <span>
                    {" "}
                    · {leg.num_stops} {t("stops")}
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </button>
  );
}

interface JourneyResultsProps {
  itineraries: JourneyItinerary[];
  selectedIndex: number;
  onSelect: (index: number) => void;
}

export function JourneyResults({
  itineraries,
  selectedIndex,
  onSelect,
}: JourneyResultsProps) {
  const t = useTranslations("journeyPlanner");

  if (itineraries.length === 0) {
    return (
      <p className="py-(--spacing-lg) text-center text-sm text-foreground-muted">
        {t("noResults")}
      </p>
    );
  }

  return (
    <div className="space-y-(--spacing-tight)">
      <h3 className="text-sm font-semibold text-foreground">
        {t("itineraries")} ({itineraries.length})
      </h3>
      {itineraries.map((it, i) => (
        <ItineraryCard
          key={i}
          itinerary={it}
          index={i}
          selected={i === selectedIndex}
          onSelect={onSelect}
        />
      ))}
    </div>
  );
}
