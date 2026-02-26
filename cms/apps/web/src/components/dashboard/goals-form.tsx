"use client";

import { useState, useEffect, useCallback } from "react";
import { useTranslations } from "next-intl";
import { X, Plus, Bus, Zap, TrainFront } from "lucide-react";
import { cn } from "@/lib/utils";
import type { Driver } from "@/types/driver";
import type { EventGoals, GoalItem, TransportType } from "@/types/event";
import type { Route } from "@/types/route";
import { fetchRoutes } from "@/lib/schedules-sdk";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";

interface GoalsFormProps {
  driver: Driver;
  targetDate: Date;
  actionType: "shift" | "training";
  isSaving: boolean;
  onBack: () => void;
  onSave: (goals: EventGoals) => void;
}

function getDefaultGoals(
  actionType: "shift" | "training",
  t: (key: string) => string,
): GoalItem[] {
  if (actionType === "shift") {
    return [
      { text: t("defaultPreTrip"), completed: false, item_type: "checklist" },
      { text: t("defaultRouteReport"), completed: false, item_type: "checklist" },
    ];
  }
  return [
    { text: t("defaultTrainingModule"), completed: false, item_type: "checklist" },
    { text: t("defaultAssessment"), completed: false, item_type: "checklist" },
  ];
}

function GoalItemRow({
  item,
  index,
  onRemove,
}: {
  item: GoalItem;
  index: number;
  onRemove: (index: number) => void;
}) {
  const t = useTranslations("dashboard.goals");
  return (
    <div className="flex items-center gap-(--spacing-inline)">
      <span className="flex-1 truncate text-sm text-foreground">
        {item.text}
      </span>
      <Button
        type="button"
        variant="ghost"
        size="sm"
        onClick={() => onRemove(index)}
        className="size-7 shrink-0 cursor-pointer p-0"
        aria-label={`${t("removeItem")} ${item.text}`}
      >
        <X className="size-3.5" />
      </Button>
    </div>
  );
}

function TransportToggle({
  value,
  onChange,
}: {
  value: TransportType | null;
  onChange: (val: TransportType | null) => void;
}) {
  const t = useTranslations("dashboard.goals");
  return (
    <ToggleGroup
      type="single"
      variant="outline"
      value={value ?? ""}
      onValueChange={(v: string) =>
        onChange(v === "" ? null : (v as TransportType))
      }
      className="w-full"
    >
      <ToggleGroupItem
        value="bus"
        className={cn(
          "flex-1 cursor-pointer gap-(--spacing-tight)",
          value === "bus" && "bg-transport-bus text-interactive-foreground",
        )}
        aria-label={t("bus")}
      >
        <Bus className="size-4" />
        <span className="text-xs">{t("bus")}</span>
      </ToggleGroupItem>
      <ToggleGroupItem
        value="trolleybus"
        className={cn(
          "flex-1 cursor-pointer gap-(--spacing-tight)",
          value === "trolleybus" &&
            "bg-transport-trolleybus text-interactive-foreground",
        )}
        aria-label={t("trolleybus")}
      >
        <Zap className="size-4" />
        <span className="text-xs">{t("trolleybus")}</span>
      </ToggleGroupItem>
      <ToggleGroupItem
        value="tram"
        className={cn(
          "flex-1 cursor-pointer gap-(--spacing-tight)",
          value === "tram" && "bg-transport-tram text-interactive-foreground",
        )}
        aria-label={t("tram")}
      >
        <TrainFront className="size-4" />
        <span className="text-xs">{t("tram")}</span>
      </ToggleGroupItem>
    </ToggleGroup>
  );
}

