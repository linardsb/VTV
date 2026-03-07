"use client";

import { useState, useCallback, useEffect } from "react";
import { useTranslations } from "next-intl";
import { useSession } from "next-auth/react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { DataOverview } from "@/components/gtfs/data-overview";
import { GTFSExport } from "@/components/gtfs/gtfs-export";
import { ComplianceExports } from "@/components/gtfs/compliance-exports";
import { GTFSImport } from "@/components/schedules/gtfs-import";
import { fetchGTFSStats, fetchFeeds } from "@/lib/gtfs-sdk";
import { fetchAgencies } from "@/lib/schedules-sdk";
import type { GTFSStats, GTFSFeed } from "@/types/gtfs";
import type { Agency } from "@/types/schedule";

export default function GTFSPage() {
  const t = useTranslations("gtfs");
  const { status } = useSession();

  const [stats, setStats] = useState<GTFSStats | null>(null);
  const [feeds, setFeeds] = useState<GTFSFeed[]>([]);
  const [agencies, setAgencies] = useState<Agency[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  const loadData = useCallback(async () => {
    setIsLoading(true);
    try {
      const [statsResult, feedsResult, agenciesResult] = await Promise.all([
        fetchGTFSStats(),
        fetchFeeds(),
        fetchAgencies(),
      ]);
      setStats(statsResult);
      setFeeds(feedsResult);
      setAgencies(agenciesResult);
    } catch (e) {
      console.warn("[gtfs] Failed to load data:", e);
      setStats(null);
      setFeeds([]);
      setAgencies([]);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (status !== "authenticated") return;
    void loadData();
  }, [loadData, status]);

  const handleImportComplete = useCallback(() => {
    void loadData();
  }, [loadData]);

  return (
    <div className="flex flex-col gap-(--spacing-grid) md:h-[calc(100vh-var(--spacing-page)*2)]">
      {/* Header */}
      <div>
        <h1 className="font-heading text-heading font-semibold text-foreground">
          {t("title")}
        </h1>
        <p className="hidden sm:block text-sm text-foreground-muted">
          {t("description")}
        </p>
      </div>

      {/* Tabs */}
      <Tabs
        defaultValue="overview"
        className="flex min-h-0 flex-1 flex-col"
      >
        <TabsList>
          <TabsTrigger value="overview" className="cursor-pointer">
            {t("tabs.overview")}
          </TabsTrigger>
          <TabsTrigger value="import" className="cursor-pointer">
            {t("tabs.import")}
          </TabsTrigger>
          <TabsTrigger value="export" className="cursor-pointer">
            {t("tabs.export")}
          </TabsTrigger>
          <TabsTrigger value="compliance" className="cursor-pointer">
            {t("tabs.compliance")}
          </TabsTrigger>
        </TabsList>

        <TabsContent
          value="overview"
          className="flex-1 overflow-auto rounded-lg border border-border mt-(--spacing-tight)"
        >
          <DataOverview
            stats={stats}
            feeds={feeds}
            isLoading={isLoading}
            onRefresh={loadData}
          />
        </TabsContent>

        <TabsContent
          value="import"
          className="flex-1 overflow-auto rounded-lg border border-border mt-(--spacing-tight)"
        >
          <GTFSImport onImportComplete={handleImportComplete} />
        </TabsContent>

        <TabsContent
          value="export"
          className="flex-1 overflow-auto rounded-lg border border-border mt-(--spacing-tight)"
        >
          <GTFSExport agencies={agencies} />
        </TabsContent>

        <TabsContent
          value="compliance"
          className="flex-1 overflow-auto rounded-lg border border-border mt-(--spacing-tight)"
        >
          <ComplianceExports agencies={agencies} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
