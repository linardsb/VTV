"use client";

import { useState, useCallback } from "react";
import { useTranslations, useLocale } from "next-intl";
import { Download, Trash2, ChevronDown, ChevronRight } from "lucide-react";
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
import { ScrollArea } from "@/components/ui/scroll-area";
import { cn } from "@/lib/utils";
import { fetchDocumentContent } from "@/lib/documents-client";
import type { DocumentItem, DocumentChunk } from "@/types/document";

function DetailRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-(--spacing-tight)">
      <span className="text-xs font-medium text-label-text uppercase tracking-wide">
        {label}
      </span>
      <div className="text-sm text-foreground">{children}</div>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    completed: "border-status-ontime/30 bg-status-ontime/10 text-status-ontime",
    processing: "border-status-delayed/30 bg-status-delayed/10 text-status-delayed",
    failed: "border-status-critical/30 bg-status-critical/10 text-status-critical",
    pending: "border-border bg-surface text-foreground-muted",
  };
  return (
    <Badge variant="outline" className={cn("text-xs", styles[status] ?? styles.pending)}>
      {status}
    </Badge>
  );
}

function formatFileSize(bytes: number | null): string {
  if (bytes === null || bytes === 0) return "-";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

interface DocumentDetailProps {
  document: DocumentItem | null;
  isOpen: boolean;
  onClose: () => void;
  onDelete: (doc: DocumentItem) => void;
  onDownload: (doc: DocumentItem) => void;
  isReadOnly: boolean;
}

export function DocumentDetail({
  document: doc,
  isOpen,
  onClose,
  onDelete,
  onDownload,
  isReadOnly,
}: DocumentDetailProps) {
  const t = useTranslations("documents.detail");
  const tActions = useTranslations("documents.actions");
  const locale = useLocale();
  const [chunks, setChunks] = useState<DocumentChunk[]>([]);
  const [totalChunks, setTotalChunks] = useState(0);
  const [showAllChunks, setShowAllChunks] = useState(false);
  const [contentExpanded, setContentExpanded] = useState(false);
  const [loadedDocId, setLoadedDocId] = useState<number | null>(null);

  // Lazy-load chunks when user expands content preview (event handler, not effect)
  const handleToggleContent = useCallback(async () => {
    if (!doc) return;
    const willExpand = !contentExpanded;
    setContentExpanded(willExpand);
    if (willExpand && loadedDocId !== doc.id) {
      try {
        const content = await fetchDocumentContent(doc.id);
        setChunks(content.chunks);
        setTotalChunks(content.total_chunks);
        setLoadedDocId(doc.id);
        setShowAllChunks(false);
      } catch {
        setChunks([]);
        setTotalChunks(0);
      }
    }
  }, [doc, contentExpanded, loadedDocId]);

  if (!doc) return null;

  const dateFormatter = new Intl.DateTimeFormat(locale, {
    year: "numeric",
    month: "long",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });

  const displayedChunks = showAllChunks ? chunks : chunks.slice(0, 3);

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-[36rem] max-h-[90vh] overflow-y-auto" showCloseButton>
        <DialogHeader>
          <DialogTitle className="font-heading text-heading font-semibold">
            {doc.title ?? doc.filename}
          </DialogTitle>
          <DialogDescription className="sr-only">
            {doc.title ?? doc.filename}
          </DialogDescription>
          <StatusBadge status={doc.status} />
        </DialogHeader>

        <div className="space-y-(--spacing-card)">
          {/* Metadata */}
          <div className="space-y-(--spacing-card)">
            <DetailRow label={t("fileName")}>{doc.filename}</DetailRow>
            <DetailRow label={t("fileType")}>
              <Badge variant="outline" className="text-xs uppercase">{doc.source_type}</Badge>
            </DetailRow>
            <DetailRow label={t("fileSize")}>{formatFileSize(doc.file_size_bytes)}</DetailRow>
            <DetailRow label={t("language")}>
              <Badge variant="outline" className="text-xs">{doc.language.toUpperCase()}</Badge>
            </DetailRow>
            <DetailRow label={t("domain")}>
              <Badge variant="outline" className="text-xs">{doc.domain}</Badge>
            </DetailRow>
            <DetailRow label={t("chunkCount")}>{doc.chunk_count}</DetailRow>
            <DetailRow label={t("uploaded")}>
              {dateFormatter.format(new Date(doc.created_at))}
            </DetailRow>
            <DetailRow label={t("updated")}>
              {dateFormatter.format(new Date(doc.updated_at))}
            </DetailRow>
            {doc.description && (
              <DetailRow label={t("description")}>{doc.description}</DetailRow>
            )}
            {!doc.description && (
              <DetailRow label={t("description")}>
                <span className="text-foreground-muted italic">{t("noDescription")}</span>
              </DetailRow>
            )}
          </div>

          {/* Actions */}
          <Separator />
          <div className="flex gap-(--spacing-inline)">
            {doc.has_file && (
              <Button
                variant="outline"
                className="flex-1 cursor-pointer"
                onClick={() => onDownload(doc)}
              >
                <Download className="mr-2 size-4" />
                {tActions("download")}
              </Button>
            )}
            {!isReadOnly && (
              <Button
                variant="destructive"
                className="cursor-pointer"
                onClick={() => onDelete(doc)}
              >
                <Trash2 className="mr-2 size-4" />
                {tActions("delete")}
              </Button>
            )}
          </div>

          {/* Content Preview */}
          {doc.chunk_count > 0 && (
            <>
              <Separator />
              <div>
                <Button
                  variant="ghost"
                  className="w-full justify-start px-0 cursor-pointer"
                  onClick={handleToggleContent}
                >
                  {contentExpanded ? (
                    <ChevronDown className="mr-2 size-4" />
                  ) : (
                    <ChevronRight className="mr-2 size-4" />
                  )}
                  <span className="text-xs font-medium text-label-text uppercase tracking-wide">
                    {t("contentPreview")}
                  </span>
                </Button>

                {contentExpanded && (
                  <ScrollArea className="mt-(--spacing-tight) max-h-[400px]">
                    <div className="space-y-(--spacing-tight)">
                      {displayedChunks.map((chunk) => (
                        <div
                          key={chunk.chunk_index}
                          className="rounded-lg bg-surface p-(--spacing-card)"
                        >
                          <p className="text-xs font-medium text-foreground-muted mb-1">
                            {t("chunk", { index: chunk.chunk_index + 1 })}
                          </p>
                          <p className="text-sm text-foreground whitespace-pre-wrap line-clamp-6">
                            {chunk.content}
                          </p>
                        </div>
                      ))}
                      {!showAllChunks && totalChunks > 3 && (
                        <Button
                          variant="ghost"
                          size="sm"
                          className="w-full cursor-pointer text-xs"
                          onClick={() => setShowAllChunks(true)}
                        >
                          {t("showAllChunks", { count: totalChunks })}
                        </Button>
                      )}
                    </div>
                  </ScrollArea>
                )}
              </div>
            </>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
