"use client";

import { useState, useCallback, useMemo } from "react";
import { useTranslations } from "next-intl";
import { useSession } from "next-auth/react";
import { toast } from "sonner";
import {
  Pencil,
  Trash2,
  Plus,
  Clock,
  CalendarOff,
  Thermometer,
  GraduationCap,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type { CalendarEvent } from "@/types/dashboard";
import type {
  EventGoals,
  GoalItem,
  EventUpdate,
  EventCategory,
  EventPriority,
  EventCreate,
} from "@/types/event";
import { updateEvent, deleteEvent, createEvent } from "@/lib/events-sdk";
import type { GoalStatus } from "./goal-progress-badge";
import { Checkbox } from "@/components/ui/checkbox";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { getEventCardStyle } from "./event-styles";

/* ── helpers ─────────────────────────────────────────────────── */

function formatTime(date: Date): string {
  return date.toLocaleTimeString(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

function formatDateISO(date: Date): string {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

function formatTimeHHMM(date: Date): string {
  const h = String(date.getHours()).padStart(2, "0");
  const mi = String(date.getMinutes()).padStart(2, "0");
  return `${h}:${mi}`;
}

function buildISO(dateStr: string, timeStr: string): string {
  const [y, mo, d] = dateStr.split("-").map(Number);
  const [h, mi] = timeStr.split(":").map(Number);
  const dt = new Date(y, mo - 1, d, h, mi, 0, 0);
  return dt.toISOString();
}

const SHIFT_TIMES: Record<
  string,
  { start: string; end: string; nextDay: boolean }
> = {
  morning: { start: "05:00", end: "13:00", nextDay: false },
  afternoon: { start: "13:00", end: "21:00", nextDay: false },
  evening: { start: "17:00", end: "01:00", nextDay: true },
  night: { start: "22:00", end: "06:00", nextDay: true },
};

function buildDatetime(date: Date, time: string, nextDay: boolean): string {
  const [hours, minutes] = time.split(":").map(Number);
  const d = new Date(date);
  if (nextDay) d.setDate(d.getDate() + 1);
  d.setHours(hours, minutes, 0, 0);
  return d.toISOString();
}

const statusTextStyles: Record<GoalStatus, string> = {
  "not-started": "text-foreground-muted",
  "in-progress": "text-status-delayed",
  completed: "text-status-ontime",
};

const barColorStyles: Record<GoalStatus, string> = {
  "not-started": "bg-foreground/20",
  "in-progress": "bg-status-delayed",
  completed: "bg-status-ontime",
};

const SCHEDULE_ROLES = ["admin", "editor", "dispatcher"];

const PRIORITIES: EventPriority[] = ["high", "medium", "low"];
const CATEGORIES: EventCategory[] = [
  "maintenance",
  "route-change",
  "driver-shift",
  "service-alert",
];

const priorityBadgeStyles: Record<EventPriority, string> = {
  high: "bg-destructive/15 text-destructive border-destructive/30",
  medium: "bg-status-delayed/15 text-status-delayed border-status-delayed/30",
  low: "bg-foreground/10 text-foreground-muted border-border",
};

/* ── module-scope sub-components ─────────────────────────────── */

function GoalItemRow({
  item,
  index,
  onToggle,
}: {
  item: GoalItem;
  index: number;
  onToggle: (index: number) => void;
}) {
  return (
    <label className="flex cursor-pointer items-center gap-(--spacing-inline) py-(--spacing-tight)">
      <Checkbox
        checked={item.completed}
        onCheckedChange={() => onToggle(index)}
      />
      <span
        className={cn(
          "text-sm",
          item.completed
            ? "text-foreground-muted line-through"
            : "text-foreground",
        )}
      >
        {item.text}
      </span>
    </label>
  );
}

function ActionCard({
  icon,
  title,
  description,
  onClick,
  disabled,
}: {
  icon: React.ReactNode;
  title: string;
  description: string;
  onClick: () => void;
  disabled: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={cn(
        "flex w-full items-center gap-(--spacing-inline) rounded-lg border border-border-subtle p-(--spacing-card) text-left transition-colors duration-200 hover:border-border hover:bg-surface cursor-pointer",
        disabled && "pointer-events-none opacity-50",
      )}
    >
      <div className="flex size-8 shrink-0 items-center justify-center rounded-md bg-interactive/10 text-interactive">
        {icon}
      </div>
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium text-foreground">{title}</p>
        <p className="text-xs text-foreground-muted">{description}</p>
      </div>
    </button>
  );
}

/* ── types ────────────────────────────────────────────────────── */

type PanelStep = "view" | "edit" | "delete-confirm";

interface EventGoalPanelProps {
  event: CalendarEvent | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onEventUpdated: () => void;
  onEventDeleted: () => void;
}

/* ── main component ──────────────────────────────────────────── */

export function EventGoalPanel({
  event,
  open,
  onOpenChange,
  onEventUpdated,
  onEventDeleted,
}: EventGoalPanelProps) {
  const tPanel = useTranslations("dashboard.eventPanel");
  const tGoals = useTranslations("dashboard.goals");
  const tDrop = useTranslations("dashboard.dropAction");
  const tPriority = useTranslations("dashboard.priority");
  const { data: session } = useSession();

  const userRole: string = (session?.user?.role as string) ?? "";
  const canEdit = SCHEDULE_ROLES.includes(userRole);

  /* ── state ─────────────────────────────── */
  const [step, setStep] = useState<PanelStep>("view");
  const [isSaving, setIsSaving] = useState(false);

  // Goal state
  const [goalItems, setGoalItems] = useState<GoalItem[]>(
    event?.goals?.items ?? [],
  );
  const [goalsDirty, setGoalsDirty] = useState(false);
  const [showAddGoal, setShowAddGoal] = useState(false);
  const [newGoalText, setNewGoalText] = useState("");

  // Edit fields
  const [editTitle, setEditTitle] = useState("");
  const [editDescription, setEditDescription] = useState("");
  const [editStartDate, setEditStartDate] = useState("");
  const [editStartTime, setEditStartTime] = useState("");
  const [editEndDate, setEditEndDate] = useState("");
  const [editEndTime, setEditEndTime] = useState("");
  const [editPriority, setEditPriority] = useState<EventPriority>("medium");
  const [editCategory, setEditCategory] = useState<EventCategory>("driver-shift");

  /* ── derived ───────────────────────────── */
  const hasGoals = goalItems.length > 0;
  const localDone = goalItems.filter((g) => g.completed).length;
  const localTotal = goalItems.length;
  const pct =
    localTotal > 0 ? Math.round((localDone / localTotal) * 100) : 0;
  const status: GoalStatus =
    localTotal === 0
      ? "not-started"
      : localDone === 0
        ? "not-started"
        : localDone === localTotal
          ? "completed"
          : "in-progress";

  const isDriverEvent = Boolean(event?.driver_id) || event?.category === "driver-shift";

  const dialogTitle = useMemo(() => {
    if (step === "delete-confirm") return tPanel("deleteTitle");
    return tPanel("title");
  }, [step, tPanel]);

  /* ── callbacks ─────────────────────────── */

  const initEditFields = useCallback(() => {
    if (!event) return;
    setEditTitle(event.title);
    setEditDescription(event.description ?? "");
    setEditStartDate(formatDateISO(event.start));
    setEditStartTime(formatTimeHHMM(event.start));
    setEditEndDate(formatDateISO(event.end));
    setEditEndTime(formatTimeHHMM(event.end));
    setEditPriority(event.priority);
    setEditCategory(event.category);
  }, [event]);

  const handleStartEdit = useCallback(() => {
    initEditFields();
    setStep("edit");
  }, [initEditFields]);

  const handleCancelEdit = useCallback(() => {
    setStep("view");
  }, []);

  const handleToggleGoal = useCallback((index: number) => {
    setGoalItems((prev) =>
      prev.map((item, i) =>
        i === index ? { ...item, completed: !item.completed } : item,
      ),
    );
    setGoalsDirty(true);
  }, []);

  const handleAddGoal = useCallback(() => {
    if (!newGoalText.trim()) return;
    const newItem: GoalItem = {
      text: newGoalText.trim(),
      completed: false,
      item_type: "checklist",
    };
    setGoalItems((prev) => [...prev, newItem]);
    setNewGoalText("");
    setGoalsDirty(true);
  }, [newGoalText]);

  const handleSaveGoals = useCallback(async () => {
    if (!event) return;
    setIsSaving(true);
    try {
      const updatedGoals: EventGoals = {
        items: goalItems,
        route_id: event.goals?.route_id ?? null,
        transport_type: event.goals?.transport_type ?? null,
        vehicle_id: event.goals?.vehicle_id ?? null,
      };
      await updateEvent(Number(event.id), { goals: updatedGoals });
      toast.success(tPanel("updated"));
      setGoalsDirty(false);
      onEventUpdated();
    } catch {
      toast.error(tPanel("updateError"));
    } finally {
      setIsSaving(false);
    }
  }, [event, goalItems, tPanel, onEventUpdated]);

  const handleSaveEdit = useCallback(async () => {
    if (!event) return;
    setIsSaving(true);
    try {
      const update: EventUpdate = {
        title: editTitle,
        description: editDescription || null,
        start_datetime: buildISO(editStartDate, editStartTime),
        end_datetime: buildISO(editEndDate, editEndTime),
        priority: editPriority,
        category: editCategory,
      };
      await updateEvent(Number(event.id), update);
      toast.success(tPanel("updated"));
      onEventUpdated();
      onOpenChange(false);
    } catch {
      toast.error(tPanel("updateError"));
    } finally {
      setIsSaving(false);
    }
  }, [
    event,
    editTitle,
    editDescription,
    editStartDate,
    editStartTime,
    editEndDate,
    editEndTime,
    editPriority,
    editCategory,
    tPanel,
    onEventUpdated,
    onOpenChange,
  ]);

  const handleDelete = useCallback(async () => {
    if (!event) return;
    setIsSaving(true);
    try {
      await deleteEvent(Number(event.id));
      toast.success(tPanel("deleted"));
      onEventDeleted();
    } catch {
      toast.error(tPanel("deleteError"));
    } finally {
      setIsSaving(false);
    }
  }, [event, tPanel, onEventDeleted]);

  const handleQuickAction = useCallback(
    async (eventData: EventCreate) => {
      setIsSaving(true);
      try {
        await createEvent(eventData);
        toast.success(tDrop("created"));
        onEventUpdated();
      } catch {
        toast.error(tDrop("createError"));
      } finally {
        setIsSaving(false);
      }
    },
    [tDrop, onEventUpdated],
  );

  const handleAssignShift = useCallback(() => {
    if (!event) return;
    const driverName = event.title.split(" - ")[0];
    const times = SHIFT_TIMES.morning;
    void handleQuickAction({
      title: `${driverName} - ${tDrop("shiftMorning")}`,
      start_datetime: buildDatetime(event.start, times.start, false),
      end_datetime: buildDatetime(event.start, times.end, times.nextDay),
      priority: "medium",
      category: "driver-shift",
      ...(event.driver_id ? { driver_id: event.driver_id } : {}),
    });
  }, [event, tDrop, handleQuickAction]);

  const handleMarkLeave = useCallback(() => {
    if (!event) return;
    const driverName = event.title.split(" - ")[0];
    void handleQuickAction({
      title: tDrop("eventTitleLeave", { name: driverName }),
      start_datetime: buildDatetime(event.start, "00:00", false),
      end_datetime: buildDatetime(event.start, "23:59", false),
      priority: "low",
      category: "driver-shift",
      ...(event.driver_id ? { driver_id: event.driver_id } : {}),
    });
  }, [event, tDrop, handleQuickAction]);

  const handleMarkSick = useCallback(() => {
    if (!event) return;
    const driverName = event.title.split(" - ")[0];
    void handleQuickAction({
      title: tDrop("eventTitleSick", { name: driverName }),
      start_datetime: buildDatetime(event.start, "00:00", false),
      end_datetime: buildDatetime(event.start, "23:59", false),
      priority: "high",
      category: "driver-shift",
      ...(event.driver_id ? { driver_id: event.driver_id } : {}),
    });
  }, [event, tDrop, handleQuickAction]);

  const handleScheduleTraining = useCallback(() => {
    if (!event) return;
    const driverName = event.title.split(" - ")[0];
    void handleQuickAction({
      title: tDrop("eventTitleTraining", { name: driverName }),
      start_datetime: buildDatetime(event.start, "09:00", false),
      end_datetime: buildDatetime(event.start, "11:00", false),
      priority: "medium",
      category: "maintenance",
      ...(event.driver_id ? { driver_id: event.driver_id } : {}),
    });
  }, [event, tDrop, handleQuickAction]);

  /* ── render ────────────────────────────── */

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[32rem]">
        <DialogHeader>
          <DialogTitle>{dialogTitle}</DialogTitle>
          <DialogDescription className="sr-only">
            {event?.title ?? ""}
          </DialogDescription>
        </DialogHeader>

        {event && step === "view" && (
          <div className="flex flex-col gap-(--spacing-grid)">
            {/* Event info */}
            <div>
              <p
                className={cn(
                  "rounded-md p-(--spacing-cell) text-sm font-medium text-foreground",
                  getEventCardStyle(event.title, event.category),
                )}
              >
                {event.title}
              </p>
              <p className="mt-(--spacing-tight) text-xs text-foreground-muted">
                {event.start.toLocaleDateString()} ·{" "}
                {formatTime(event.start)} – {formatTime(event.end)}
              </p>
              {event.description && (
                <p className="mt-(--spacing-tight) text-xs text-foreground-muted">
                  {event.description}
                </p>
              )}
              <div className="mt-(--spacing-tight) flex flex-wrap gap-(--spacing-tight)">
                <Badge
                  variant="outline"
                  className={cn(
                    "text-xs",
                    priorityBadgeStyles[event.priority],
                  )}
                >
                  {tPriority(event.priority)}
                </Badge>
                <Badge variant="outline" className="text-xs">
                  {tPanel(`categories.${event.category}`)}
                </Badge>
              </div>
            </div>

            {/* Goal progress */}
            {hasGoals && (
              <>
                <Separator />
                <div>
                  <div className="mb-(--spacing-tight) flex items-center justify-between">
                    <p className="text-sm font-medium text-foreground">
                      {tGoals("goalProgress")}
                    </p>
                    <span
                      className={cn(
                        "text-xs font-medium",
                        statusTextStyles[status],
                      )}
                    >
                      {tGoals("progress", {
                        done: localDone,
                        total: localTotal,
                      })}
                    </span>
                  </div>
                  <div className="h-2 w-full overflow-hidden rounded-none bg-foreground/10">
                    <div
                      className={cn(
                        "h-full rounded-none transition-all duration-200",
                        barColorStyles[status],
                      )}
                      style={{ width: `${String(pct)}%` }}
                    />
                  </div>
                </div>

                {/* Goal checklist */}
                <div className="flex flex-col">
                  {goalItems.map((item, index) => (
                    <GoalItemRow
                      key={`goal-${String(index)}`}
                      item={item}
                      index={index}
                      onToggle={handleToggleGoal}
                    />
                  ))}
                </div>

                {/* Add goal input (when goals exist) */}
                {canEdit && (
                  <div className="flex items-center gap-(--spacing-inline)">
                    <Input
                      value={newGoalText}
                      onChange={(e) => setNewGoalText(e.target.value)}
                      placeholder={tPanel("addGoalPlaceholder")}
                      className="h-8 text-sm"
                      onKeyDown={(e) => {
                        if (e.key === "Enter") handleAddGoal();
                      }}
                    />
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={handleAddGoal}
                      disabled={!newGoalText.trim()}
                      className="h-8 cursor-pointer"
                    >
                      <Plus className="size-3.5" />
                    </Button>
                  </div>
                )}

                {/* Transport/route badges */}
                {(event.goals?.transport_type ||
                  event.goals?.vehicle_id) && (
                  <div className="flex flex-wrap gap-(--spacing-tight) text-xs text-foreground-muted">
                    {event.goals.transport_type && (
                      <span className="rounded-none bg-foreground/10 px-2 py-0.5">
                        {event.goals.transport_type}
                      </span>
                    )}
                    {event.goals.vehicle_id && (
                      <span className="rounded-none bg-foreground/10 px-2 py-0.5">
                        {event.goals.vehicle_id}
                      </span>
                    )}
                  </div>
                )}
              </>
            )}

            {/* No goals fallback */}
            {!hasGoals && !showAddGoal && (
              <div className="py-4 text-center">
                <p className="text-sm text-foreground-muted">
                  {tGoals("noGoals")}
                </p>
                {canEdit && (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setShowAddGoal(true)}
                    className="mt-(--spacing-tight) cursor-pointer"
                  >
                    <Plus className="mr-1 size-3.5" />
                    {tPanel("addGoals")}
                  </Button>
                )}
              </div>
            )}

            {/* Add goals input (when no goals yet) */}
            {!hasGoals && showAddGoal && (
              <div className="flex flex-col gap-(--spacing-tight)">
                <p className="text-sm font-medium text-foreground">
                  {tPanel("addGoals")}
                </p>
                <div className="flex items-center gap-(--spacing-inline)">
                  <Input
                    value={newGoalText}
                    onChange={(e) => setNewGoalText(e.target.value)}
                    placeholder={tPanel("addGoalPlaceholder")}
                    className="h-8 text-sm"
                    onKeyDown={(e) => {
                      if (e.key === "Enter") handleAddGoal();
                    }}
                  />
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={handleAddGoal}
                    disabled={!newGoalText.trim()}
                    className="h-8 cursor-pointer"
                  >
                    <Plus className="size-3.5" />
                  </Button>
                </div>
                {goalItems.length > 0 && (
                  <div className="flex flex-col">
                    {goalItems.map((item, index) => (
                      <GoalItemRow
                        key={`new-goal-${String(index)}`}
                        item={item}
                        index={index}
                        onToggle={handleToggleGoal}
                      />
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Quick actions — driver events only */}
            {isDriverEvent && canEdit && (
              <>
                <Separator />
                <div>
                  <p className="mb-(--spacing-tight) text-sm font-medium text-foreground">
                    {tPanel("quickActions")}
                  </p>
                  <div className="flex flex-col gap-(--spacing-tight)">
                    <ActionCard
                      icon={<Clock className="size-4" />}
                      title={tDrop("assignShift")}
                      description={tDrop("assignShiftDesc", {
                        shift: tDrop("shiftMorning"),
                      })}
                      onClick={handleAssignShift}
                      disabled={isSaving}
                    />
                    <ActionCard
                      icon={<CalendarOff className="size-4" />}
                      title={tDrop("markLeave")}
                      description={tDrop("markLeaveDesc")}
                      onClick={handleMarkLeave}
                      disabled={isSaving}
                    />
                    <ActionCard
                      icon={<Thermometer className="size-4" />}
                      title={tDrop("markSick")}
                      description={tDrop("markSickDesc")}
                      onClick={handleMarkSick}
                      disabled={isSaving}
                    />
                    <ActionCard
                      icon={<GraduationCap className="size-4" />}
                      title={tDrop("scheduleTraining")}
                      description={tDrop("scheduleTrainingDesc")}
                      onClick={handleScheduleTraining}
                      disabled={isSaving}
                    />
                  </div>
                </div>
              </>
            )}

            {/* Footer actions */}
            <div className="flex justify-end gap-(--spacing-inline)">
              {goalsDirty && (
                <Button
                  size="sm"
                  onClick={() => void handleSaveGoals()}
                  disabled={isSaving}
                  className="cursor-pointer"
                >
                  {isSaving ? tPanel("saving") : tPanel("save")}
                </Button>
              )}
              {canEdit && (
                <>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleStartEdit}
                    className="cursor-pointer"
                  >
                    <Pencil className="mr-1 size-3.5" />
                    {tPanel("edit")}
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setStep("delete-confirm")}
                    className="cursor-pointer text-destructive hover:text-destructive"
                  >
                    <Trash2 className="mr-1 size-3.5" />
                    {tPanel("delete")}
                  </Button>
                </>
              )}
            </div>
          </div>
        )}

        {/* ── Edit Mode ─────────────────────── */}
        {event && step === "edit" && (
          <div className="flex flex-col gap-(--spacing-grid)">
            <div className="flex flex-col gap-(--spacing-inline)">
              <Label htmlFor="edit-title">{tPanel("titleLabel")}</Label>
              <Input
                id="edit-title"
                value={editTitle}
                onChange={(e) => setEditTitle(e.target.value)}
              />
            </div>

            <div className="flex flex-col gap-(--spacing-inline)">
              <Label htmlFor="edit-description">
                {tPanel("description")}
              </Label>
              <Textarea
                id="edit-description"
                value={editDescription}
                onChange={(e) => setEditDescription(e.target.value)}
                placeholder={tPanel("descriptionPlaceholder")}
                rows={3}
              />
            </div>

            <div className="grid grid-cols-2 gap-(--spacing-inline)">
              <div className="flex flex-col gap-(--spacing-tight)">
                <Label htmlFor="edit-start-date">
                  {tPanel("startDate")}
                </Label>
                <Input
                  id="edit-start-date"
                  type="date"
                  value={editStartDate}
                  onChange={(e) => setEditStartDate(e.target.value)}
                />
              </div>
              <div className="flex flex-col gap-(--spacing-tight)">
                <Label htmlFor="edit-start-time">
                  {tPanel("startTime")}
                </Label>
                <Input
                  id="edit-start-time"
                  type="time"
                  value={editStartTime}
                  onChange={(e) => setEditStartTime(e.target.value)}
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-(--spacing-inline)">
              <div className="flex flex-col gap-(--spacing-tight)">
                <Label htmlFor="edit-end-date">{tPanel("endDate")}</Label>
                <Input
                  id="edit-end-date"
                  type="date"
                  value={editEndDate}
                  onChange={(e) => setEditEndDate(e.target.value)}
                />
              </div>
              <div className="flex flex-col gap-(--spacing-tight)">
                <Label htmlFor="edit-end-time">{tPanel("endTime")}</Label>
                <Input
                  id="edit-end-time"
                  type="time"
                  value={editEndTime}
                  onChange={(e) => setEditEndTime(e.target.value)}
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-(--spacing-inline)">
              <div className="flex flex-col gap-(--spacing-tight)">
                <Label>{tPanel("priority")}</Label>
                <Select
                  value={editPriority}
                  onValueChange={(v) => setEditPriority(v as EventPriority)}
                >
                  <SelectTrigger className="cursor-pointer">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {PRIORITIES.map((p) => (
                      <SelectItem key={p} value={p} className="cursor-pointer">
                        {tPriority(p)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="flex flex-col gap-(--spacing-tight)">
                <Label>{tPanel("category")}</Label>
                <Select
                  value={editCategory}
                  onValueChange={(v) => setEditCategory(v as EventCategory)}
                >
                  <SelectTrigger className="cursor-pointer">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {CATEGORIES.map((c) => (
                      <SelectItem key={c} value={c} className="cursor-pointer">
                        {tPanel(`categories.${c}`)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            {/* Edit footer */}
            <div className="flex justify-end gap-(--spacing-inline)">
              <Button
                variant="outline"
                size="sm"
                onClick={handleCancelEdit}
                disabled={isSaving}
                className="cursor-pointer"
              >
                {tPanel("cancel")}
              </Button>
              <Button
                size="sm"
                onClick={() => void handleSaveEdit()}
                disabled={isSaving}
                className="cursor-pointer"
              >
                {isSaving ? tPanel("saving") : tPanel("save")}
              </Button>
            </div>
          </div>
        )}

        {/* ── Delete Confirmation ────────────── */}
        {event && step === "delete-confirm" && (
          <div className="flex flex-col gap-(--spacing-grid)">
            <div>
              <p className="text-sm font-medium text-foreground">
                {event.title}
              </p>
              <p className="text-xs text-foreground-muted">
                {event.start.toLocaleDateString()} ·{" "}
                {formatTime(event.start)} – {formatTime(event.end)}
              </p>
            </div>

            <div className="rounded-md bg-destructive/10 p-(--spacing-card)">
              <p className="text-sm text-foreground">
                {tPanel("deleteConfirmation")}
              </p>
              <p className="mt-(--spacing-tight) text-xs text-foreground-muted">
                {tPanel("deleteWarning")}
              </p>
            </div>

            <div className="flex justify-end gap-(--spacing-inline)">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setStep("view")}
                disabled={isSaving}
                className="cursor-pointer"
              >
                {tPanel("deleteCancel")}
              </Button>
              <Button
                variant="destructive"
                size="sm"
                onClick={() => void handleDelete()}
                disabled={isSaving}
                className="cursor-pointer"
              >
                {isSaving ? tPanel("deleting") : tPanel("deleteConfirm")}
              </Button>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
