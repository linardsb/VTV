"use client";

import { useState, useCallback } from "react";
import { useTranslations, useLocale } from "next-intl";
import { Pencil, Trash2, X, Plus, Check } from "lucide-react";
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
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { Separator } from "@/components/ui/separator";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { addCalendarException, deleteCalendarException } from "@/lib/schedules-client";
import { CalendarMonthGrid } from "@/components/schedules/calendar-month-grid";
import type { Calendar, CalendarUpdate, CalendarException } from "@/types/schedule";

type DayPreset = "weekdays" | "weekend" | "daily" | "clear";

const DAY_PRESETS: Record<DayPreset, Record<string, boolean>> = {
  weekdays: { monday: true, tuesday: true, wednesday: true, thursday: true, friday: true, saturday: false, sunday: false },
  weekend: { monday: false, tuesday: false, wednesday: false, thursday: false, friday: false, saturday: true, sunday: true },
  daily: { monday: true, tuesday: true, wednesday: true, thursday: true, friday: true, saturday: true, sunday: true },
  clear: { monday: false, tuesday: false, wednesday: false, thursday: false, friday: false, saturday: false, sunday: false },
};

const DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"] as const;

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

function formFromCalendar(cal: Calendar): FormState {
  return {
    gtfs_service_id: cal.gtfs_service_id,
    monday: cal.monday,
    tuesday: cal.tuesday,
    wednesday: cal.wednesday,
    thursday: cal.thursday,
    friday: cal.friday,
    saturday: cal.saturday,
    sunday: cal.sunday,
    start_date: cal.start_date,
    end_date: cal.end_date,
  };
}

interface CalendarDialogProps {
  calendar: Calendar | null;
  exceptions: CalendarException[];
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (data: CalendarUpdate) => void;
  onDelete: (calendar: Calendar) => void;
  onExceptionsChange: () => void;
  isReadOnly: boolean;
}

function DetailRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-(--spacing-tight)">
      <span className="text-xs font-medium text-label-text uppercase tracking-wide">{label}</span>
      <div className="text-sm text-foreground">{children}</div>
    </div>
  );
}

