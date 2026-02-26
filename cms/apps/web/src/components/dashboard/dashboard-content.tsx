"use client";

import { useRef, useState, useCallback } from "react";
import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { useTranslations } from "next-intl";
import { useSession } from "next-auth/react";
import { Button } from "@/components/ui/button";
import {
  ResizablePanelGroup,
  ResizablePanel,
  ResizableHandle,
} from "@/components/ui/resizable";
import { useIsMobile } from "@/hooks/use-mobile";
import { DashboardMetrics } from "./dashboard-metrics";
import { CalendarPanel } from "./calendar-panel";
import { DriverRoster } from "./driver-roster";
import { DriverDropDialog } from "./driver-drop-dialog";
import { useDriversSummary } from "@/hooks/use-drivers-summary";
import type { Driver } from "@/types/driver";

interface DashboardContentProps {
  locale: string;
}

const SCHEDULE_ROLES = ["admin", "editor", "dispatcher"];

export function DashboardContent({ locale }: DashboardContentProps) {
  const t = useTranslations("dashboard");
  const { data: session } = useSession();
  const isMobile = useIsMobile();

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
        typeof (parsed as Record<string, unknown>).id !== "number" ||
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
    <div className="flex h-[calc(100vh-var(--spacing-page)*2)] flex-col gap-(--spacing-grid)">
      {/* Page header */}
      <div className="flex shrink-0 items-center justify-between">
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

      {/* Resizable layout: desktop (panels) vs mobile (stacked) */}
      {isMobile ? (
        <div className="flex min-h-0 flex-1 flex-col gap-(--spacing-grid)">
          <DashboardMetrics />
          <div className="min-h-0 flex-1">
            <CalendarPanel
              onDayDrop={canSchedule ? handleDayDrop : undefined}
              refetchRef={calendarRefetchRef}
            />
          </div>
        </div>
      ) : (
        <ResizablePanelGroup
          orientation="vertical"
          className="min-h-0 flex-1 overflow-hidden"
        >
          {/* TOP PANEL: Analytics metric cards */}
          <ResizablePanel defaultSize="20%" minSize="10%" maxSize="40%">
            <DashboardMetrics />
          </ResizablePanel>

          <ResizableHandle withHandle />

          {/* BOTTOM PANEL: Drivers + Calendar */}
          <ResizablePanel defaultSize="80%" minSize="40%">
            <ResizablePanelGroup
              orientation="horizontal"
              className="overflow-hidden"
            >
              {/* BOTTOM-LEFT: Driver roster */}
              <ResizablePanel defaultSize="25%" minSize="15%" maxSize="45%">
                <DriverRoster
                  drivers={drivers}
                  isLoading={driversLoading}
                  canDrag={canSchedule}
                />
              </ResizablePanel>

              <ResizableHandle withHandle />

              {/* BOTTOM-RIGHT: Operations calendar */}
              <ResizablePanel defaultSize="75%" minSize="40%">
                <CalendarPanel
                  onDayDrop={canSchedule ? handleDayDrop : undefined}
                  refetchRef={calendarRefetchRef}
                />
              </ResizablePanel>
            </ResizablePanelGroup>
          </ResizablePanel>
        </ResizablePanelGroup>
      )}

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
