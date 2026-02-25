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
import { Switch } from "@/components/ui/switch";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";
import { toHexColor, fromHexColor } from "@/lib/color-utils";
import type { Route, RouteCreate, RouteUpdate } from "@/types/route";
import type { Agency } from "@/types/schedule";

interface RouteFormProps {
  mode: "create" | "edit";
  route?: Route | null;
  agencies: Agency[];
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (data: RouteCreate | RouteUpdate) => void;
}

interface FormState {
  gtfs_route_id: string;
  agency_id: string;
  route_short_name: string;
  route_long_name: string;
  route_type: string;
  route_color: string;
  route_text_color: string;
  route_sort_order: string;
  is_active: boolean;
}

/** Preset route colors by transport type, matching Riga Satiksme conventions. */
const COLOR_PRESETS: Record<string, { label: string; colors: { hex: string; name: string }[] }> = {
  "3": {
    label: "bus",
    colors: [
      { hex: "#1E88E5", name: "Blue" },
      { hex: "#E53935", name: "Red" },
      { hex: "#FB8C00", name: "Orange" },
      { hex: "#3949AB", name: "Indigo" },
      { hex: "#00ACC1", name: "Cyan" },
      { hex: "#546E7A", name: "Grey" },
    ],
  },
  "11": {
    label: "trolleybus",
    colors: [
      { hex: "#43A047", name: "Green" },
      { hex: "#2E7D32", name: "Dark Green" },
      { hex: "#388E3C", name: "Forest" },
      { hex: "#4CAF50", name: "Light Green" },
      { hex: "#00897B", name: "Teal" },
      { hex: "#1B5E20", name: "Deep Green" },
    ],
  },
  "0": {
    label: "tram",
    colors: [
      { hex: "#8E24AA", name: "Purple" },
      { hex: "#6A1B9A", name: "Deep Purple" },
      { hex: "#AB47BC", name: "Light Purple" },
      { hex: "#7B1FA2", name: "Violet" },
      { hex: "#D81B60", name: "Pink" },
      { hex: "#9C27B0", name: "Magenta" },
    ],
  },
  default: {
    label: "other",
    colors: [
      { hex: "#1E88E5", name: "Blue" },
      { hex: "#E53935", name: "Red" },
      { hex: "#43A047", name: "Green" },
      { hex: "#FB8C00", name: "Orange" },
      { hex: "#8E24AA", name: "Purple" },
      { hex: "#546E7A", name: "Grey" },
    ],
  },
};

const TEXT_COLOR_PRESETS = [
  { hex: "#FFFFFF", name: "White" },
  { hex: "#000000", name: "Black" },
  { hex: "#1A1A1A", name: "Near Black" },
  { hex: "#FAFAFA", name: "Near White" },
];

function ColorSwatches({
  colors,
  selected,
  onSelect,
}: {
  colors: { hex: string; name: string }[];
  selected: string;
  onSelect: (hex: string) => void;
}) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {colors.map((c) => (
        <button
          key={c.hex}
          type="button"
          title={c.name}
          onClick={() => onSelect(c.hex)}
          className={cn(
            "size-7 cursor-pointer rounded-md border-2 transition-all hover:scale-110",
            selected.toLowerCase() === c.hex.toLowerCase()
              ? "border-foreground ring-2 ring-foreground/20"
              : "border-transparent ring-1 ring-border",
          )}
          style={{ backgroundColor: c.hex }}
          aria-label={c.name}
        />
      ))}
    </div>
  );
}

function routeToFormState(route: Route): FormState {
  return {
    gtfs_route_id: route.gtfs_route_id,
    agency_id: String(route.agency_id),
    route_short_name: route.route_short_name,
    route_long_name: route.route_long_name,
    route_type: String(route.route_type),
    route_color: toHexColor(route.route_color, ""),
    route_text_color: toHexColor(route.route_text_color, ""),
    route_sort_order: route.route_sort_order !== null ? String(route.route_sort_order) : "",
    is_active: route.is_active,
  };
}

