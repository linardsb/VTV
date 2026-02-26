"use client";

import { useState, useCallback } from "react";
import { useTranslations } from "next-intl";
import { useLocale } from "next-intl";
import { toast } from "sonner";
import { Clock, CalendarOff, Thermometer, GraduationCap, Pencil } from "lucide-react";
import { cn } from "@/lib/utils";
import type { Driver } from "@/types/driver";
import type { EventCreate, EventGoals } from "@/types/event";
import { createEvent } from "@/lib/events-sdk";
import { GoalsForm } from "./goals-form";
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

interface DriverDropDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  driver: Driver | null;
  targetDate: Date | null;
  onEventCreated: () => void;
}

interface ActionCardProps {
  icon: React.ReactNode;
  title: string;
  description: string;
  onClick: () => void;
  disabled: boolean;
}

const SHIFT_TIMES: Record<string, { start: string; end: string; nextDay: boolean }> = {
  morning: { start: "05:00", end: "13:00", nextDay: false },
  afternoon: { start: "13:00", end: "21:00", nextDay: false },
  evening: { start: "17:00", end: "01:00", nextDay: true },
  night: { start: "22:00", end: "06:00", nextDay: true },
};

const SHIFT_LABEL_KEYS: Record<string, string> = {
  morning: "shiftMorning",
  afternoon: "shiftAfternoon",
  evening: "shiftEvening",
  night: "shiftNight",
};

function buildDatetime(date: Date, time: string, nextDay: boolean): string {
  const [hours, minutes] = time.split(":").map(Number);
  const d = new Date(date);
  if (nextDay) {
    d.setDate(d.getDate() + 1);
  }
  d.setHours(hours, minutes, 0, 0);
  return d.toISOString();
}

function ActionCard({ icon, title, description, onClick, disabled }: ActionCardProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={cn(
        "flex w-full items-center gap-(--spacing-inline) rounded-lg border border-border-subtle p-(--spacing-card) text-left transition-colors duration-200 hover:border-border hover:bg-surface cursor-pointer",
        disabled && "pointer-events-none opacity-50"
      )}
    >
      <div className="flex size-9 shrink-0 items-center justify-center rounded-md bg-interactive/10 text-interactive">
        {icon}
      </div>
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium text-foreground">{title}</p>
        <p className="text-xs text-foreground-muted">{description}</p>
      </div>
    </button>
  );
}

