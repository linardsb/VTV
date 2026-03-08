"use client";

import { useState, useCallback, useEffect } from "react";
import { useTranslations } from "next-intl";
import { useSession } from "next-auth/react";
import dynamic from "next/dynamic";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { cn } from "@/lib/utils";
import { fetchZoneEvents, fetchDwellReport } from "@/lib/geofences-sdk";
import type { Geofence, GeofenceEvent, DwellTimeReport } from "@/types/geofence";

const GeofenceMap = dynamic(
  () =>
    import("@/components/geofences/geofence-map").then((m) => m.GeofenceMap),
  {
    ssr: false,
    loading: () => <Skeleton className="h-[200px] w-full" />,
  },
);

interface GeofenceDetailProps {
  geofence: Geofence | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onEdit: () => void;
  onDelete: () => void;
  isReadOnly: boolean;
  canDelete: boolean;
}

const ZONE_TYPE_COLORS: Record<string, string> = {
  depot: "bg-interactive/10 text-interactive border-interactive/20",
  terminal: "bg-status-ontime/10 text-status-ontime border-status-ontime/20",
  restricted: "bg-status-critical/10 text-status-critical border-status-critical/20",
  customer: "bg-status-delayed/10 text-status-delayed border-status-delayed/20",
  custom: "bg-surface-secondary text-foreground-muted border-border",
};

const EVENT_TYPE_COLORS: Record<string, string> = {
  enter: "bg-status-ontime/10 text-status-ontime border-status-ontime/20",
  exit: "bg-status-delayed/10 text-status-delayed border-status-delayed/20",
  dwell_exceeded: "bg-status-critical/10 text-status-critical border-status-critical/20",
};

function DetailRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex justify-between py-1.5">
      <span className="text-sm text-foreground-muted">{label}</span>
      <span className="text-sm font-medium text-foreground text-right max-w-[60%] break-words">
        {value ?? "-"}
      </span>
    </div>
  );
}

function formatDwell(seconds: number | null): string {
  if (seconds === null) return "-";
  const mins = Math.floor(seconds / 60);
  if (mins < 1) return `${seconds}s`;
  return `${mins}m`;
}

