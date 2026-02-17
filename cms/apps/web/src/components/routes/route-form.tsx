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
import { AGENCY_IDS, type RouteFormData, type RouteType } from "@/types/route";

interface RouteFormProps {
  mode: "create" | "edit";
  initialData?: RouteFormData;
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (data: RouteFormData) => void;
}

const DEFAULT_FORM: RouteFormData = {
  shortName: "",
  longName: "",
  type: 3,
  agencyId: "rs",
  color: "#1E88E5",
  textColor: "#FFFFFF",
  description: "",
  isActive: true,
};

export function RouteForm({
  mode,
  initialData,
  isOpen,
  onClose,
  onSubmit,
}: RouteFormProps) {
  const t = useTranslations("routes");
  const [form, setForm] = useState<RouteFormData>(initialData ?? DEFAULT_FORM);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!form.shortName.trim() || !form.longName.trim()) return;
    onSubmit(form);
    onClose();
  }

  function updateField<K extends keyof RouteFormData>(key: K, value: RouteFormData[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  return (
    <Sheet open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <SheetContent side="right" className="w-[400px] overflow-y-auto sm:w-[400px]">
        <SheetHeader>
          <SheetTitle className="font-heading text-heading font-semibold">
            {mode === "create" ? t("form.createTitle") : t("form.editTitle")}
          </SheetTitle>
        </SheetHeader>

        <form onSubmit={handleSubmit} className="mt-(--spacing-grid) space-y-(--spacing-card)">
          {/* Short Name */}
          <div className="space-y-(--spacing-tight)">
            <Label htmlFor="shortName">{t("detail.shortName")} *</Label>
            <Input
              id="shortName"
              value={form.shortName}
              onChange={(e) => updateField("shortName", e.target.value)}
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
              value={form.longName}
              onChange={(e) => updateField("longName", e.target.value)}
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
              value={String(form.type)}
              onValueChange={(v) => updateField("type", Number(v) as RouteType)}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="3">{t("filters.bus")}</SelectItem>
                <SelectItem value="11">{t("filters.trolleybus")}</SelectItem>
                <SelectItem value="0">{t("filters.tram")}</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* Agency */}
          <div className="space-y-(--spacing-tight)">
            <Label>{t("detail.agency")} *</Label>
            <Select
              value={form.agencyId}
              onValueChange={(v) => updateField("agencyId", v)}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {AGENCY_IDS.map((id) => (
                  <SelectItem key={id} value={id}>
                    {t(`agencies.${id}`)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <Separator />

          {/* Colors */}
          <div className="grid grid-cols-2 gap-(--spacing-grid)">
            <div className="space-y-(--spacing-tight)">
              <Label htmlFor="routeColor">{t("detail.routeColor")}</Label>
              <div className="flex items-center gap-(--spacing-tight)">
                <input
                  type="color"
                  value={form.color}
                  onChange={(e) => updateField("color", e.target.value)}
                  className="size-8 cursor-pointer rounded border border-border"
                  aria-label={t("detail.routeColor")}
                />
                <Input
                  id="routeColor"
                  value={form.color}
                  onChange={(e) => updateField("color", e.target.value)}
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
                  value={form.textColor}
                  onChange={(e) => updateField("textColor", e.target.value)}
                  className="size-8 cursor-pointer rounded border border-border"
                  aria-label={t("detail.textColor")}
                />
                <Input
                  id="textColor"
                  value={form.textColor}
                  onChange={(e) => updateField("textColor", e.target.value)}
                  placeholder={t("form.textColorPlaceholder")}
                  className="font-mono text-xs"
                />
              </div>
            </div>
          </div>

          {/* Description */}
          <div className="space-y-(--spacing-tight)">
            <Label htmlFor="description">{t("detail.description")}</Label>
            <Textarea
              id="description"
              value={form.description}
              onChange={(e) => updateField("description", e.target.value)}
              placeholder={t("form.descriptionPlaceholder")}
              rows={3}
            />
          </div>

          {/* Active toggle */}
          <div className="flex items-center justify-between">
            <Label htmlFor="isActive">{t("detail.isActive")}</Label>
            <Switch
              id="isActive"
              checked={form.isActive}
              onCheckedChange={(checked) => updateField("isActive", checked)}
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
