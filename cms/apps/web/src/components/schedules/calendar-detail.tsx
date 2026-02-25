"use client";

import { useState, useCallback } from "react";
import { useTranslations } from "next-intl";
import { useLocale } from "next-intl";
import { Pencil, Trash2, X, Plus, Check } from "lucide-react";
import { toast } from "sonner";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
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
import type { Calendar, CalendarException } from "@/types/schedule";

const DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"] as const;

interface CalendarDetailProps {
  calendar: Calendar | null;
  exceptions: CalendarException[];
  isOpen: boolean;
  onClose: () => void;
  onEdit: (calendar: Calendar) => void;
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

export function CalendarDetail({
  calendar,
  exceptions,
  isOpen,
  onClose,
  onEdit,
  onDelete,
  onExceptionsChange,
  isReadOnly,
}: CalendarDetailProps) {
  const t = useTranslations("schedules.calendars");
  const tDays = useTranslations("schedules.days");
  const locale = useLocale();

  const [newExDate, setNewExDate] = useState("");
  const [newExType, setNewExType] = useState<"1" | "2">("1");

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

  return (
    <Sheet open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <SheetContent side="right" className="w-full overflow-y-auto sm:w-[420px]">
        <SheetHeader>
          <SheetTitle className="font-heading text-heading font-semibold">
            {calendar.gtfs_service_id}
          </SheetTitle>
        </SheetHeader>

        <div className="px-4 pb-4 space-y-(--spacing-card)">
          {/* Operating days */}
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

          <Separator />

          {/* Month grid */}
          <CalendarMonthGrid calendar={calendar} />

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
                <Button variant="outline" className="flex-1 cursor-pointer" onClick={() => onEdit(calendar)}>
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
        </div>
      </SheetContent>
    </Sheet>
  );
}