export function GeofenceDetail({
  geofence,
  open,
  onOpenChange,
  onEdit,
  onDelete,
  isReadOnly,
  canDelete,
}: GeofenceDetailProps) {
  const t = useTranslations("geofences");
  const { status } = useSession();

  const [events, setEvents] = useState<GeofenceEvent[]>([]);
  const [eventsLoading, setEventsLoading] = useState(false);
  const [dwellReport, setDwellReport] = useState<DwellTimeReport | null>(null);
  const [dwellLoading, setDwellLoading] = useState(false);
  const [activeTab, setActiveTab] = useState("info");

  const loadEvents = useCallback(async () => {
    if (!geofence || status !== "authenticated") return;
    setEventsLoading(true);
    try {
      const result = await fetchZoneEvents(geofence.id, {
        page: 1,
        page_size: 10,
      });
      setEvents(result.items);
    } catch {
      // silently fail
    } finally {
      setEventsLoading(false);
    }
  }, [geofence, status]);

  const loadDwellReport = useCallback(async () => {
    if (!geofence || status !== "authenticated") return;
    setDwellLoading(true);
    try {
      const result = await fetchDwellReport(geofence.id, {});
      setDwellReport(result);
    } catch {
      // silently fail
    } finally {
      setDwellLoading(false);
    }
  }, [geofence, status]);

  useEffect(() => {
    if (!open || !geofence) return;
    if (activeTab === "events") void loadEvents();
    if (activeTab === "dwell") void loadDwellReport();
  }, [open, geofence, activeTab, loadEvents, loadDwellReport]);

  if (!geofence) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[36rem] max-h-[90vh] overflow-y-auto" showCloseButton>
        <DialogHeader>
          <DialogTitle className="font-heading text-heading font-semibold">
            {t("detail.title")}
          </DialogTitle>
          <DialogDescription className="sr-only">
            {t("detail.title")}
          </DialogDescription>
        </DialogHeader>

        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList className="w-full">
            <TabsTrigger value="info" className="flex-1 cursor-pointer">
              {t("detail.tabs.info")}
            </TabsTrigger>
            <TabsTrigger value="events" className="flex-1 cursor-pointer">
              {t("detail.tabs.events")}
            </TabsTrigger>
            <TabsTrigger value="dwell" className="flex-1 cursor-pointer">
              {t("detail.tabs.dwell")}
            </TabsTrigger>
          </TabsList>

          <TabsContent value="info" className="space-y-3 mt-(--spacing-card)">
            {/* Mini map preview */}
            <div className="h-[150px] border border-border">
              <GeofenceMap
                geofences={[geofence]}
                selectedGeofenceId={geofence.id}
                onSelectGeofence={() => {}}
              />
            </div>

            <DetailRow label={t("detail.name")} value={geofence.name} />
            <DetailRow
              label={t("detail.zoneType")}
              value={
                <Badge
                  variant="outline"
                  className={cn("text-xs", ZONE_TYPE_COLORS[geofence.zone_type] ?? "")}
                >
                  {t(`filters.${geofence.zone_type}`)}
                </Badge>
              }
            />
            <DetailRow label={t("detail.description")} value={geofence.description} />
            <DetailRow
              label={t("detail.alertOnEnter")}
              value={geofence.alert_on_enter ? "Yes" : "No"}
            />
            <DetailRow
              label={t("detail.alertOnExit")}
              value={geofence.alert_on_exit ? "Yes" : "No"}
            />
            <DetailRow
              label={t("detail.alertOnDwell")}
              value={geofence.alert_on_dwell ? "Yes" : "No"}
            />
            {geofence.alert_on_dwell && (
              <DetailRow
                label={t("detail.dwellThreshold")}
                value={t("dwell.minutes", { count: geofence.dwell_threshold_minutes ?? 0 })}
              />
            )}
            <DetailRow
              label={t("detail.severity")}
              value={geofence.alert_severity}
            />
            <DetailRow
              label={t("detail.status")}
              value={
                <Badge
                  variant="outline"
                  className={cn(
                    "text-xs",
                    geofence.is_active
                      ? "bg-status-ontime/10 text-status-ontime border-status-ontime/20"
                      : "bg-surface-secondary text-foreground-muted border-border",
                  )}
                >
                  {geofence.is_active ? t("table.active") : t("table.inactive")}
                </Badge>
              }
            />
            <DetailRow
              label={t("detail.createdAt")}
              value={new Date(geofence.created_at).toLocaleString()}
            />
          </TabsContent>

          <TabsContent value="events" className="mt-(--spacing-card)">
            {eventsLoading ? (
              <div className="space-y-2">
                {Array.from({ length: 3 }).map((_, i) => (
                  <Skeleton key={`ev-skel-${i}`} className="h-10 w-full" />
                ))}
              </div>
            ) : events.length === 0 ? (
              <p className="text-sm text-foreground-muted text-center py-4">
                {t("events.noEvents")}
              </p>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="text-xs">{t("events.vehicleId")}</TableHead>
                    <TableHead className="text-xs">{t("events.eventType")}</TableHead>
                    <TableHead className="text-xs">{t("events.enteredAt")}</TableHead>
                    <TableHead className="text-xs">{t("events.dwellTime")}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {events.map((event) => (
                    <TableRow key={event.id}>
                      <TableCell className="font-mono text-xs">
                        {event.vehicle_id}
                      </TableCell>
                      <TableCell>
                        <Badge
                          variant="outline"
                          className={cn(
                            "text-xs",
                            EVENT_TYPE_COLORS[event.event_type] ?? "",
                          )}
                        >
                          {t(`events.${event.event_type}`)}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-xs text-foreground-muted">
                        {new Date(event.entered_at).toLocaleString()}
                      </TableCell>
                      <TableCell className="text-xs text-foreground-muted">
                        {formatDwell(event.dwell_seconds)}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </TabsContent>

          <TabsContent value="dwell" className="mt-(--spacing-card)">
            {dwellLoading ? (
              <div className="space-y-2">
                {Array.from({ length: 4 }).map((_, i) => (
                  <Skeleton key={`dw-skel-${i}`} className="h-16 w-full" />
                ))}
              </div>
            ) : !dwellReport ? (
              <p className="text-sm text-foreground-muted text-center py-4">
                {t("dwell.noData")}
              </p>
            ) : (
              <div className="grid grid-cols-2 gap-(--spacing-card)">
                <div className="border border-border p-(--spacing-card)">
                  <p className="text-xs text-foreground-muted">{t("dwell.totalEvents")}</p>
                  <p className="text-lg font-heading font-semibold text-foreground">
                    {dwellReport.total_events}
                  </p>
                </div>
                <div className="border border-border p-(--spacing-card)">
                  <p className="text-xs text-foreground-muted">{t("dwell.avgDwell")}</p>
                  <p className="text-lg font-heading font-semibold text-foreground">
                    {formatDwell(dwellReport.avg_dwell_seconds)}
                  </p>
                </div>
                <div className="border border-border p-(--spacing-card)">
                  <p className="text-xs text-foreground-muted">{t("dwell.maxDwell")}</p>
                  <p className="text-lg font-heading font-semibold text-foreground">
                    {formatDwell(dwellReport.max_dwell_seconds)}
                  </p>
                </div>
                <div className="border border-border p-(--spacing-card)">
                  <p className="text-xs text-foreground-muted">{t("dwell.vehiclesInside")}</p>
                  <p className="text-lg font-heading font-semibold text-foreground">
                    {dwellReport.vehicles_inside}
                  </p>
                </div>
              </div>
            )}
          </TabsContent>
        </Tabs>

        {(!isReadOnly || canDelete) && (
          <>
            <Separator />
            <div className="flex gap-2">
              {!isReadOnly && (
                <Button
                  variant="outline"
                  className="flex-1 cursor-pointer"
                  onClick={onEdit}
                >
                  {t("actions.edit")}
                </Button>
              )}
              {canDelete && (
                <Button
                  variant="destructive"
                  className="flex-1 cursor-pointer"
                  onClick={onDelete}
                >
                  {t("actions.delete")}
                </Button>
              )}
            </div>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
