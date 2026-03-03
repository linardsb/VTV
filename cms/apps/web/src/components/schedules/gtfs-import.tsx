"use client";

import { useState, useCallback } from "react";
import { useDropzone } from "react-dropzone";
import { useTranslations } from "next-intl";
import { Upload, FileArchive, X, CheckCircle, AlertTriangle, XCircle } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";
import { importGTFS, validateSchedule } from "@/lib/schedules-sdk";
import type { GTFSImportResponse, ValidationResult } from "@/types/schedule";

interface GTFSImportProps {
  onImportComplete: () => void;
}

export function GTFSImport({ onImportComplete }: GTFSImportProps) {
  const t = useTranslations("schedules.import");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [importResult, setImportResult] = useState<GTFSImportResponse | null>(null);
  const [validationResult, setValidationResult] = useState<ValidationResult | null>(null);
  const [isValidating, setIsValidating] = useState(false);

  const onDrop = useCallback((acceptedFiles: File[]) => {
    if (acceptedFiles.length > 0) {
      setSelectedFile(acceptedFiles[0]);
      setImportResult(null);
    }
  }, []);

  const { getRootProps, getInputProps, isDragActive, isDragReject } = useDropzone({
    onDrop,
    accept: { "application/zip": [".zip"] },
    maxSize: 100 * 1024 * 1024,
    multiple: false,
  });

  const handleImport = useCallback(async () => {
    if (!selectedFile) return;
    setIsUploading(true);
    try {
      const result = await importGTFS(selectedFile);
      setImportResult(result);
      toast.success(t("importSuccess"));
      onImportComplete();
    } catch {
      toast.error(t("importError"));
    } finally {
      setIsUploading(false);
    }
  }, [selectedFile, t, onImportComplete]);

  const handleValidate = useCallback(async () => {
    setIsValidating(true);
    try {
      const result = await validateSchedule();
      setValidationResult(result);
    } catch {
      toast.error(t("validateError"));
    } finally {
      setIsValidating(false);
    }
  }, [t]);

  return (
    <div className="space-y-(--spacing-grid) p-(--spacing-card)">
      {/* Upload */}
      <div className="space-y-(--spacing-card)">
        <h3 className="text-sm font-semibold text-foreground">{t("uploadTitle")}</h3>

        {!selectedFile ? (
          <div
            {...getRootProps()}
            className={cn(
              "flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed p-(--spacing-xl) transition-colors",
              isDragActive && !isDragReject && "border-cta bg-cta/5",
              isDragReject && "border-status-critical bg-status-critical/5",
              !isDragActive && !isDragReject && "border-border hover:border-foreground-muted"
            )}
          >
            <input {...getInputProps()} />
            <Upload className="size-8 text-foreground-muted mb-(--spacing-sm)" aria-hidden="true" />
            <p className="text-sm font-medium text-foreground">
              {isDragActive ? t("dropzoneActive") : t("dropzone")}
            </p>
            <p className="mt-1 text-xs text-foreground-muted">{t("dropzoneHint")}</p>
          </div>
        ) : (
          <div className="flex items-center gap-(--spacing-inline) rounded-lg border border-border p-(--spacing-card)">
            <FileArchive className="size-8 shrink-0 text-foreground-muted" aria-hidden="true" />
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium truncate">{selectedFile.name}</p>
              <p className="text-xs text-foreground-muted">
                {(selectedFile.size / (1024 * 1024)).toFixed(1)} MB
              </p>
            </div>
            <Button
              variant="ghost"
              size="sm"
              className="size-8 p-0 shrink-0 cursor-pointer"
              onClick={() => { setSelectedFile(null); setImportResult(null); }}
            >
              <X className="size-4" />
            </Button>
          </div>
        )}

        {isUploading && (
          <div className="space-y-(--spacing-tight)">
            <div className="relative h-2 w-full overflow-hidden rounded-none bg-muted">
              <div className="absolute inset-0 h-full w-1/3 animate-pulse rounded-none bg-interactive" />
            </div>
            <p className="text-xs text-foreground-muted text-center">{t("importing")}</p>
          </div>
        )}

        <Button
          className="w-full cursor-pointer"
          disabled={!selectedFile || isUploading}
          onClick={handleImport}
        >
          {isUploading ? t("importing") : t("importButton")}
        </Button>
      </div>

      {/* Import result */}
      {importResult && (
        <>
          <Separator />
          <div className="space-y-(--spacing-inline)">
            <h3 className="text-sm font-semibold text-foreground">{t("importResults")}</h3>
            <div className="grid grid-cols-2 gap-(--spacing-inline)">
              <ResultBadge label={t("agencies")} count={importResult.agencies_count} created={importResult.agencies_created} updated={importResult.agencies_updated} />
              <ResultBadge label={t("routes")} count={importResult.routes_count} created={importResult.routes_created} updated={importResult.routes_updated} />
              <ResultBadge label={t("calendars")} count={importResult.calendars_count} created={importResult.calendars_created} updated={importResult.calendars_updated} />
              <ResultBadge label={t("calendarDates")} count={importResult.calendar_dates_count} />
              <ResultBadge label={t("trips")} count={importResult.trips_count} created={importResult.trips_created} updated={importResult.trips_updated} />
              <ResultBadge label={t("stopTimes")} count={importResult.stop_times_count} />
            </div>
            {importResult.skipped_stop_times > 0 && (
              <p className="text-xs text-foreground-muted">
                {t("skippedStopTimes", { count: importResult.skipped_stop_times })}
              </p>
            )}
            {importResult.warnings.length > 0 && (
              <div className="space-y-1">
                {importResult.warnings.map((w, i) => (
                  <div key={i} className="flex items-start gap-1 text-xs">
                    <AlertTriangle className="size-3 shrink-0 mt-0.5 text-status-delayed" />
                    <span className="text-foreground-muted">{w}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </>
      )}

      <Separator />

      {/* Validate */}
      <div className="space-y-(--spacing-card)">
        <h3 className="text-sm font-semibold text-foreground">{t("validateTitle")}</h3>
        <p className="text-xs text-foreground-muted">{t("validateDescription")}</p>
        <Button
          variant="outline"
          className="w-full cursor-pointer"
          onClick={handleValidate}
          disabled={isValidating}
        >
          {isValidating ? t("validating") : t("validateButton")}
        </Button>
      </div>

      {/* Validation result */}
      {validationResult && (
        <div className="space-y-(--spacing-inline)">
          <div className="flex items-center gap-(--spacing-inline)">
            {validationResult.valid ? (
              <CheckCircle className="size-5 text-status-ontime" />
            ) : (
              <XCircle className="size-5 text-status-critical" />
            )}
            <span className="text-sm font-medium">
              {validationResult.valid ? t("valid") : t("invalid")}
            </span>
          </div>
          {validationResult.errors.length > 0 && (
            <div className="space-y-1">
              {validationResult.errors.map((e, i) => (
                <div key={i} className="flex items-start gap-1 text-xs">
                  <XCircle className="size-3 shrink-0 mt-0.5 text-status-critical" />
                  <span className="text-foreground-muted">{e}</span>
                </div>
              ))}
            </div>
          )}
          {validationResult.warnings.length > 0 && (
            <div className="space-y-1">
              {validationResult.warnings.map((w, i) => (
                <div key={i} className="flex items-start gap-1 text-xs">
                  <AlertTriangle className="size-3 shrink-0 mt-0.5 text-status-delayed" />
                  <span className="text-foreground-muted">{w}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function ResultBadge({ label, count, created, updated }: { label: string; count: number; created?: number; updated?: number }) {
  const hasBreakdown = created !== undefined && updated !== undefined && count > 0;
  return (
    <div className="flex items-center justify-between rounded-md border border-border px-3 py-2">
      <span className="text-xs text-foreground-muted">{label}</span>
      <div className="flex items-center gap-1">
        <Badge variant="outline" className="font-mono">{count}</Badge>
        {hasBreakdown && (
          <span className="text-[10px] text-foreground-subtle">
            +{created} / ~{updated}
          </span>
        )}
      </div>
    </div>
  );
}
