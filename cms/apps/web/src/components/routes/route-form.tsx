"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
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
    <Sheet open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <SheetContent side="right" className="w-full overflow-y-auto sm:w-[400px]">
        <SheetHeader>
          <SheetTitle className="font-heading text-heading font-semibold">
            {mode === "create" ? t("form.createTitle") : t("form.editTitle")}
          </SheetTitle>
        </SheetHeader>

        <form onSubmit={handleSubmit} className="mt-(--spacing-grid) space-y-(--spacing-card)">
          {/* GTFS Route ID (create only) */}
          {mode === "create" && (
            <div className="space-y-(--spacing-tight)">
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
          <div className="space-y-(--spacing-tight)">
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
          <div className="space-y-(--spacing-tight)">
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
          <div className="space-y-(--spacing-tight)">
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
            <div className="space-y-(--spacing-tight)">
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

          {/* Colors */}
          <div className="grid grid-cols-2 gap-(--spacing-grid)">
            <div className="space-y-(--spacing-tight)">
              <Label htmlFor="routeColor">{t("detail.routeColor")}</Label>
              <div className="flex items-center gap-(--spacing-tight)">
                <input
                  type="color"
                  value={form.route_color || "#888888"}
                  onChange={(e) => updateField("route_color", e.target.value)}
                  className="size-8 cursor-pointer rounded border border-border"
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
            <div className="space-y-(--spacing-tight)">
              <Label htmlFor="textColor">{t("detail.textColor")}</Label>
              <div className="flex items-center gap-(--spacing-tight)">
                <input
                  type="color"
                  value={form.route_text_color || "#FFFFFF"}
                  onChange={(e) => updateField("route_text_color", e.target.value)}
                  className="size-8 cursor-pointer rounded border border-border"
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
          </div>

          {/* Sort Order */}
          <div className="space-y-(--spacing-tight)">
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
          <div className="flex gap-(--spacing-inline)">
            <Button type="button" variant="outline" className="flex-1 cursor-pointer" onClick={onClose}>
              {t("actions.cancel")}
            </Button>
            <Button type="submit" className="flex-1 cursor-pointer">
              {t("actions.save")}
            </Button>
          </div>
        </form>
      </SheetContent>
    </Sheet>
  );
}