const DEFAULT_FORM: FormState = {
  gtfs_route_id: "",
  agency_id: "",
  route_short_name: "",
  route_long_name: "",
  route_type: "3",
  route_color: "#1E88E5",
  route_text_color: "#FFFFFF",
  route_sort_order: "",
  is_active: true,
};

export function RouteForm({
  mode,
  route,
  agencies,
  isOpen,
  onClose,
  onSubmit,
}: RouteFormProps) {
  const t = useTranslations("routes");
  const [form, setForm] = useState<FormState>(
    mode === "edit" && route ? routeToFormState(route) : DEFAULT_FORM,
  );

  const routeColorPresets = COLOR_PRESETS[form.route_type] ?? COLOR_PRESETS.default;

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!form.route_short_name.trim() || !form.route_long_name.trim()) return;

    if (mode === "create") {
      if (!form.gtfs_route_id.trim() || !form.agency_id) return;
      const data: RouteCreate = {
        gtfs_route_id: form.gtfs_route_id.trim(),
        agency_id: Number(form.agency_id),
        route_short_name: form.route_short_name.trim(),
        route_long_name: form.route_long_name.trim(),
        route_type: Number(form.route_type),
        route_color: form.route_color ? fromHexColor(form.route_color) : null,
        route_text_color: form.route_text_color ? fromHexColor(form.route_text_color) : null,
        route_sort_order: form.route_sort_order ? Number(form.route_sort_order) : null,
      };
      onSubmit(data);
    } else {
      const data: RouteUpdate = {
        route_short_name: form.route_short_name.trim(),
        route_long_name: form.route_long_name.trim(),
        route_type: Number(form.route_type),
        route_color: form.route_color ? fromHexColor(form.route_color) : null,
        route_text_color: form.route_text_color ? fromHexColor(form.route_text_color) : null,
        route_sort_order: form.route_sort_order ? Number(form.route_sort_order) : null,
        is_active: form.is_active,
      };
      onSubmit(data);
    }
    onClose();
  }

  function updateField<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-h-[90vh] overflow-y-auto" showCloseButton>
        <DialogHeader>
          <DialogTitle className="font-heading text-heading font-semibold">
            {mode === "create" ? t("form.createTitle") : t("form.editTitle")}
          </DialogTitle>
          <DialogDescription className="sr-only">
            {mode === "create" ? t("form.createTitle") : t("form.editTitle")}
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-5">
          {/* GTFS Route ID (create only) */}
          {mode === "create" && (
            <div className="space-y-1.5">
              <Label htmlFor="gtfsRouteId">{t("detail.gtfsRouteId")} *</Label>
              <Input
                id="gtfsRouteId"
                value={form.gtfs_route_id}
                onChange={(e) => updateField("gtfs_route_id", e.target.value)}
                placeholder={t("form.gtfsRouteIdPlaceholder")}
                maxLength={50}
                required
              />
            </div>
          )}

          {/* Short Name */}
          <div className="space-y-1.5">
            <Label htmlFor="shortName">{t("detail.shortName")} *</Label>
            <Input
              id="shortName"
              value={form.route_short_name}
              onChange={(e) => updateField("route_short_name", e.target.value)}
              placeholder={t("form.shortNamePlaceholder")}
              maxLength={10}
              required
            />
            <p className="text-xs text-foreground-muted">{t("form.shortNameHelp")}</p>
          </div>

          {/* Long Name */}
          <div className="space-y-1.5">
            <Label htmlFor="longName">{t("detail.longName")} *</Label>
            <Input
              id="longName"
              value={form.route_long_name}
              onChange={(e) => updateField("route_long_name", e.target.value)}
              placeholder={t("form.longNamePlaceholder")}
              maxLength={200}
              required
            />
            <p className="text-xs text-foreground-muted">{t("form.longNameHelp")}</p>
          </div>

          {/* Route Type */}
          <div className="space-y-1.5">
            <Label>{t("detail.routeType")} *</Label>
            <Select
              value={form.route_type}
              onValueChange={(v) => updateField("route_type", v)}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="3">{t("filters.bus")}</SelectItem>
                <SelectItem value="11">{t("filters.trolleybus")}</SelectItem>
                <SelectItem value="0">{t("filters.tram")}</SelectItem>
                <SelectItem value="1">{t("filters.subway")}</SelectItem>
                <SelectItem value="2">{t("filters.rail")}</SelectItem>
                <SelectItem value="4">{t("filters.ferry")}</SelectItem>
                <SelectItem value="7">{t("filters.funicular")}</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* Agency */}
          {mode === "create" && (
            <div className="space-y-1.5">
              <Label>{t("detail.agency")} *</Label>
              <Select
                value={form.agency_id}
                onValueChange={(v) => updateField("agency_id", v)}
              >
                <SelectTrigger>
                  <SelectValue placeholder={t("filters.allAgencies")} />
                </SelectTrigger>
                <SelectContent>
                  {agencies.map((a) => (
                    <SelectItem key={a.id} value={String(a.id)}>
                      {a.agency_name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}

          <Separator />

          {/* Route Color */}
          <div className="space-y-2.5">
            <Label htmlFor="routeColor">{t("detail.routeColor")}</Label>
            <ColorSwatches
              colors={routeColorPresets.colors}
              selected={form.route_color}
              onSelect={(hex) => updateField("route_color", hex)}
            />
            <div className="flex items-center gap-2">
              <input
                type="color"
                value={form.route_color || "#888888"}
                onChange={(e) => updateField("route_color", e.target.value)}
                className="size-8 shrink-0 cursor-pointer rounded border border-border"
                aria-label={t("detail.routeColor")}
              />
              <Input
                id="routeColor"
                value={form.route_color}
                onChange={(e) => updateField("route_color", e.target.value)}
                placeholder={t("form.colorPlaceholder")}
                className="font-mono text-xs"
              />
            </div>
          </div>

          {/* Text Color */}
          <div className="space-y-2.5">
            <Label htmlFor="textColor">{t("detail.textColor")}</Label>
            <ColorSwatches
              colors={TEXT_COLOR_PRESETS}
              selected={form.route_text_color}
              onSelect={(hex) => updateField("route_text_color", hex)}
            />
            <div className="flex items-center gap-2">
              <input
                type="color"
                value={form.route_text_color || "#FFFFFF"}
                onChange={(e) => updateField("route_text_color", e.target.value)}
                className="size-8 shrink-0 cursor-pointer rounded border border-border"
                aria-label={t("detail.textColor")}
              />
              <Input
                id="textColor"
                value={form.route_text_color}
                onChange={(e) => updateField("route_text_color", e.target.value)}
                placeholder={t("form.textColorPlaceholder")}
                className="font-mono text-xs"
              />
            </div>
          </div>

          {/* Color Preview */}
          {form.route_color && (
            <div className="flex items-center gap-3">
              <div
                className="flex h-8 min-w-16 items-center justify-center rounded-md px-3 text-xs font-bold"
                style={{
                  backgroundColor: form.route_color,
                  color: form.route_text_color || "#FFFFFF",
                }}
              >
                {form.route_short_name || "22"}
              </div>
              <span className="text-xs text-foreground-muted">{t("form.colorPreview")}</span>
            </div>
          )}

          <Separator />

          {/* Sort Order */}
          <div className="space-y-1.5">
            <Label htmlFor="sortOrder">{t("detail.sortOrder")}</Label>
            <Input
              id="sortOrder"
              type="number"
              value={form.route_sort_order}
              onChange={(e) => updateField("route_sort_order", e.target.value)}
              placeholder={t("form.sortOrderPlaceholder")}
            />
          </div>

          {/* Active toggle */}
          <div className="flex items-center justify-between">
            <Label htmlFor="isActive">{t("detail.isActive")}</Label>
            <Switch
              id="isActive"
              checked={form.is_active}
              onCheckedChange={(checked) => updateField("is_active", checked)}
            />
          </div>

          <Separator />

          {/* Actions */}
          <div className="flex gap-3 pt-2">
            <Button type="button" variant="outline" className="flex-1 cursor-pointer" onClick={onClose}>
              {t("actions.cancel")}
            </Button>
            <Button type="submit" className="flex-1 cursor-pointer">
              {t("actions.save")}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
