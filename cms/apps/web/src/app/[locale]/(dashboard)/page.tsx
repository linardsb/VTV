import { getTranslations } from "next-intl/server";
import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { DashboardMetrics } from "@/components/dashboard/dashboard-metrics";
import { CalendarGrid } from "@/components/dashboard/calendar-grid";
import {
  ResizablePanelGroup,
  ResizablePanel,
  ResizableHandle,
} from "@/components/ui/resizable";
import { MOCK_EVENTS } from "@/lib/mock-dashboard-data";

export const revalidate = 3600; // 1 hour — calendar uses mock data, metrics are client-side

export default async function DashboardPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  const t = await getTranslations("dashboard");

  return (
    <div className="space-y-(--spacing-section)">
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

      <ResizablePanelGroup orientation="vertical" className="min-h-[calc(100vh-6rem)]">
        {/* Metrics panel */}
        <ResizablePanel defaultSize={20} minSize={10}>
          <DashboardMetrics />
        </ResizablePanel>

        <ResizableHandle withHandle />

        {/* Calendar panel */}
        <ResizablePanel defaultSize={80} minSize={30}>
          <div className="h-full pt-(--spacing-grid)">
            <CalendarGrid events={MOCK_EVENTS} />
          </div>
        </ResizablePanel>
      </ResizablePanelGroup>
    </div>
  );
}