export function CalendarDialog({
  calendar,
  exceptions,
  isOpen,
  onClose,
  onSubmit,
  onDelete,
  onExceptionsChange,
  isReadOnly,
}: CalendarDialogProps) {
  const t = useTranslations("schedules.calendars");
  const tDays = useTranslations("schedules.days");
  const locale = useLocale();

  const [mode, setMode] = useState<"view" | "edit">("view");
  const [form, setForm] = useState<FormState | null>(null);
  const [newExDate, setNewExDate] = useState("");
  const [newExType, setNewExType] = useState<"1" | "2">("1");

  function handleEdit() {
    if (!calendar) return;
    setForm(formFromCalendar(calendar));
    setMode("edit");
  }

  function handleCancelEdit() {
    setMode("view");
    setForm(null);
  }

  function handleClose() {
    setMode("view");
    setForm(null);
    onClose();
  }

  function applyPreset(preset: DayPreset) {
    setForm((prev) => prev ? ({ ...prev, ...DAY_PRESETS[preset] }) : prev);
  }

  function handleSave(e: React.FormEvent) {
    e.preventDefault();
    if (!form || !calendar) return;
    if (!form.start_date || !form.end_date) return;

    if (form.end_date < form.start_date) {
      toast.error(t("dateValidation"));
      return;
    }

    const { gtfs_service_id: _, ...rest } = form;
    void _;
    onSubmit(rest as CalendarUpdate);
    setMode("view");
    setForm(null);
  }

  const handleAddException = useCallback(async () => {
    if (!calendar || !newExDate) return;
    try {
      await addCalendarException(calendar.id, {
        date: newExDate,
        exception_type: Number(newExType) as 1 | 2,
      });
      toast.success(t("exceptionAdded"));
      setNewExDate("");
      onExceptionsChange();
    } catch {
      toast.error(t("exceptionError"));
    }
  }, [calendar, newExDate, newExType, t, onExceptionsChange]);

  const handleDeleteException = useCallback(async (exId: number) => {
    try {
      await deleteCalendarException(exId);
      toast.success(t("exceptionRemoved"));
      onExceptionsChange();
    } catch {
      toast.error(t("exceptionError"));
    }
  }, [t, onExceptionsChange]);

  if (!calendar) return null;

  const dateFormatter = new Intl.DateTimeFormat(locale, {
    year: "numeric",
    month: "long",
    day: "numeric",
  });

  // Data for the month grid — use form state (live preview) in edit mode, calendar in view mode
  const gridData = mode === "edit" && form ? form : calendar;

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && handleClose()}>
      <DialogContent className="sm:max-w-3xl max-h-[90vh] overflow-y-auto" showCloseButton>
        <DialogHeader>
          <DialogTitle className="font-heading text-heading font-semibold">
            {calendar.gtfs_service_id}
          </DialogTitle>
          <DialogDescription className="sr-only">
            {mode === "edit" ? t("editTitle") : t("serviceId")}
          </DialogDescription>
        </DialogHeader>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-(--spacing-grid)">
          {/* Left column: details or edit form */}
          <div className="space-y-(--spacing-card)">
            {mode === "view" ? (
              /* ---- VIEW MODE ---- */
              <>
                <DetailRow label={t("operatingDays")}>
                  <div className="flex flex-wrap gap-1">
                    {DAYS.map((day) => (
                      <Badge
                        key={day}
                        variant="outline"
                        className={
                          calendar[day]
                            ? "border-status-ontime/30 bg-status-ontime/10 text-status-ontime"
                            : "border-border text-foreground-subtle"
                        }
                      >
                        {calendar[day] && <Check className="mr-0.5 size-3" />}
                        {tDays(day.slice(0, 3))}
                      </Badge>
                    ))}
                  </div>
                </DetailRow>

                <DetailRow label={t("dateRange")}>
                  {dateFormatter.format(new Date(calendar.start_date))} — {dateFormatter.format(new Date(calendar.end_date))}
                </DetailRow>

                {calendar.created_by_name && (
                  <DetailRow label={t("createdBy")}>
                    {calendar.created_by_name}
                  </DetailRow>
                )}

                <Separator />

                {/* Exceptions */}
                <div className="space-y-(--spacing-inline)">
                  <p className="text-xs font-medium text-label-text uppercase tracking-wide">
                    {t("exceptions")} ({exceptions.length})
                  </p>
                  {exceptions.length === 0 ? (
                    <p className="text-sm text-foreground-muted">{t("noExceptions")}</p>
                  ) : (
                    <div className="space-y-1">
                      {exceptions.map((ex) => (
                        <div key={ex.id} className="flex items-center justify-between rounded-md border border-border px-3 py-1.5">
                          <div className="flex items-center gap-(--spacing-inline)">
                            <span className="text-sm font-mono">{ex.date}</span>
                            <Badge
                              variant="outline"
                              className={
                                ex.exception_type === 1
                                  ? "border-status-ontime/30 bg-status-ontime/10 text-status-ontime text-xs"
                                  : "border-status-delayed/30 bg-status-delayed/10 text-status-delayed text-xs"
                              }
                            >
                              {ex.exception_type === 1 ? t("exceptionAdded") : t("exceptionRemoved")}
                            </Badge>
                          </div>
                          {!isReadOnly && (
                            <Button
                              variant="ghost"
                              size="sm"
                              className="size-6 p-0 text-status-critical"
                              onClick={() => handleDeleteException(ex.id)}
                            >
                              <X className="size-3" />
                            </Button>
                          )}
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Add exception */}
                  {!isReadOnly && (
                    <div className="flex items-end gap-(--spacing-inline)">
                      <div className="flex-1 space-y-(--spacing-tight)">
                        <Label htmlFor="exDate" className="text-xs">{t("exceptionDate")}</Label>
                        <Input
                          id="exDate"
                          type="date"
                          value={newExDate}
                          onChange={(e) => setNewExDate(e.target.value)}
                        />
                      </div>
                      <div className="w-28 space-y-(--spacing-tight)">
                        <Label className="text-xs">{t("exceptionType")}</Label>
                        <Select value={newExType} onValueChange={(v) => setNewExType(v as "1" | "2")}>
                          <SelectTrigger>
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="1">{t("added")}</SelectItem>
                            <SelectItem value="2">{t("removed")}</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                      <Button
                        size="sm"
                        className="cursor-pointer"
                        onClick={handleAddException}
                        disabled={!newExDate}
                      >
                        <Plus className="size-4" />
                      </Button>
                    </div>
                  )}
                </div>

                {/* Actions */}
                {!isReadOnly && (
                  <>
                    <Separator />
                    <div className="flex gap-(--spacing-inline)">
                      <Button variant="outline" className="flex-1 cursor-pointer" onClick={handleEdit}>
                        <Pencil className="mr-2 size-4" />
                        {t("edit")}
                      </Button>
                      <Button variant="destructive" className="cursor-pointer" onClick={() => onDelete(calendar)}>
                        <Trash2 className="mr-2 size-4" />
                        {t("delete")}
                      </Button>
                    </div>
                  </>
                )}
              </>
            ) : (
              /* ---- EDIT MODE ---- */
              form && (
                <form onSubmit={handleSave} id="calendar-edit-form" className="space-y-(--spacing-card)">
                  {/* Service ID (read-only) */}
                  <div className="space-y-(--spacing-tight)">
                    <Label htmlFor="serviceId">{t("serviceId")}</Label>
                    <Input
                      id="serviceId"
                      value={form.gtfs_service_id}
                      disabled
                      maxLength={50}
                    />
                  </div>

                  <Separator />

                  {/* Days with presets */}
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
                        <Label htmlFor={`edit-${day}`}>{tDays(day)}</Label>
                        <Switch
                          id={`edit-${day}`}
                          checked={form[day]}
                          onCheckedChange={(checked) => setForm((prev) => prev ? ({ ...prev, [day]: checked }) : prev)}
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
                        onChange={(e) => setForm((prev) => prev ? ({ ...prev, start_date: e.target.value }) : prev)}
                        required
                      />
                    </div>
                    <div className="space-y-(--spacing-tight)">
                      <Label htmlFor="endDate">{t("endDate")} *</Label>
                      <Input
                        id="endDate"
                        type="date"
                        value={form.end_date}
                        onChange={(e) => setForm((prev) => prev ? ({ ...prev, end_date: e.target.value }) : prev)}
                        required
                      />
                    </div>
                  </div>

                  <Separator />

                  <div className="flex gap-3">
                    <Button type="button" variant="outline" className="flex-1 cursor-pointer" onClick={handleCancelEdit}>
                      {t("cancel")}
                    </Button>
                    <Button type="submit" className="flex-1 cursor-pointer">
                      {t("save")}
                    </Button>
                  </div>
                </form>
              )
            )}
          </div>

          {/* Right column: live month grid */}
          <div className="space-y-(--spacing-card)">
            <CalendarMonthGrid calendar={gridData} />
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
