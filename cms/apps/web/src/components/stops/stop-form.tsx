"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { X } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import type { Stop, StopCreate, StopUpdate } from "@/types/stop";

interface StopFormProps {
  mode: "create" | "edit";
  stop: Stop | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (data: StopCreate | StopUpdate) => void;
  defaultCoords?: { lat: number; lon: number } | null;
  onCoordsChange?: (lat: number, lon: number) => void;
  externalCoords?: { lat: number; lon: number } | null;
  inline?: boolean;
}

interface FormState {
  stop_name: string;
  gtfs_stop_id: string;
  stop_desc: string;
  stop_lat: string;
  stop_lon: string;
  location_type: number;
  parent_station_id: string;
  wheelchair_boarding: number;
  is_active: boolean;
}

function getInitialState(
  mode: "create" | "edit",
  stop: Stop | null,
  defaultCoords?: { lat: number; lon: number } | null,
): FormState {
  if (mode === "edit" && stop) {
    return {
      stop_name: stop.stop_name,
      gtfs_stop_id: stop.gtfs_stop_id,
      stop_desc: stop.stop_desc ?? "",
      stop_lat: stop.stop_lat !== null ? String(stop.stop_lat) : "",
      stop_lon: stop.stop_lon !== null ? String(stop.stop_lon) : "",
      location_type: stop.location_type,
      parent_station_id: stop.parent_station_id !== null ? String(stop.parent_station_id) : "",
      wheelchair_boarding: stop.wheelchair_boarding,
      is_active: stop.is_active,
    };
  }
  return {
    stop_name: "",
    gtfs_stop_id: "",
    stop_desc: "",
    stop_lat: defaultCoords ? String(defaultCoords.lat) : "",
    stop_lon: defaultCoords ? String(defaultCoords.lon) : "",
    location_type: 0,
    parent_station_id: "",
    wheelchair_boarding: 0,
    is_active: true,
  };
}

function parseCoord(value: string): number | null {
  const parsed = parseFloat(value);
  return isNaN(parsed) ? null : parsed;
}

