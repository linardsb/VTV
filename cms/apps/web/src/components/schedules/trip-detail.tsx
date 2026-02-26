"use client";

import { useState, useCallback, useEffect } from "react";
import { useTranslations } from "next-intl";
import { useLocale } from "next-intl";
import { Pencil, Trash2 } from "lucide-react";
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
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";
import { fetchTrip } from "@/lib/schedules-sdk";
import type { Trip, TripDetail as TripDetailType, StopTime } from "@/types/schedule";
import type { Route } from "@/types/route";
import type { Calendar } from "@/types/schedule";

interface TripDetailProps {
  trip: Trip | null;
  routes: Route[];
  calendars: Calendar[];
  isOpen: boolean;
  onClose: () => void;
  onEdit: (trip: Trip) => void;
  onDelete: (trip: Trip) => void;
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

export function TripDetail({
  trip,
  routes,
  calendars,
  isOpen,
  onClose,
  onEdit,
  onDelete,
  isReadOnly,
}: TripDetailProps) {
  const t = useTranslations("schedules.trips");
  const locale = useLocale();
  const [stopTimes, setStopTimes] = useState<StopTime[]>([]);
  const [isLoadingTimes, setIsLoadingTimes] = useState(false);

  const loadStopTimes = useCallback(async (tripId: number) => {
    setIsLoadingTimes(true);
    try {
      const detail: TripDetailType = await fetchTrip(tripId);
      setStopTimes(detail.stop_times);
    } catch {
      setStopTimes([]);
    } finally {
      setIsLoadingTimes(false);
    }
  }, []);

  useEffect(() => {
    if (trip && isOpen) {
      void loadStopTimes(trip.id);
    } else {
      setStopTimes([]);
    }
  }, [trip, isOpen, loadStopTimes]);

  if (!trip) return null;

  const routeName = routes.find((r) => r.id === trip.route_id);
  const calendarName = calendars.find((c) => c.id === trip.calendar_id);

  const dateFormatter = new Intl.DateTimeFormat(locale, {
    year: "numeric",
    month: "long",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-[36rem] max-h-[90vh] overflow-y-auto" showCloseButton>
        <DialogHeader>
          <DialogTitle className="font-heading text-heading font-semibold">
            {trip.gtfs_trip_id}
          </DialogTitle>
          <DialogDescription className="sr-only">
            {trip.gtfs_trip_id}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-(--spacing-card)">
          <div className="space-y-(--spacing-card)">
            <DetailRow label={t("route")}>
              {routeName ? `${routeName.route_short_name} - ${routeName.route_long_name}` : "-"}
            </DetailRow>
            <DetailRow label={t("calendar")}>
              {calendarName?.gtfs_service_id ?? "-"}
            </DetailRow>
            <DetailRow label={t("direction")}>
              {trip.direction_id !== null ? (
                <Badge variant="outline" className="text-xs">
                  {trip.direction_id === 0 ? t("outbound") : t("inbound")}
                </Badge>
              ) : "-"}
            </DetailRow>
            <DetailRow label={t("headsign")}>
              {trip.trip_headsign ?? "-"}
            </DetailRow>
            {trip.block_id && (
              <DetailRow label={t("blockId")}>
                <span className="font-mono">{trip.block_id}</span>
              </DetailRow>
            )}
            <DetailRow label={t("createdAt")}>
              {dateFormatter.format(new Date(trip.created_at))}
            </DetailRow>
          </div>

          <Separator />

          {/* Stop times */}
          <div className="space-y-(--spacing-inline)">
            <p className="text-xs font-medium text-label-text uppercase tracking-wide">
              {t("stopTimes")} ({stopTimes.length})
            </p>
            {isLoadingTimes ? (
              <div className="space-y-2">
                {Array.from({ length: 3 }, (_, i) => (
                  <Skeleton key={i} className="h-8 w-full" />
                ))}
              </div>
            ) : stopTimes.length === 0 ? (
              <p className="text-sm text-foreground-muted">{t("noStopTimes")}</p>
            ) : (
              <div className="rounded-md border border-border overflow-auto max-h-64">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="w-12">#</TableHead>
                      <TableHead>{t("arrival")}</TableHead>
                      <TableHead>{t("departure")}</TableHead>
                      <TableHead>{t("stopId")}</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {stopTimes.map((st) => (
                      <TableRow key={st.id}>
                        <TableCell className="text-foreground-muted">{st.stop_sequence}</TableCell>
                        <TableCell className="font-mono">{st.arrival_time}</TableCell>
                        <TableCell className="font-mono">{st.departure_time}</TableCell>
                        <TableCell className="font-mono text-foreground-muted">{st.stop_id}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}
          </div>

          {/* Actions */}
          {!isReadOnly && (
            <>
              <Separator />
              <div className="flex gap-(--spacing-inline)">
                <Button variant="outline" className="flex-1 cursor-pointer" onClick={() => onEdit(trip)}>
                  <Pencil className="mr-2 size-4" />
                  {t("edit")}
                </Button>
                <Button variant="destructive" className="cursor-pointer" onClick={() => onDelete(trip)}>
                  <Trash2 className="mr-2 size-4" />
                  {t("delete")}
                </Button>
              </div>
            </>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
