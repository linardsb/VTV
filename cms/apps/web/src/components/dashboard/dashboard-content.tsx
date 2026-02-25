"use client";

import { useRef, useState, useCallback } from "react";
import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { useTranslations } from "next-intl";
import { useSession } from "next-auth/react";
import { Button } from "@/components/ui/button";
import { DashboardMetrics } from "./dashboard-metrics";
import { CalendarPanel } from "./calendar-panel";
import { DriverRoster } from "./driver-roster";
import { DriverDropDialog } from "./driver-drop-dialog";
import { useDriversSummary } from "@/hooks/use-drivers-summary";
import type { Driver } from "@/types/driver";

interface DashboardContentProps {
  locale: string;
}

const SCHEDULE_ROLES = ["admin", "editor"];

export function DashboardContent({ locale }: DashboardContentProps) {
  const t = useTranslations("dashboard");
  const { data: session } = useSession();

  const { drivers, isLoading: driversLoading } = useDriversSummary();

  const [dropDriver, setDropDriver] = useState<Driver | null>(null);
  const [dropDate, setDropDate] = useState<Date | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);

  const calendarRefetchRef = useRef<(() => Promise<void>) | null>(null);

  const userRole: string = (session?.user?.role as string) ?? "";
  const canSchedule = SCHEDULE_ROLES.includes(userRole);

  const handleDayDrop = useCallback((date: Date, driverJson: string) => {
    try {
      const parsed: unknown = JSON.parse(driverJson);
      if (
        typeof parsed !== "object" ||
        parsed === null ||
        typeof (parsed as Record<string, unknown>).id !== "string" ||
        typeof (parsed as Record<string, unknown>).first_name !== "string" ||
        typeof (parsed as Record<string, unknown>).last_name !== "string"
      ) {
        return;
      }
      setDropDriver(parsed as Driver);
      setDropDate(date);
      setDialogOpen(true);
    } catch {
      /* ignore malformed data */
    }
  }, []);

  const handleEventCreated = useCallback(() => {
    setDialogOpen(false);
    void calendarRefetchRef.current?.();
  }, []);

  return (
    <div className="space-y-(--spacing-section)">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <h1 className="font-heading text-heading font-semibold text-foreground">
          {t("title")}
        </h1>
        <Button asChild variant="outline" className="cursor-pointer">
          <Link href={`/${locale}/routes`}>
            {t("manageRoutes")}
            <ArrowRight className="ml-2 size-4" aria-hidden="true" />
          </Link>
        </Button>
      </div>

      {/* Metrics panel */}
      <DashboardMetrics />

      {/* Main area: driver roster + calendar */}
      <div className="flex min-h-[calc(100vh-14rem)] gap-(--spacing-grid)">
        {/* Left: driver roster (hidden on mobile) */}
        <div className="hidden w-64 shrink-0 lg:block">
          <DriverRoster
            drivers={drivers}
            isLoading={driversLoading}
            canDrag={canSchedule}
          />
        </div>

        {/* Right: calendar */}
        <div className="min-w-0 flex-1">
          <CalendarPanel
            onDayDrop={canSchedule ? handleDayDrop : undefined}
            refetchRef={calendarRefetchRef}
          />
        </div>
      </div>

      {/* Drop action dialog */}
      <DriverDropDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        driver={dropDriver}
        targetDate={dropDate}
        onEventCreated={handleEventCreated}
      />
    </div>
  );
}
