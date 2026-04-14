"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

/** Latvia bounding box for coordinate validation. */
const LAT_MIN = 55.5;
const LAT_MAX = 58.1;
const LON_MIN = 20.5;
const LON_MAX = 28.3;

interface JourneyFormProps {
  onSubmit: (params: {
    from_lat: number;
    from_lon: number;
    to_lat: number;
    to_lon: number;
    depart_at?: string;
  }) => void;
  loading: boolean;
}

function parseCoord(value: string, min: number, max: number): number | null {
  const num = Number(value);
  if (Number.isNaN(num) || num < min || num > max) return null;
  return num;
}

export function JourneyForm({ onSubmit, loading }: JourneyFormProps) {
  const t = useTranslations("journeyPlanner");
  const [coordError, setCoordError] = useState(false);

  function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);

    const fromLat = parseCoord(fd.get("from_lat") as string, LAT_MIN, LAT_MAX);
    const fromLon = parseCoord(fd.get("from_lon") as string, LON_MIN, LON_MAX);
    const toLat = parseCoord(fd.get("to_lat") as string, LAT_MIN, LAT_MAX);
    const toLon = parseCoord(fd.get("to_lon") as string, LON_MIN, LON_MAX);

    if (fromLat == null || fromLon == null || toLat == null || toLon == null) {
      setCoordError(true);
      return;
    }

    setCoordError(false);
    const departAt = (fd.get("depart_at") as string) || undefined;

    onSubmit({
      from_lat: fromLat,
      from_lon: fromLon,
      to_lat: toLat,
      to_lon: toLon,
      depart_at: departAt,
    });
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-(--spacing-grid)">
      {/* Origin */}
      <fieldset className="space-y-(--spacing-tight)">
        <legend className="text-sm font-semibold text-foreground">
          {t("from")}
        </legend>
        <div className="grid grid-cols-2 gap-(--spacing-inline)">
          <div>
            <Label htmlFor="from_lat" className="text-xs text-foreground-muted">
              {t("latitude")}
            </Label>
            <Input
              id="from_lat"
              name="from_lat"
              type="number"
              step="any"
              placeholder="56.9496"
              defaultValue="56.9496"
              required
              min={LAT_MIN}
              max={LAT_MAX}
            />
          </div>
          <div>
            <Label htmlFor="from_lon" className="text-xs text-foreground-muted">
              {t("longitude")}
            </Label>
            <Input
              id="from_lon"
              name="from_lon"
              type="number"
              step="any"
              placeholder="24.1052"
              defaultValue="24.1052"
              required
              min={LON_MIN}
              max={LON_MAX}
            />
          </div>
        </div>
      </fieldset>

      {/* Destination */}
      <fieldset className="space-y-(--spacing-tight)">
        <legend className="text-sm font-semibold text-foreground">
          {t("to")}
        </legend>
        <div className="grid grid-cols-2 gap-(--spacing-inline)">
          <div>
            <Label htmlFor="to_lat" className="text-xs text-foreground-muted">
              {t("latitude")}
            </Label>
            <Input
              id="to_lat"
              name="to_lat"
              type="number"
              step="any"
              placeholder="56.9677"
              required
              min={LAT_MIN}
              max={LAT_MAX}
            />
          </div>
          <div>
            <Label htmlFor="to_lon" className="text-xs text-foreground-muted">
              {t("longitude")}
            </Label>
            <Input
              id="to_lon"
              name="to_lon"
              type="number"
              step="any"
              placeholder="24.1056"
              required
              min={LON_MIN}
              max={LON_MAX}
            />
          </div>
        </div>
      </fieldset>

      {/* Departure time */}
      <div>
        <Label htmlFor="depart_at" className="text-xs text-foreground-muted">
          {t("departAt")}
        </Label>
        <Input
          id="depart_at"
          name="depart_at"
          type="datetime-local"
          className="w-full"
        />
      </div>

      {coordError && (
        <p className="text-xs text-error" role="alert">
          {t("invalidParams")}
        </p>
      )}

      <Button type="submit" className="w-full cursor-pointer" disabled={loading}>
        {loading ? t("searching") : t("search")}
      </Button>
    </form>
  );
}
