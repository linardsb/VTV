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
import { Separator } from "@/components/ui/separator";
import type { Calendar, CalendarCreate, CalendarUpdate } from "@/types/schedule";

const DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"] as const;

interface CalendarFormProps {
  mode: "create" | "edit";
  calendar?: Calendar | null;
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (data: CalendarCreate | CalendarUpdate) => void;
}

interface FormState {
  gtfs_service_id: string;
  monday: boolean;
  tuesday: boolean;
  wednesday: boolean;
  thursday: boolean;
  friday: boolean;
  saturday: boolean;
  sunday: boolean;
  start_date: string;
  end_date: string;
}

const DEFAULT_FORM: FormState = {
  gtfs_service_id: "",
  monday: true,
  tuesday: true,
  wednesday: true,
  thursday: true,
  friday: true,
  saturday: false,
  sunday: false,
  start_date: "",
  end_date: "",
};

export function CalendarForm({
  mode,
  calendar,
  isOpen,
  onClose,
  onSubmit,
}: CalendarFormProps) {
  const t = useTranslations("schedules.calendars");
  const tDays = useTranslations("schedules.days");

  const [form, setForm] = useState<FormState>(
    mode === "edit" && calendar
      ? {
          gtfs_service_id: calendar.gtfs_service_id,
          monday: calendar.monday,
          tuesday: calendar.tuesday,
          wednesday: calendar.wednesday,
          thursday: calendar.thursday,
          friday: calendar.friday,
          saturday: calendar.saturday,
          sunday: calendar.sunday,
          start_date: calendar.start_date,
          end_date: calendar.end_date,
        }
      : DEFAULT_FORM,
  );

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!form.gtfs_service_id.trim() || !form.start_date || !form.end_date) return;

    if (mode === "create") {
      const data: CalendarCreate = { ...form, gtfs_service_id: form.gtfs_service_id.trim() };
      onSubmit(data);
    } else {
      const { gtfs_service_id: _serviceId, ...rest } = form;
      void _serviceId;
      onSubmit(rest as CalendarUpdate);
    }
    onClose();
  }

  return (
    <Sheet open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <SheetContent side="right" className="w-full overflow-y-auto sm:w-[400px]">
        <SheetHeader>
          <SheetTitle className="font-heading text-heading font-semibold">
            {mode === "create" ? t("createTitle") : t("editTitle")}
          </SheetTitle>
        </SheetHeader>

        <form onSubmit={handleSubmit} className="mt-(--spacing-grid) space-y-(--spacing-card)">
          {/* Service ID */}
          <div className="space-y-(--spacing-tight)">
            <Label htmlFor="serviceId">{t("serviceId")} *</Label>
            <Input
              id="serviceId"
              value={form.gtfs_service_id}
              onChange={(e) => setForm((prev) => ({ ...prev, gtfs_service_id: e.target.value }))}
              placeholder={t("serviceIdPlaceholder")}
              maxLength={50}
              required
              disabled={mode === "edit"}
            />
          </div>

          <Separator />

          {/* Days */}
          <div className="space-y-(--spacing-inline)">
            <p className="text-xs font-medium text-label-text uppercase tracking-wide">
              {t("operatingDays")}
            </p>
            {DAYS.map((day) => (
              <div key={day} className="flex items-center justify-between">
                <Label htmlFor={day}>{tDays(day)}</Label>
                <Switch
                  id={day}
                  checked={form[day]}
                  onCheckedChange={(checked) => setForm((prev) => ({ ...prev, [day]: checked }))}
                />
              </div>
            ))}
          </div>

          <Separator />

          {/* Date range */}
          <div className="grid grid-cols-2 gap-(--spacing-grid)">
            <div className="space-y-(--spacing-tight)">
              <Label htmlFor="startDate">{t("startDate")} *</Label>
              <Input
                id="startDate"
                type="date"
                value={form.start_date}
                onChange={(e) => setForm((prev) => ({ ...prev, start_date: e.target.value }))}
                required
              />
            </div>
            <div className="space-y-(--spacing-tight)">
              <Label htmlFor="endDate">{t("endDate")} *</Label>
              <Input
                id="endDate"
                type="date"
                value={form.end_date}
                onChange={(e) => setForm((prev) => ({ ...prev, end_date: e.target.value }))}
                required
              />
            </div>
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
      </SheetContent>
    </Sheet>
  );
}
