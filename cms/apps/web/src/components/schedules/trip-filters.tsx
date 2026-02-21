"use client";

import { useTranslations } from "next-intl";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { RouteTypeBadge } from "@/components/routes/route-type-badge";
import type { Route } from "@/types/route";
import type { Calendar } from "@/types/schedule";

interface TripFiltersProps {
  routes: Route[];
  calendars: Calendar[];
  routeFilter: number | null;
  onRouteFilterChange: (routeId: number | null) => void;
  calendarFilter: number | null;
  onCalendarFilterChange: (calendarId: number | null) => void;
  directionFilter: number | null;
  onDirectionFilterChange: (direction: number | null) => void;
}

export function TripFilters({
  routes,
  calendars,
  routeFilter,
  onRouteFilterChange,
  calendarFilter,
  onCalendarFilterChange,
  directionFilter,
  onDirectionFilterChange,
}: TripFiltersProps) {
  const t = useTranslations("schedules.trips");

  return (
    <div className="flex flex-wrap items-center gap-(--spacing-inline)">
      {/* Route filter */}
      <Select
        value={routeFilter === null ? "all" : String(routeFilter)}
        onValueChange={(v) => onRouteFilterChange(v === "all" ? null : Number(v))}
      >
        <SelectTrigger className="w-40" aria-label={t("route")}>
          <SelectValue placeholder={t("allRoutes")} />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">{t("allRoutes")}</SelectItem>
          {routes.map((r) => (
            <SelectItem key={r.id} value={String(r.id)}>
              <span className="flex items-center gap-(--spacing-tight)">
                {r.route_short_name} - {r.route_long_name}
                <RouteTypeBadge type={r.route_type} className="ml-auto text-[10px] py-0 px-1" />
              </span>
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      {/* Calendar filter */}
      <Select
        value={calendarFilter === null ? "all" : String(calendarFilter)}
        onValueChange={(v) => onCalendarFilterChange(v === "all" ? null : Number(v))}
      >
        <SelectTrigger className="w-40" aria-label={t("calendar")}>
          <SelectValue placeholder={t("allCalendars")} />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">{t("allCalendars")}</SelectItem>
          {calendars.map((c) => (
            <SelectItem key={c.id} value={String(c.id)}>
              {c.gtfs_service_id}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      {/* Direction filter */}
      <Select
        value={directionFilter === null ? "all" : String(directionFilter)}
        onValueChange={(v) => onDirectionFilterChange(v === "all" ? null : Number(v))}
      >
        <SelectTrigger className="w-36" aria-label={t("direction")}>
          <SelectValue placeholder={t("allDirections")} />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">{t("allDirections")}</SelectItem>
          <SelectItem value="0">{t("outbound")}</SelectItem>
          <SelectItem value="1">{t("inbound")}</SelectItem>
        </SelectContent>
      </Select>
    </div>
  );
}
