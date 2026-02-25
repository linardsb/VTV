"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { toast } from "sonner";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Separator } from "@/components/ui/separator";
import { CalendarMonthGrid } from "@/components/schedules/calendar-month-grid";
import type { CalendarCreate, CalendarUpdate } from "@/types/schedule";

type DayPreset = "weekdays" | "weekend" | "daily" | "clear";

const DAY_PRESETS: Record<DayPreset, Record<string, boolean>> = {
  weekdays: { monday: true, tuesday: true, wednesday: true, thursday: true, friday: true, saturday: false, sunday: false },
  weekend: { monday: false, tuesday: false, wednesday: false, thursday: false, friday: false, saturday: true, sunday: true },
  daily: { monday: true, tuesday: true, wednesday: true, thursday: true, friday: true, saturday: true, sunday: true },
  clear: { monday: false, tuesday: false, wednesday: false, thursday: false, friday: false, saturday: false, sunday: false },
};

const DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"] as const;

interface CalendarFormProps {
  mode: "create";
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
  isOpen,
  onClose,
  onSubmit,
}: CalendarFormProps) {
  const t = useTranslations("schedules.calendars");
  const tDays = useTranslations("schedules.days");

  const [form, setForm] = useState<FormState>(DEFAULT_FORM);

  function applyPreset(preset: DayPreset) {
    setForm((prev) => ({ ...prev, ...DAY_PRESETS[preset] }));
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!form.gtfs_service_id.trim() || !form.start_date || !form.end_date) return;

    if (form.end_date < form.start_date) {
      toast.error(t("dateValidation"));
      return;
    }

    const data: CalendarCreate = { ...form, gtfs_service_id: form.gtfs_service_id.trim() };
    onSubmit(data);
    onClose();
  }

  const showGrid = form.start_date && form.end_date;

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-3xl max-h-[90vh] overflow-y-auto" showCloseButton>
        <DialogHeader>
          <DialogTitle className="font-heading text-heading font-semibold">
            {t("createTitle")}
          </DialogTitle>
          <DialogDescription className="sr-only">
            {t("createTitle")}
          </DialogDescription>
        </DialogHeader>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-(--spacing-grid)">
          {/* Form */}
          <form onSubmit={handleSubmit} id="calendar-create-form" className="space-y-5">
            {/* Service ID */}
            <div className="space-y-(--spacing-tight)">
              <Label htmlFor="createServiceId">{t("serviceId")} *</Label>
              <Input
                id="createServiceId"
                value={form.gtfs_service_id}
                onChange={(e) => setForm((prev) => ({ ...prev, gtfs_service_id: e.target.value }))}
                placeholder={t("serviceIdPlaceholder")}
                maxLength={50}
                required
              />
            </div>

            <Separator />

            {/* Days */}
            <div className="space-y-2.5">
              <p className="text-xs font-medium text-label-text uppercase tracking-wide">
                {t("operatingDays")}
              </p>
              <div className="flex flex-wrap gap-1.5">
                <Button type="button" variant="outline" size="sm" className="cursor-pointer text-xs h-7 px-2" onClick={() => applyPreset("weekdays")}>
                  {t("presetWeekdays")}
                </Button>
                <Button type="button" variant="outline" size="sm" className="cursor-pointer text-xs h-7 px-2" onClick={() => applyPreset("weekend")}>
                  {t("presetWeekend")}
                </Button>
                <Button type="button" variant="outline" size="sm" className="cursor-pointer text-xs h-7 px-2" onClick={() => applyPreset("daily")}>
                  {t("presetDaily")}
                </Button>
                <Button type="button" variant="outline" size="sm" className="cursor-pointer text-xs h-7 px-2" onClick={() => applyPreset("clear")}>
                  {t("presetClear")}
                </Button>
              </div>
              {DAYS.map((day) => (
                <div key={day} className="flex items-center justify-between py-0.5">
                  <Label htmlFor={`create-${day}`}>{tDays(day)}</Label>
                  <Switch
                    id={`create-${day}`}
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
                <Label htmlFor="createStartDate">{t("startDate")} *</Label>
                <Input
                  id="createStartDate"
                  type="date"
                  value={form.start_date}
                  onChange={(e) => setForm((prev) => ({ ...prev, start_date: e.target.value }))}
                  required
                />
              </div>
              <div className="space-y-(--spacing-tight)">
                <Label htmlFor="createEndDate">{t("endDate")} *</Label>
                <Input
                  id="createEndDate"
                  type="date"
                  value={form.end_date}
                  onChange={(e) => setForm((prev) => ({ ...prev, end_date: e.target.value }))}
                  required
                />
              </div>
            </div>

            <Separator />

            <div className="flex gap-3">
              <Button type="button" variant="outline" className="flex-1 cursor-pointer" onClick={onClose}>
                {t("cancel")}
              </Button>
              <Button type="submit" className="flex-1 cursor-pointer">
                {t("save")}
              </Button>
            </div>
          </form>

          {/* Live month grid preview */}
          <div className="space-y-(--spacing-card)">
            {showGrid ? (
              <CalendarMonthGrid calendar={form} />
            ) : (
              <div className="flex h-full items-center justify-center rounded-lg border-2 border-dashed border-border p-(--spacing-card)">
                <p className="text-sm text-foreground-muted text-center">
                  {t("gridHint")}
                </p>
              </div>
            )}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