export function DriverDropDialog({
  open,
  onOpenChange,
  driver,
  targetDate,
  onEventCreated,
}: DriverDropDialogProps) {
  const t = useTranslations("dashboard");
  const locale = useLocale();

  type DialogStep = "action" | "goals";
  type GoalAction = "shift" | "training";

  const [isSaving, setIsSaving] = useState(false);
  const [showCustomForm, setShowCustomForm] = useState(false);
  const [customTitle, setCustomTitle] = useState("");
  const [customStart, setCustomStart] = useState("09:00");
  const [customEnd, setCustomEnd] = useState("17:00");
  const [step, setStep] = useState<DialogStep>("action");
  const [selectedAction, setSelectedAction] = useState<GoalAction | null>(null);

  const driverName = driver
    ? `${driver.first_name} ${driver.last_name}`
    : "";

  const formattedDate = targetDate
    ? targetDate.toLocaleDateString(locale, {
        weekday: "long",
        year: "numeric",
        month: "long",
        day: "numeric",
      })
    : "";

  const handleCreate = useCallback(
    async (eventData: EventCreate) => {
      setIsSaving(true);
      try {
        await createEvent(eventData);
        toast.success(t("dropAction.created"));
        onEventCreated();
      } catch {
        toast.error(t("dropAction.createError"));
      } finally {
        setIsSaving(false);
      }
    },
    [t, onEventCreated],
  );

  function handleAssignShift() {
    if (!driver || !targetDate) return;
    setSelectedAction("shift");
    setStep("goals");
  }

  function handleMarkLeave() {
    if (!driver || !targetDate) return;
    void handleCreate({
      title: t("dropAction.eventTitleLeave", { name: driverName }),
      description: t("dropAction.eventDesc", { number: driver.employee_number }),
      start_datetime: buildDatetime(targetDate, "00:00", false),
      end_datetime: buildDatetime(targetDate, "23:59", false),
      priority: "low",
      category: "driver-shift",
      driver_id: driver.id,
    });
  }

  function handleMarkSick() {
    if (!driver || !targetDate) return;
    void handleCreate({
      title: t("dropAction.eventTitleSick", { name: driverName }),
      description: t("dropAction.eventDesc", { number: driver.employee_number }),
      start_datetime: buildDatetime(targetDate, "00:00", false),
      end_datetime: buildDatetime(targetDate, "23:59", false),
      priority: "high",
      category: "driver-shift",
      driver_id: driver.id,
    });
  }

  function handleScheduleTraining() {
    if (!driver || !targetDate) return;
    setSelectedAction("training");
    setStep("goals");
  }

  function handleCustomSubmit() {
    if (!driver || !targetDate || !customTitle.trim()) return;
    void handleCreate({
      title: t("dropAction.eventTitleCustom", { name: driverName, title: customTitle.trim() }),
      description: t("dropAction.eventDesc", { number: driver.employee_number }),
      start_datetime: buildDatetime(targetDate, customStart, false),
      end_datetime: buildDatetime(targetDate, customEnd, false),
      priority: "medium",
      category: "driver-shift",
      driver_id: driver.id,
    });
  }

  const handleGoalsSave = useCallback(
    (goals: EventGoals) => {
      if (!driver || !targetDate || !selectedAction) return;

      if (selectedAction === "shift") {
        const shift = driver.default_shift;
        const times = SHIFT_TIMES[shift] ?? SHIFT_TIMES.morning;
        const shiftLabelKey = SHIFT_LABEL_KEYS[shift] ?? "shiftMorning";

        void handleCreate({
          title: t("dropAction.eventTitleShift", {
            name: driverName,
            shift: t(`dropAction.${shiftLabelKey}`),
          }),
          description: t("dropAction.eventDesc", {
            number: driver.employee_number,
          }),
          start_datetime: buildDatetime(targetDate, times.start, false),
          end_datetime: buildDatetime(targetDate, times.end, times.nextDay),
          priority: "medium",
          category: "driver-shift",
          goals,
          driver_id: driver.id,
        });
      } else {
        void handleCreate({
          title: t("dropAction.eventTitleTraining", { name: driverName }),
          description: t("dropAction.eventDesc", {
            number: driver.employee_number,
          }),
          start_datetime: buildDatetime(targetDate, "09:00", false),
          end_datetime: buildDatetime(targetDate, "11:00", false),
          priority: "medium",
          category: "maintenance",
          goals,
          driver_id: driver.id,
        });
      }
    },
    [driver, targetDate, selectedAction, handleCreate, t, driverName],
  );

  const handleGoalsBack = useCallback(() => {
    setStep("action");
    setSelectedAction(null);
  }, []);

  function handleOpenChange(nextOpen: boolean) {
    if (!nextOpen) {
      setIsSaving(false);
      setStep("action");
      setSelectedAction(null);
      setShowCustomForm(false);
      setCustomTitle("");
      setCustomStart("09:00");
      setCustomEnd("17:00");
    }
    onOpenChange(nextOpen);
  }

  if (!driver || !targetDate) return null;

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className={cn(step === "goals" && "sm:max-w-[36rem]")}>
        <DialogHeader>
          <DialogTitle>
            {step === "goals" ? t("goals.title") : t("dropAction.title")}
          </DialogTitle>
          <DialogDescription>
            {step === "goals"
              ? t("goals.subtitle", { name: driverName, date: formattedDate })
              : t("dropAction.description", { name: driverName, date: formattedDate })}
          </DialogDescription>
        </DialogHeader>

        {step === "goals" && selectedAction && driver && targetDate ? (
          <GoalsForm
            key={`goals-${selectedAction}`}
            driver={driver}
            targetDate={targetDate}
            actionType={selectedAction}
            isSaving={isSaving}
            onBack={handleGoalsBack}
            onSave={handleGoalsSave}
          />
        ) : !showCustomForm ? (
          <div className="flex flex-col gap-(--spacing-tight)">
            <ActionCard
              icon={<Clock className="size-4" />}
              title={t("dropAction.assignShift")}
              description={t("dropAction.assignShiftDesc", {
                shift: t(`dropAction.${SHIFT_LABEL_KEYS[driver.default_shift] ?? "shiftMorning"}`),
              })}
              onClick={handleAssignShift}
              disabled={isSaving}
            />
            <ActionCard
              icon={<CalendarOff className="size-4" />}
              title={t("dropAction.markLeave")}
              description={t("dropAction.markLeaveDesc")}
              onClick={handleMarkLeave}
              disabled={isSaving}
            />
            <ActionCard
              icon={<Thermometer className="size-4" />}
              title={t("dropAction.markSick")}
              description={t("dropAction.markSickDesc")}
              onClick={handleMarkSick}
              disabled={isSaving}
            />
            <ActionCard
              icon={<GraduationCap className="size-4" />}
              title={t("dropAction.scheduleTraining")}
              description={t("dropAction.scheduleTrainingDesc")}
              onClick={handleScheduleTraining}
              disabled={isSaving}
            />
            <ActionCard
              icon={<Pencil className="size-4" />}
              title={t("dropAction.customEvent")}
              description={t("dropAction.customEventDesc")}
              onClick={() => setShowCustomForm(true)}
              disabled={isSaving}
            />
          </div>
        ) : (
          <div className="flex flex-col gap-(--spacing-grid)">
            <div className="space-y-(--spacing-tight)">
              <Label htmlFor="custom-title">{t("dropAction.eventTitle")}</Label>
              <Input
                id="custom-title"
                value={customTitle}
                onChange={(e) => setCustomTitle(e.target.value)}
                placeholder={t("dropAction.eventTitle")}
              />
            </div>
            <div className="grid grid-cols-2 gap-(--spacing-inline)">
              <div className="space-y-(--spacing-tight)">
                <Label htmlFor="custom-start">{t("dropAction.startTime")}</Label>
                <Input
                  id="custom-start"
                  type="time"
                  value={customStart}
                  onChange={(e) => setCustomStart(e.target.value)}
                />
              </div>
              <div className="space-y-(--spacing-tight)">
                <Label htmlFor="custom-end">{t("dropAction.endTime")}</Label>
                <Input
                  id="custom-end"
                  type="time"
                  value={customEnd}
                  onChange={(e) => setCustomEnd(e.target.value)}
                />
              </div>
            </div>
            <div className="flex justify-end gap-(--spacing-inline)">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setShowCustomForm(false)}
                disabled={isSaving}
                className="cursor-pointer"
              >
                {t("dropAction.cancel")}
              </Button>
              <Button
                size="sm"
                onClick={handleCustomSubmit}
                disabled={isSaving || !customTitle.trim()}
                className="cursor-pointer"
              >
                {isSaving ? t("dropAction.saving") : t("dropAction.save")}
              </Button>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