export function StopForm({
  mode,
  stop,
  open,
  onOpenChange,
  onSubmit,
  defaultCoords,
  onCoordsChange,
  externalCoords,
  inline = false,
}: StopFormProps) {
  const t = useTranslations("stops");
  const tLoc = useTranslations("stops.locationTypes");
  const tWheelchair = useTranslations("stops.wheelchairOptions");
  const [form, setForm] = useState<FormState>(() =>
    getInitialState(mode, stop, defaultCoords),
  );

  // Adjust form state during render when external coords change (React 19 pattern).
  // This avoids calling setState in useEffect, which is forbidden by react-hooks/set-state-in-effect.
  const [prevExtCoords, setPrevExtCoords] = useState<{ lat: number; lon: number } | null>(null);

  if (
    externalCoords &&
    (prevExtCoords?.lat !== externalCoords.lat ||
      prevExtCoords?.lon !== externalCoords.lon)
  ) {
    setPrevExtCoords(externalCoords);
    setForm((prev) => ({
      ...prev,
      stop_lat: externalCoords.lat.toFixed(6),
      stop_lon: externalCoords.lon.toFixed(6),
    }));
  }

  function updateField<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((prev) => {
      const next = { ...prev, [key]: value };
      if (
        onCoordsChange &&
        (key === "stop_lat" || key === "stop_lon")
      ) {
        const lat = parseFloat(key === "stop_lat" ? String(value) : next.stop_lat);
        const lon = parseFloat(key === "stop_lon" ? String(value) : next.stop_lon);
        if (!isNaN(lat) && !isNaN(lon)) {
          queueMicrotask(() => onCoordsChange(lat, lon));
        }
      }
      return next;
    });
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!form.stop_name.trim() || !form.gtfs_stop_id.trim()) return;

    const parentId = form.parent_station_id.trim()
      ? parseInt(form.parent_station_id, 10)
      : null;

    if (mode === "create") {
      const data: StopCreate = {
        stop_name: form.stop_name.trim(),
        gtfs_stop_id: form.gtfs_stop_id.trim(),
        stop_desc: form.stop_desc.trim() || undefined,
        stop_lat: parseCoord(form.stop_lat),
        stop_lon: parseCoord(form.stop_lon),
        location_type: form.location_type,
        parent_station_id: isNaN(parentId as number) ? undefined : parentId,
        wheelchair_boarding: form.wheelchair_boarding,
      };
      onSubmit(data);
    } else {
      const data: StopUpdate = {
        stop_name: form.stop_name.trim(),
        stop_desc: form.stop_desc.trim() || null,
        stop_lat: parseCoord(form.stop_lat),
        stop_lon: parseCoord(form.stop_lon),
        location_type: form.location_type,
        parent_station_id: isNaN(parentId as number) ? null : parentId,
        wheelchair_boarding: form.wheelchair_boarding,
        is_active: form.is_active,
      };
      onSubmit(data);
    }
    onOpenChange(false);
  }

  const title = mode === "create" ? t("form.createTitle") : t("form.editTitle");

  const formBody = (
    <form onSubmit={handleSubmit} className="space-y-(--spacing-card)">
      {/* Stop Name */}
      <div className="space-y-(--spacing-tight)">
        <Label htmlFor="stop_name">{t("detail.stopName")} *</Label>
        <Input
          id="stop_name"
          value={form.stop_name}
          onChange={(e) => updateField("stop_name", e.target.value)}
          placeholder={t("form.stopNamePlaceholder")}
          maxLength={200}
          required
        />
      </div>

      {/* GTFS Stop ID */}
      <div className="space-y-(--spacing-tight)">
        <Label htmlFor="gtfs_stop_id">{t("detail.gtfsStopId")} *</Label>
        {mode === "edit" ? (
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <Input
                  id="gtfs_stop_id"
                  value={form.gtfs_stop_id}
                  readOnly
                  className="font-mono text-xs opacity-60 cursor-not-allowed"
                />
              </TooltipTrigger>
              <TooltipContent>
                <p>{t("form.gtfsIdReadonly")}</p>
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        ) : (
          <Input
            id="gtfs_stop_id"
            value={form.gtfs_stop_id}
            onChange={(e) => updateField("gtfs_stop_id", e.target.value)}
            placeholder={t("form.gtfsStopIdPlaceholder")}
            maxLength={50}
            className="font-mono text-xs"
            required
          />
        )}
      </div>

      {/* Description */}
      <div className="space-y-(--spacing-tight)">
        <Label htmlFor="stop_desc">{t("detail.description")}</Label>
        <Textarea
          id="stop_desc"
          value={form.stop_desc}
          onChange={(e) => updateField("stop_desc", e.target.value)}
          placeholder={t("form.descriptionPlaceholder")}
          maxLength={500}
          rows={3}
        />
      </div>

      <Separator />

      {/* Coordinates */}
      <div className="grid grid-cols-2 gap-(--spacing-grid)">
        <div className="space-y-(--spacing-tight)">
          <Label htmlFor="stop_lat">{t("detail.latitude")}</Label>
          <Input
            id="stop_lat"
            type="number"
            step="any"
            min={-90}
            max={90}
            value={form.stop_lat}
            onChange={(e) => updateField("stop_lat", e.target.value)}
            placeholder={t("form.latitudePlaceholder")}
          />
        </div>
        <div className="space-y-(--spacing-tight)">
          <Label htmlFor="stop_lon">{t("detail.longitude")}</Label>
          <Input
            id="stop_lon"
            type="number"
            step="any"
            min={-180}
            max={180}
            value={form.stop_lon}
            onChange={(e) => updateField("stop_lon", e.target.value)}
            placeholder={t("form.longitudePlaceholder")}
          />
        </div>
      </div>

      <Separator />

      {/* Location Type */}
      <div className="space-y-(--spacing-tight)">
        <Label>{t("detail.locationType")}</Label>
        <Select
          value={String(form.location_type)}
          onValueChange={(v) => updateField("location_type", Number(v))}
        >
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {[0, 1, 2, 3, 4].map((val) => (
              <SelectItem key={val} value={String(val)}>
                {tLoc(String(val))}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Wheelchair Boarding */}
      <div className="space-y-(--spacing-tight)">
        <Label>{t("detail.wheelchairBoarding")}</Label>
        <Select
          value={String(form.wheelchair_boarding)}
          onValueChange={(v) => updateField("wheelchair_boarding", Number(v))}
        >
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {[0, 1, 2].map((val) => (
              <SelectItem key={val} value={String(val)}>
                {tWheelchair(String(val))}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Parent Station ID */}
      <div className="space-y-(--spacing-tight)">
        <Label htmlFor="parent_station_id">{t("detail.parentStation")}</Label>
        <Input
          id="parent_station_id"
          type="number"
          value={form.parent_station_id}
          onChange={(e) => updateField("parent_station_id", e.target.value)}
        />
      </div>

      {/* Active toggle (edit mode only) */}
      {mode === "edit" && (
        <div className="flex items-center justify-between">
          <Label htmlFor="is_active">{t("detail.isActive")}</Label>
          <Switch
            id="is_active"
            checked={form.is_active}
            onCheckedChange={(checked) => updateField("is_active", checked)}
          />
        </div>
      )}

      <Separator />

      {/* Actions */}
      <div className="flex gap-(--spacing-inline)">
        <Button
          type="button"
          variant="outline"
          className="flex-1 cursor-pointer"
          onClick={() => onOpenChange(false)}
        >
          {t("actions.cancel")}
        </Button>
        <Button type="submit" className="flex-1 cursor-pointer">
          {t("actions.save")}
        </Button>
      </div>
    </form>
  );

  // Inline mode: render form directly (no Sheet wrapper) for desktop side-by-side
  if (inline) {
    if (!open) return null;
    return (
      <div className="flex h-full flex-col overflow-y-auto p-(--spacing-page)">
        <div className="mb-(--spacing-grid) flex items-center justify-between">
          <h2 className="font-heading text-heading font-semibold">{title}</h2>
          <Button
            variant="ghost"
            size="sm"
            className="size-8 cursor-pointer p-0"
            onClick={() => onOpenChange(false)}
            aria-label={t("actions.close")}
          >
            <X className="size-4" />
          </Button>
        </div>
        {formBody}
      </div>
    );
  }

  // Dialog mode: wrap form in Dialog overlay (mobile)
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[28rem] max-h-[90vh] overflow-y-auto" showCloseButton>
        <DialogHeader>
          <DialogTitle className="font-heading text-heading font-semibold">
            {title}
          </DialogTitle>
          <DialogDescription className="sr-only">
            {title}
          </DialogDescription>
        </DialogHeader>
        {formBody}
      </DialogContent>
    </Dialog>
  );
}