export function GoalsForm({
  driver,
  targetDate,
  actionType,
  isSaving,
  onBack,
  onSave,
}: GoalsFormProps) {
  const t = useTranslations("dashboard.goals");

  const [routeId, setRouteId] = useState<number | null>(null);
  const [transportType, setTransportType] = useState<TransportType | null>(
    null,
  );
  const [vehicleId, setVehicleId] = useState("");
  const [notes, setNotes] = useState("");
  const [goalItems, setGoalItems] = useState<GoalItem[]>(
    getDefaultGoals(actionType, t),
  );
  const [newGoalText, setNewGoalText] = useState("");
  const [routes, setRoutes] = useState<Route[]>([]);
  const [routesLoading, setRoutesLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    async function loadRoutes() {
      try {
        const result = await fetchRoutes({ page_size: 500 });
        if (!cancelled) {
          const qualifiedIds = driver.qualified_route_ids
            ? driver.qualified_route_ids
                .split(",")
                .map(Number)
                .filter(Boolean)
            : [];
          const filtered =
            qualifiedIds.length > 0
              ? result.items.filter((r: Route) => qualifiedIds.includes(r.id))
              : result.items;
          setRoutes(filtered);
        }
      } catch {
        // Silently handle — route select will show empty state
      } finally {
        if (!cancelled) setRoutesLoading(false);
      }
    }
    void loadRoutes();
    return () => {
      cancelled = true;
    };
  }, [driver.qualified_route_ids]);

  const handleAddGoal = useCallback(() => {
    if (!newGoalText.trim()) return;
    setGoalItems((prev) => [
      ...prev,
      { text: newGoalText.trim(), completed: false, item_type: "checklist" },
    ]);
    setNewGoalText("");
  }, [newGoalText]);

  const handleRemoveGoal = useCallback((index: number) => {
    setGoalItems((prev) => prev.filter((_, i) => i !== index));
  }, []);

  function handleSave() {
    const goals: EventGoals = {
      items: goalItems,
      route_id: routeId,
      transport_type: transportType,
      vehicle_id: vehicleId.trim() || null,
    };
    onSave(goals);
  }

  const driverName = `${driver.first_name} ${driver.last_name}`;
  const formattedDate = targetDate.toLocaleDateString();

  return (
    <div className="flex flex-col gap-(--spacing-grid)">
      <p className="text-sm text-foreground-muted">
        {t("subtitle", { name: driverName, date: formattedDate })}
      </p>

      {/* Route Assignment */}
      <div className="space-y-(--spacing-tight)">
        <Label>{t("route")}</Label>
        {routesLoading ? (
          <p className="text-sm text-foreground-muted">{t("routeLoading")}</p>
        ) : routes.length === 0 ? (
          <p className="text-sm text-foreground-muted">
            {t("routeNoQualified")}
          </p>
        ) : (
          <Select
            value={routeId !== null ? String(routeId) : ""}
            onValueChange={(v) => setRouteId(v ? Number(v) : null)}
          >
            <SelectTrigger className="cursor-pointer">
              <SelectValue placeholder={t("routePlaceholder")} />
            </SelectTrigger>
            <SelectContent>
              {routes.map((route) => (
                <SelectItem
                  key={route.id}
                  value={String(route.id)}
                  className="cursor-pointer"
                >
                  {route.route_short_name} — {route.route_long_name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}
      </div>

      {/* Transport Type */}
      <div className="space-y-(--spacing-tight)">
        <Label>{t("transportType")}</Label>
        <TransportToggle value={transportType} onChange={setTransportType} />
      </div>

      {/* Vehicle Number */}
      <div className="space-y-(--spacing-tight)">
        <Label htmlFor="vehicle-id">{t("vehicle")}</Label>
        <Input
          id="vehicle-id"
          value={vehicleId}
          onChange={(e) => setVehicleId(e.target.value)}
          placeholder={t("vehiclePlaceholder")}
        />
      </div>

      {/* Goal Checklist */}
      <div className="space-y-(--spacing-tight)">
        <Label>
          {actionType === "training" ? t("itemsTraining") : t("items")}
        </Label>
        <div className="flex flex-col gap-(--spacing-tight) rounded-lg border border-border-subtle p-(--spacing-card)">
          {goalItems.map((item, index) => (
            <GoalItemRow
              key={`goal-${String(index)}`}
              item={item}
              index={index}
              onRemove={handleRemoveGoal}
            />
          ))}
          <div className="flex items-center gap-(--spacing-inline)">
            <Input
              value={newGoalText}
              onChange={(e) => setNewGoalText(e.target.value)}
              placeholder={t("addItemPlaceholder")}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  handleAddGoal();
                }
              }}
              className="flex-1"
            />
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={handleAddGoal}
              disabled={!newGoalText.trim()}
              className="shrink-0 cursor-pointer"
            >
              <Plus className="mr-1 size-3.5" />
              {t("addItem")}
            </Button>
          </div>
        </div>
      </div>

      {/* Performance Notes */}
      <div className="space-y-(--spacing-tight)">
        <Label htmlFor="goals-notes">{t("notes")}</Label>
        <Textarea
          id="goals-notes"
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          placeholder={t("notesPlaceholder")}
          rows={3}
        />
      </div>

      {/* Actions */}
      <div className="flex justify-end gap-(--spacing-inline)">
        <Button
          variant="outline"
          size="sm"
          onClick={onBack}
          disabled={isSaving}
          className="cursor-pointer"
        >
          {t("back")}
        </Button>
        <Button
          size="sm"
          onClick={handleSave}
          disabled={isSaving}
          className="cursor-pointer"
        >
          {isSaving ? t("saving") : t("save")}
        </Button>
      </div>
    </div>
  );
}
