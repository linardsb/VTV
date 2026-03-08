"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import dynamic from "next/dynamic";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Separator } from "@/components/ui/separator";
import { Switch } from "@/components/ui/switch";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type {
  Geofence,
  GeofenceCreate,
  GeofenceUpdate,
  ZoneType,
  AlertSeverity,
} from "@/types/geofence";

const GeofenceMap = dynamic(
  () =>
    import("@/components/geofences/geofence-map").then((m) => m.GeofenceMap),
  {
    ssr: false,
    loading: () => <Skeleton className="h-[300px] w-full" />,
  },
);

interface GeofenceFormProps {
  mode: "create" | "edit";
  geofence: Geofence | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (data: GeofenceCreate | GeofenceUpdate) => void;
}

const ZONE_TYPES: ZoneType[] = [
  "depot",
  "terminal",
  "restricted",
  "customer",
  "custom",
];
const SEVERITIES: AlertSeverity[] = [
  "critical",
  "high",
  "medium",
  "low",
  "info",
];

export function GeofenceForm({
  mode,
  geofence,
  open,
  onOpenChange,
  onSubmit,
}: GeofenceFormProps) {
  const t = useTranslations("geofences");
  const isEdit = mode === "edit";

  const [name, setName] = useState(geofence?.name ?? "");
  const [zoneType, setZoneType] = useState<ZoneType>(
    geofence?.zone_type ?? "custom",
  );
  const [color, setColor] = useState(geofence?.color ?? "");
  const [description, setDescription] = useState(
    geofence?.description ?? "",
  );
  const [alertOnEnter, setAlertOnEnter] = useState(
    geofence?.alert_on_enter ?? true,
  );
  const [alertOnExit, setAlertOnExit] = useState(
    geofence?.alert_on_exit ?? true,
  );
  const [alertOnDwell, setAlertOnDwell] = useState(
    geofence?.alert_on_dwell ?? false,
  );
  const [dwellThreshold, setDwellThreshold] = useState(
    geofence?.dwell_threshold_minutes ?? 30,
  );
  const [alertSeverity, setAlertSeverity] = useState<AlertSeverity>(
    geofence?.alert_severity ?? "medium",
  );
  const [coordinates, setCoordinates] = useState<number[][]>(
    geofence?.coordinates ?? [],
  );

  const isValid = name.trim().length > 0 && coordinates.length >= 3;

  const handleSubmit = () => {
    if (!isValid) return;

    // Ensure polygon is closed (first == last point)
    const closedCoords = [...coordinates];
    if (
      closedCoords.length >= 3 &&
      (closedCoords[0][0] !== closedCoords[closedCoords.length - 1][0] ||
        closedCoords[0][1] !== closedCoords[closedCoords.length - 1][1])
    ) {
      closedCoords.push([...closedCoords[0]]);
    }

    if (isEdit) {
      const data: GeofenceUpdate = {};
      if (name !== geofence?.name) data.name = name;
      if (zoneType !== geofence?.zone_type) data.zone_type = zoneType;
      if (color !== (geofence?.color ?? ""))
        data.color = color || null;
      if (description !== (geofence?.description ?? ""))
        data.description = description || null;
      if (alertOnEnter !== geofence?.alert_on_enter)
        data.alert_on_enter = alertOnEnter;
      if (alertOnExit !== geofence?.alert_on_exit)
        data.alert_on_exit = alertOnExit;
      if (alertOnDwell !== geofence?.alert_on_dwell)
        data.alert_on_dwell = alertOnDwell;
      if (dwellThreshold !== geofence?.dwell_threshold_minutes)
        data.dwell_threshold_minutes = alertOnDwell ? dwellThreshold : null;
      if (alertSeverity !== geofence?.alert_severity)
        data.alert_severity = alertSeverity;
      data.coordinates = closedCoords;
      onSubmit(data);
    } else {
      const data: GeofenceCreate = {
        name,
        zone_type: zoneType,
        coordinates: closedCoords,
        color: color || null,
        description: description || null,
        alert_on_enter: alertOnEnter,
        alert_on_exit: alertOnExit,
        alert_on_dwell: alertOnDwell,
        dwell_threshold_minutes: alertOnDwell ? dwellThreshold : null,
        alert_severity: alertSeverity,
      };
      onSubmit(data);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="sm:max-w-[48rem] max-h-[90vh] overflow-y-auto"
        showCloseButton
      >
        <DialogHeader>
          <DialogTitle className="font-heading text-heading font-semibold">
            {isEdit ? t("form.editTitle") : t("form.createTitle")}
          </DialogTitle>
          <DialogDescription className="sr-only">
            {isEdit ? t("form.editTitle") : t("form.createTitle")}
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-col md:flex-row gap-(--spacing-card)">
          {/* Left: form fields */}
          <div className="flex-1 space-y-(--spacing-card)">
            <div className="space-y-1">
              <p className="text-xs font-medium text-label-text uppercase tracking-wide">
                {t("form.name")}
              </p>
              <Input
                value={name}
                onChange={(e) => setName(e.target.value)}
                maxLength={200}
                aria-label={t("form.name")}
              />
            </div>

            <div className="space-y-1">
              <p className="text-xs font-medium text-label-text uppercase tracking-wide">
                {t("form.zoneType")}
              </p>
              <Select
                value={zoneType}
                onValueChange={(v) => setZoneType(v as ZoneType)}
              >
                <SelectTrigger aria-label={t("form.zoneType")}>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {ZONE_TYPES.map((zt) => (
                    <SelectItem key={zt} value={zt}>
                      {t(`filters.${zt}`)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-1">
              <p className="text-xs font-medium text-label-text uppercase tracking-wide">
                {t("form.color")}
              </p>
              <div className="flex gap-2 items-center">
                <Input
                  value={color}
                  onChange={(e) => setColor(e.target.value)}
                  placeholder="#0391F2"
                  maxLength={7}
                  className="flex-1"
                  aria-label={t("form.color")}
                />
                {color && (
                  <div
                    className="size-8 border border-border shrink-0"
                    style={{ backgroundColor: color }}
                    aria-hidden="true"
                  />
                )}
              </div>
            </div>

            <div className="space-y-1">
              <p className="text-xs font-medium text-label-text uppercase tracking-wide">
                {t("form.description")}
              </p>
              <Textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                maxLength={1000}
                rows={2}
                aria-label={t("form.description")}
              />
            </div>

            <Separator />

            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-sm">{t("form.alertOnEnter")}</span>
                <Switch
                  checked={alertOnEnter}
                  onCheckedChange={setAlertOnEnter}
                  aria-label={t("form.alertOnEnter")}
                />
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm">{t("form.alertOnExit")}</span>
                <Switch
                  checked={alertOnExit}
                  onCheckedChange={setAlertOnExit}
                  aria-label={t("form.alertOnExit")}
                />
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm">{t("form.alertOnDwell")}</span>
                <Switch
                  checked={alertOnDwell}
                  onCheckedChange={setAlertOnDwell}
                  aria-label={t("form.alertOnDwell")}
                />
              </div>
              {alertOnDwell && (
                <div className="space-y-1">
                  <p className="text-xs font-medium text-label-text uppercase tracking-wide">
                    {t("form.dwellThreshold")}
                  </p>
                  <Input
                    type="number"
                    min={1}
                    max={1440}
                    value={dwellThreshold}
                    onChange={(e) =>
                      setDwellThreshold(Number(e.target.value))
                    }
                    aria-label={t("form.dwellThreshold")}
                  />
                  <p className="text-xs text-foreground-subtle">
                    {t("form.dwellThresholdHelp")}
                  </p>
                </div>
              )}
            </div>

            <div className="space-y-1">
              <p className="text-xs font-medium text-label-text uppercase tracking-wide">
                {t("form.severity")}
              </p>
              <Select
                value={alertSeverity}
                onValueChange={(v) =>
                  setAlertSeverity(v as AlertSeverity)
                }
              >
                <SelectTrigger aria-label={t("form.severity")}>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {SEVERITIES.map((s) => (
                    <SelectItem key={s} value={s}>
                      {s}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          {/* Right: map */}
          <div className="flex-1 min-h-[300px] md:min-h-[400px]">
            <p className="text-xs font-medium text-label-text uppercase tracking-wide mb-2">
              {t("form.coordinates")}
            </p>
            <p className="text-xs text-foreground-subtle mb-2">
              {t("form.coordinatesHelp")}
            </p>
            <div className="h-[300px] md:h-[350px] border border-border">
              <GeofenceMap
                geofences={[]}
                selectedGeofenceId={null}
                onSelectGeofence={() => {}}
                editMode
                editCoordinates={coordinates}
                onCoordinatesChange={setCoordinates}
              />
            </div>
            {coordinates.length > 0 && (
              <Button
                variant="outline"
                size="sm"
                className="mt-2 cursor-pointer"
                onClick={() => setCoordinates([])}
              >
                {t("map.clearPolygon")}
              </Button>
            )}
          </div>
        </div>

        <Separator />

        <div className="flex gap-2">
          <Button
            variant="outline"
            className="flex-1 cursor-pointer"
            onClick={() => onOpenChange(false)}
          >
            {t("actions.cancel")}
          </Button>
          <Button
            className="flex-1 cursor-pointer"
            onClick={handleSubmit}
            disabled={!isValid}
          >
            {t("actions.save")}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
