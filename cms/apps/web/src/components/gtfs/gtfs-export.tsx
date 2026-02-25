"use client";

import { useState, useCallback } from "react";
import { useTranslations } from "next-intl";
import { Download, FileArchive } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { exportGTFS } from "@/lib/gtfs-client";

interface GTFSExportProps {
  agencies: Array<{ id: number; agency_name: string }>;
}

export function GTFSExport({ agencies }: GTFSExportProps) {
  const t = useTranslations("gtfs.export");
  const [selectedAgency, setSelectedAgency] = useState<string>("all");
  const [isDownloading, setIsDownloading] = useState(false);

  const handleDownload = useCallback(async () => {
    setIsDownloading(true);
    try {
      const agencyId =
        selectedAgency === "all" ? undefined : Number(selectedAgency);
      await exportGTFS(agencyId);
      toast.success(t("downloadSuccess"));
    } catch {
      toast.error(t("downloadError"));
    } finally {
      setIsDownloading(false);
    }
  }, [selectedAgency, t]);

  return (
    <div className="space-y-(--spacing-grid) p-(--spacing-card)">
      {/* Header */}
      <div className="space-y-(--spacing-tight)">
        <h3 className="text-sm font-semibold text-foreground">{t("title")}</h3>
        <p className="text-xs text-foreground-muted">{t("description")}</p>
      </div>

      {/* Agency filter */}
      <div className="space-y-(--spacing-tight)">
        <label
          htmlFor="agency-filter"
          className="text-xs font-medium text-foreground-muted"
        >
          {t("agencyFilter")}
        </label>
        <Select value={selectedAgency} onValueChange={setSelectedAgency}>
          <SelectTrigger id="agency-filter" className="cursor-pointer">
            <SelectValue placeholder={t("allAgencies")} />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all" className="cursor-pointer">
              {t("allAgencies")}
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

      {/* Download button */}
      <Button
        className="w-full cursor-pointer"
        disabled={isDownloading}
        onClick={handleDownload}
      >
        {isDownloading ? (
          t("downloading")
        ) : (
          <>
            <Download className="mr-1 size-4" aria-hidden="true" />
            {t("downloadButton")}
          </>
        )}
      </Button>

      <Separator />

      {/* Included files note */}
      <div className="flex items-start gap-(--spacing-inline)">
        <FileArchive
          className="size-4 shrink-0 mt-0.5 text-foreground-muted"
          aria-hidden="true"
        />
        <p className="text-xs text-foreground-muted">{t("includesNote")}</p>
      </div>
    </div>
  );
}
