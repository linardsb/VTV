"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import type { Trip, TripCreate, TripUpdate, Calendar } from "@/types/schedule";
import type { Route } from "@/types/route";

interface TripFormProps {
  mode: "create" | "edit";
  trip?: Trip | null;
  routes: Route[];
  calendars: Calendar[];
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (data: TripCreate | TripUpdate) => void;
}

interface FormState {
  gtfs_trip_id: string;
  route_id: string;
  calendar_id: string;
  direction_id: string;
  trip_headsign: string;
  block_id: string;
}

const DEFAULT_FORM: FormState = {
  gtfs_trip_id: "",
  route_id: "",
  calendar_id: "",
  direction_id: "",
  trip_headsign: "",
  block_id: "",
};

export function TripForm({
  mode,
  trip,
  routes,
  calendars,
  isOpen,
  onClose,
  onSubmit,
}: TripFormProps) {
  const t = useTranslations("schedules.trips");

  const [form, setForm] = useState<FormState>(
    mode === "edit" && trip
      ? {
          gtfs_trip_id: trip.gtfs_trip_id,
          route_id: String(trip.route_id),
          calendar_id: String(trip.calendar_id),
          direction_id: trip.direction_id !== null ? String(trip.direction_id) : "",
          trip_headsign: trip.trip_headsign ?? "",
          block_id: trip.block_id ?? "",
        }
      : DEFAULT_FORM,
  );

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!form.gtfs_trip_id.trim() || !form.route_id || !form.calendar_id) return;

    if (mode === "create") {
      const data: TripCreate = {
        gtfs_trip_id: form.gtfs_trip_id.trim(),
        route_id: Number(form.route_id),
        calendar_id: Number(form.calendar_id),
        direction_id: form.direction_id ? Number(form.direction_id) : null,
        trip_headsign: form.trip_headsign || null,
        block_id: form.block_id || null,
      };
      onSubmit(data);
    } else {
      const data: TripUpdate = {
        route_id: Number(form.route_id),
        calendar_id: Number(form.calendar_id),
        direction_id: form.direction_id ? Number(form.direction_id) : null,
        trip_headsign: form.trip_headsign || null,
        block_id: form.block_id || null,
      };
      onSubmit(data);
    }
    onClose();
  }

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-h-[90vh] overflow-y-auto" showCloseButton>
        <DialogHeader>
          <DialogTitle className="font-heading text-heading font-semibold">
            {mode === "create" ? t("createTitle") : t("editTitle")}
          </DialogTitle>
          <DialogDescription className="sr-only">
            {mode === "create" ? t("createTitle") : t("editTitle")}
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-(--spacing-card)">
          {/* Trip ID */}
          <div className="space-y-(--spacing-tight)">
            <Label htmlFor="tripId">{t("tripId")} *</Label>
            <Input
              id="tripId"
              value={form.gtfs_trip_id}
              onChange={(e) => setForm((prev) => ({ ...prev, gtfs_trip_id: e.target.value }))}
              placeholder={t("tripIdPlaceholder")}
              maxLength={100}
              required
              disabled={mode === "edit"}
            />
          </div>

          {/* Route */}
          <div className="space-y-(--spacing-tight)">
            <Label>{t("route")} *</Label>
            <Select
              value={form.route_id}
              onValueChange={(v) => setForm((prev) => ({ ...prev, route_id: v }))}
            >
              <SelectTrigger>
                <SelectValue placeholder={t("selectRoute")} />
              </SelectTrigger>
              <SelectContent>
                {routes.map((r) => (
                  <SelectItem key={r.id} value={String(r.id)}>
                    {r.route_short_name} - {r.route_long_name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Calendar */}
          <div className="space-y-(--spacing-tight)">
            <Label>{t("calendar")} *</Label>
            <Select
              value={form.calendar_id}
              onValueChange={(v) => setForm((prev) => ({ ...prev, calendar_id: v }))}
            >
              <SelectTrigger>
                <SelectValue placeholder={t("selectCalendar")} />
              </SelectTrigger>
              <SelectContent>
                {calendars.map((c) => (
                  <SelectItem key={c.id} value={String(c.id)}>
                    {c.gtfs_service_id}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <Separator />

          {/* Direction */}
          <div className="space-y-(--spacing-tight)">
            <Label>{t("direction")}</Label>
            <Select
              value={form.direction_id}
              onValueChange={(v) => setForm((prev) => ({ ...prev, direction_id: v }))}
            >
              <SelectTrigger>
                <SelectValue placeholder={t("allDirections")} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="0">{t("outbound")}</SelectItem>
                <SelectItem value="1">{t("inbound")}</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* Headsign */}
          <div className="space-y-(--spacing-tight)">
            <Label htmlFor="headsign">{t("headsign")}</Label>
            <Input
              id="headsign"
              value={form.trip_headsign}
              onChange={(e) => setForm((prev) => ({ ...prev, trip_headsign: e.target.value }))}
              placeholder={t("headsignPlaceholder")}
              maxLength={200}
            />
          </div>

          {/* Block ID */}
          <div className="space-y-(--spacing-tight)">
            <Label htmlFor="blockId">{t("blockId")}</Label>
            <Input
              id="blockId"
              value={form.block_id}
              onChange={(e) => setForm((prev) => ({ ...prev, block_id: e.target.value }))}
              placeholder={t("blockIdPlaceholder")}
              maxLength={50}
            />
          </div>

          <Separator />

          <div className="flex gap-(--spacing-inline)">
            <Button type="button" variant="outline" className="flex-1 cursor-pointer" onClick={onClose}>
              {t("cancel")}
            </Button>
            <Button type="submit" className="flex-1 cursor-pointer">
              {t("save")}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
