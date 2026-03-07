"use client";

import { useState, useCallback } from "react";
import { useTranslations } from "next-intl";
import { Download, FileCode2, Building2, Route, Navigation, MapPin } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import {
  exportNeTEx,
  exportSiriVM,
  exportSiriSM,
  fetchComplianceStatus,
} from "@/lib/gtfs-sdk";
import type { ExportMetadata } from "@/types/gtfs";

/* ── Module-scope sub-component ── */

interface StatusSectionProps {
  status: ExportMetadata | null;
  isLoading: boolean;
  t: (key: string) => string;
}

function StatusSection({ status, isLoading, t }: StatusSectionProps) {
  if (isLoading) {
    return (
      <div className="space-y-(--spacing-grid)">
        <Skeleton className="h-4 w-32" />
        <div className="grid grid-cols-2 gap-(--spacing-grid) sm:grid-cols-4">
          <Skeleton className="h-16" />
          <Skeleton className="h-16" />
          <Skeleton className="h-16" />
          <Skeleton className="h-16" />
        </div>
      </div>
    );
  }

  if (!status) return null;

  const entityItems = [
    { label: t("status.agencies"), count: status.entity_counts.agencies, icon: Building2 },
    { label: t("status.routes"), count: status.entity_counts.routes, icon: Route },
    { label: t("status.trips"), count: status.entity_counts.trips, icon: Navigation },
    { label: t("status.stops"), count: status.entity_counts.stops, icon: MapPin },
  ];

  return (
    <div className="space-y-(--spacing-grid)">
      <h3 className="text-sm font-semibold text-foreground">
        {t("status.title")}
      </h3>

      <div className="flex flex-wrap items-center gap-(--spacing-grid) text-xs text-foreground-muted">
        <span>
          {t("status.format")}: <Badge variant="outline">{status.format}</Badge>
        </span>
        <span>
          {t("status.version")}: <Badge variant="outline">{status.version}</Badge>
        </span>
        <span>
          {t("status.codespace")}: <span className="font-mono text-foreground">{status.codespace}</span>
        </span>
        <span>
          {t("status.generatedAt")}:{" "}
          <span className="text-foreground">
            {new Date(status.generated_at).toLocaleString()}
          </span>
        </span>
      </div>

      <div className="grid grid-cols-2 gap-(--spacing-grid) sm:grid-cols-4">
        {entityItems.map((item) => (
          <div
            key={item.label}
            className="flex items-center gap-(--spacing-inline) border border-border p-(--spacing-card)"
          >
            <item.icon className="size-4 shrink-0 text-foreground-muted" aria-hidden="true" />
            <div>
              <p className="text-lg font-semibold text-foreground">{item.count}</p>
              <p className="text-xs text-foreground-muted">{item.label}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ── Main component ── */

interface ComplianceExportsProps {
  agencies: Array<{ id: number; agency_name: string }>;
}

export function ComplianceExports({ agencies }: ComplianceExportsProps) {
  const t = useTranslations("gtfs.compliance");

  const [netexAgency, setNetexAgency] = useState<string>("all");
  const [siriVmRoute, setSiriVmRoute] = useState("");
  const [siriVmFeed, setSiriVmFeed] = useState("");
  const [siriSmStop, setSiriSmStop] = useState("");
  const [siriSmFeed, setSiriSmFeed] = useState("");
  const [downloadingNetex, setDownloadingNetex] = useState(false);
  const [downloadingSiriVm, setDownloadingSiriVm] = useState(false);
  const [downloadingSiriSm, setDownloadingSiriSm] = useState(false);
  const [status, setStatus] = useState<ExportMetadata | null>(null);
  const [statusLoading, setStatusLoading] = useState(false);

  const loadStatus = useCallback(async () => {
    setStatusLoading(true);
    try {
      const data = await fetchComplianceStatus();
      setStatus(data);
    } catch {
      toast.error(t("status.loadError"));
    } finally {
      setStatusLoading(false);
    }
  }, [t]);

  const handleNetexDownload = useCallback(async () => {
    setDownloadingNetex(true);
    try {
      const agencyId =
        netexAgency === "all" ? undefined : Number(netexAgency);
      await exportNeTEx(agencyId);
      toast.success(t("netex.downloadSuccess"));
    } catch {
      toast.error(t("netex.downloadError"));
    } finally {
      setDownloadingNetex(false);
    }
  }, [netexAgency, t]);

  const handleSiriVmDownload = useCallback(async () => {
    setDownloadingSiriVm(true);
    try {
      await exportSiriVM(siriVmRoute || undefined, siriVmFeed || undefined);
      toast.success(t("siriVm.downloadSuccess"));
    } catch {
      toast.error(t("siriVm.downloadError"));
    } finally {
      setDownloadingSiriVm(false);
    }
  }, [siriVmRoute, siriVmFeed, t]);

  const handleSiriSmDownload = useCallback(async () => {
    if (!siriSmStop.trim()) {
      toast.error(t("siriSm.stopRequired"));
      return;
    }
    setDownloadingSiriSm(true);
    try {
      await exportSiriSM(siriSmStop.trim(), siriSmFeed || undefined);
      toast.success(t("siriSm.downloadSuccess"));
    } catch {
      toast.error(t("siriSm.downloadError"));
    } finally {
      setDownloadingSiriSm(false);
    }
  }, [siriSmStop, siriSmFeed, t]);

  return (
    <div className="space-y-(--spacing-grid) p-(--spacing-card)">
      {/* Header */}
      <div className="space-y-(--spacing-tight)">
        <h3 className="text-sm font-semibold text-foreground">{t("title")}</h3>
        <p className="text-xs text-foreground-muted">{t("description")}</p>
      </div>

      {/* Export cards grid */}
      <div className="grid gap-(--spacing-grid) lg:grid-cols-3">
        {/* NeTEx Card */}
        <div className="space-y-(--spacing-grid) border border-border p-(--spacing-card)">
          <div className="space-y-(--spacing-tight)">
            <div className="flex items-center gap-(--spacing-inline)">
              <FileCode2 className="size-4 text-foreground-muted" aria-hidden="true" />
              <h4 className="text-sm font-semibold text-foreground">
                {t("netex.title")}
              </h4>
            </div>
            <p className="text-xs text-foreground-muted">{t("netex.description")}</p>
          </div>

          <div className="space-y-(--spacing-tight)">
            <Label htmlFor="netex-agency" className="text-xs font-medium text-foreground-muted">
              {t("netex.agencyFilter")}
            </Label>
            <Select value={netexAgency} onValueChange={setNetexAgency}>
              <SelectTrigger id="netex-agency" className="cursor-pointer">
                <SelectValue placeholder={t("netex.allAgencies")} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all" className="cursor-pointer">
                  {t("netex.allAgencies")}
                </SelectItem>
                {agencies.map((agency) => (
                  <SelectItem
                    key={agency.id}
                    value={String(agency.id)}
                    className="cursor-pointer"
                  >
                    {agency.agency_name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <Button
            className="w-full cursor-pointer"
            disabled={downloadingNetex}
            onClick={handleNetexDownload}
          >
            {downloadingNetex ? (
              t("netex.downloading")
            ) : (
              <>
                <Download className="mr-1 size-4" aria-hidden="true" />
                {t("netex.downloadButton")}
              </>
            )}
          </Button>

          <p className="text-xs text-foreground-muted">{t("netex.includesNote")}</p>
        </div>

        {/* SIRI-VM Card */}
        <div className="space-y-(--spacing-grid) border border-border p-(--spacing-card)">
          <div className="space-y-(--spacing-tight)">
            <div className="flex items-center gap-(--spacing-inline)">
              <FileCode2 className="size-4 text-foreground-muted" aria-hidden="true" />
              <h4 className="text-sm font-semibold text-foreground">
                {t("siriVm.title")}
              </h4>
            </div>
            <p className="text-xs text-foreground-muted">{t("siriVm.description")}</p>
          </div>

          <div className="space-y-(--spacing-tight)">
            <Label htmlFor="siri-vm-route" className="text-xs font-medium text-foreground-muted">
              {t("siriVm.routeFilter")}
            </Label>
            <Input
              id="siri-vm-route"
              value={siriVmRoute}
              onChange={(e) => setSiriVmRoute(e.target.value)}
              placeholder={t("siriVm.routePlaceholder")}
              className="text-sm"
            />
          </div>

          <div className="space-y-(--spacing-tight)">
            <Label htmlFor="siri-vm-feed" className="text-xs font-medium text-foreground-muted">
              {t("siriVm.feedFilter")}
            </Label>
            <Input
              id="siri-vm-feed"
              value={siriVmFeed}
              onChange={(e) => setSiriVmFeed(e.target.value)}
              placeholder={t("siriVm.feedPlaceholder")}
              className="text-sm"
            />
          </div>

          <Button
            className="w-full cursor-pointer"
            disabled={downloadingSiriVm}
            onClick={handleSiriVmDownload}
          >
            {downloadingSiriVm ? (
              t("siriVm.downloading")
            ) : (
              <>
                <Download className="mr-1 size-4" aria-hidden="true" />
                {t("siriVm.downloadButton")}
              </>
            )}
          </Button>
        </div>

        {/* SIRI-SM Card */}
        <div className="space-y-(--spacing-grid) border border-border p-(--spacing-card)">
          <div className="space-y-(--spacing-tight)">
            <div className="flex items-center gap-(--spacing-inline)">
              <FileCode2 className="size-4 text-foreground-muted" aria-hidden="true" />
              <h4 className="text-sm font-semibold text-foreground">
                {t("siriSm.title")}
              </h4>
            </div>
            <p className="text-xs text-foreground-muted">{t("siriSm.description")}</p>
          </div>

          <div className="space-y-(--spacing-tight)">
            <Label htmlFor="siri-sm-stop" className="text-xs font-medium text-foreground-muted">
              {t("siriSm.stopName")}
            </Label>
            <Input
              id="siri-sm-stop"
              value={siriSmStop}
              onChange={(e) => setSiriSmStop(e.target.value)}
              placeholder={t("siriSm.stopPlaceholder")}
              className="text-sm"
              required
            />
          </div>

          <div className="space-y-(--spacing-tight)">
            <Label htmlFor="siri-sm-feed" className="text-xs font-medium text-foreground-muted">
              {t("siriSm.feedFilter")}
            </Label>
            <Input
              id="siri-sm-feed"
              value={siriSmFeed}
              onChange={(e) => setSiriSmFeed(e.target.value)}
              placeholder={t("siriSm.feedPlaceholder")}
              className="text-sm"
            />
          </div>

          <Button
            className="w-full cursor-pointer"
            disabled={downloadingSiriSm}
            onClick={handleSiriSmDownload}
          >
            {downloadingSiriSm ? (
              t("siriSm.downloading")
            ) : (
              <>
                <Download className="mr-1 size-4" aria-hidden="true" />
                {t("siriSm.downloadButton")}
              </>
            )}
          </Button>
        </div>
      </div>

      <Separator />

      {/* Status section — loaded on demand */}
      {status || statusLoading ? (
        <StatusSection status={status} isLoading={statusLoading} t={t} />
      ) : (
        <Button
          variant="outline"
          className="cursor-pointer"
          onClick={loadStatus}
        >
          {t("status.title")}
        </Button>
      )}
    </div>
  );
}
