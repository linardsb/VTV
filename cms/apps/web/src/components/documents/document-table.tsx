"use client";

import { useState, useMemo } from "react";
import { useTranslations } from "next-intl";
import { MoreHorizontal, Download, Trash2, ArrowUpDown, FileText } from "lucide-react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Pagination,
  PaginationContent,
  PaginationEllipsis,
  PaginationItem,
  PaginationLink,
  PaginationNext,
  PaginationPrevious,
} from "@/components/ui/pagination";
import { getPageRange } from "@/lib/pagination-utils";
import { cn } from "@/lib/utils";
import type { DocumentItem } from "@/types/document";

type SortField = "name" | "source_type" | "file_size_bytes" | "created_at";
type SortDir = "asc" | "desc";

function formatFileSize(bytes: number | null): string {
  if (bytes === null || bytes === 0) return "-";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function getDocumentName(doc: DocumentItem): string {
  return doc.title ?? doc.filename;
}

function StatusBadge({ status }: { status: string }) {
  const t = useTranslations("documents.filters");
  const styles: Record<string, string> = {
    completed: "border-status-ontime/30 bg-status-ontime/10 text-status-ontime",
    processing: "border-status-delayed/30 bg-status-delayed/10 text-status-delayed",
    failed: "border-status-critical/30 bg-status-critical/10 text-status-critical",
    pending: "border-border bg-surface text-foreground-muted",
  };
  const labels: Record<string, string> = {
    completed: t("completed"),
    processing: t("processing"),
    failed: t("failed"),
    pending: t("pending"),
  };
  return (
    <Badge variant="outline" className={cn("text-xs", styles[status] ?? styles.pending)}>
      {labels[status] ?? status}
    </Badge>
  );
}

function TypeBadge({ sourceType }: { sourceType: string }) {
  return (
    <Badge variant="outline" className="text-xs uppercase">
      {sourceType}
    </Badge>
  );
}

function SortableHeader({
  field,
  children,
  onToggle,
}: {
  field: SortField;
  children: React.ReactNode;
  onToggle: (field: SortField) => void;
}) {
  return (
    <Button
      variant="ghost"
      size="sm"
      className="-ml-3 h-8 cursor-pointer"
      onClick={() => onToggle(field)}
    >
      {children}
      <ArrowUpDown className="ml-1 size-3" aria-hidden="true" />
    </Button>
  );
}

interface DocumentTableProps {
  documents: DocumentItem[];
  selectedDocumentId: number | null;
  onSelectDocument: (id: number) => void;
  onDeleteDocument: (doc: DocumentItem) => void;
  onDownloadDocument: (doc: DocumentItem) => void;
  isReadOnly: boolean;
  page: number;
  totalPages: number;
  totalItems: number;
  pageSize: number;
  onPageChange: (page: number) => void;
}

export function DocumentTable({
  documents,
  selectedDocumentId,
  onSelectDocument,
  onDeleteDocument,
  onDownloadDocument,
  isReadOnly,
  page,
  totalPages,
  totalItems,
  pageSize,
  onPageChange,
}: DocumentTableProps) {
  const t = useTranslations("documents");
  const [sortField, setSortField] = useState<SortField>("created_at");
  const [sortDir, setSortDir] = useState<SortDir>("desc");

  const sorted = useMemo(() => {
    const copy = [...documents];
    copy.sort((a, b) => {
      let cmp = 0;
      switch (sortField) {
        case "name":
          cmp = getDocumentName(a).localeCompare(getDocumentName(b), undefined, { numeric: true });
          break;
        case "source_type":
          cmp = a.source_type.localeCompare(b.source_type);
          break;
        case "file_size_bytes":
          cmp = (a.file_size_bytes ?? 0) - (b.file_size_bytes ?? 0);
          break;
        case "created_at":
          cmp = a.created_at.localeCompare(b.created_at);
          break;
      }
      return sortDir === "asc" ? cmp : -cmp;
    });
    return copy;
  }, [documents, sortField, sortDir]);

  function toggleSort(field: SortField) {
    if (sortField === field) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortField(field);
      setSortDir("asc");
    }
  }

  if (documents.length === 0) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-(--spacing-grid) py-20">
        <FileText className="size-12 text-foreground-muted" aria-hidden="true" />
        <p className="text-lg font-medium text-foreground">{t("table.noResults")}</p>
        <p className="text-sm text-foreground-muted">{t("table.noResultsDescription")}</p>
      </div>
    );
  }

  const from = (page - 1) * pageSize + 1;
  const to = Math.min(page * pageSize, totalItems);

  return (
    <div className="flex flex-1 flex-col">
      <div className="flex-1 overflow-auto">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>
                <SortableHeader onToggle={toggleSort} field="name">{t("table.name")}</SortableHeader>
              </TableHead>
              <TableHead className="hidden sm:table-cell w-24">
                <SortableHeader onToggle={toggleSort} field="source_type">{t("table.type")}</SortableHeader>
              </TableHead>
              <TableHead className="hidden md:table-cell w-24">
                <SortableHeader onToggle={toggleSort} field="file_size_bytes">{t("table.size")}</SortableHeader>
              </TableHead>
              <TableHead className="hidden lg:table-cell w-32">{t("table.domain")}</TableHead>
              <TableHead className="w-28">{t("table.status")}</TableHead>
              <TableHead className="hidden md:table-cell w-36">
                <SortableHeader onToggle={toggleSort} field="created_at">{t("table.uploaded")}</SortableHeader>
              </TableHead>
              <TableHead className="w-12">
                <span className="sr-only">{t("table.actions")}</span>
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {sorted.map((doc) => (
              <TableRow
                key={doc.id}
                className={cn(
                  "cursor-pointer transition-colors",
                  selectedDocumentId === doc.id && "bg-selected-bg"
                )}
                onClick={() => onSelectDocument(doc.id)}
              >
                <TableCell>
                  <div className="flex flex-col">
                    <span className="font-medium truncate max-w-[300px]">
                      {getDocumentName(doc)}
                    </span>
                    {doc.title && (
                      <span className="text-xs text-foreground-muted truncate max-w-[300px]">
                        {doc.filename}
                      </span>
                    )}
                  </div>
                </TableCell>
                <TableCell className="hidden sm:table-cell">
                  <TypeBadge sourceType={doc.source_type} />
                </TableCell>
                <TableCell className="hidden md:table-cell text-foreground-muted text-sm">
                  {formatFileSize(doc.file_size_bytes)}
                </TableCell>
                <TableCell className="hidden lg:table-cell">
                  <Badge variant="outline" className="text-xs">
                    {doc.domain}
                  </Badge>
                </TableCell>
                <TableCell>
                  <StatusBadge status={doc.status} />
                </TableCell>
                <TableCell className="hidden md:table-cell text-foreground-muted text-sm">
                  {new Date(doc.created_at).toLocaleDateString()}
                </TableCell>
                <TableCell>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="size-8 p-0"
                        aria-label={t("table.actions")}
                        onClick={(e) => e.stopPropagation()}
                      >
                        <MoreHorizontal className="size-4" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      {doc.has_file && (
                        <DropdownMenuItem onClick={() => onDownloadDocument(doc)}>
                          <Download className="mr-2 size-4" />
                          {t("actions.download")}
                        </DropdownMenuItem>
                      )}
                      {!isReadOnly && (
                        <DropdownMenuItem
                          className="text-status-critical"
                          onClick={() => onDeleteDocument(doc)}
                        >
                          <Trash2 className="mr-2 size-4" />
                          {t("actions.delete")}
                        </DropdownMenuItem>
                      )}
                    </DropdownMenuContent>
                  </DropdownMenu>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      {/* Pagination */}
      <div className="flex items-center justify-between border-t border-border px-(--spacing-card) py-(--spacing-tight)">
        <p className="hidden sm:block text-xs text-foreground-muted">
          {t("table.showing", { from, to, total: totalItems })}
        </p>
        {totalPages > 1 && (
          <Pagination className="mx-0 w-auto justify-end">
            <PaginationContent className="gap-0.5">
              <PaginationItem>
                <PaginationPrevious
                  onClick={() => onPageChange(Math.max(1, page - 1))}
                  aria-disabled={page === 1}
                  className={cn(
                    "h-8 w-8 p-0 [&>svg]:size-4 [&>span]:hidden",
                    page === 1 && "pointer-events-none opacity-50",
                  )}
                />
              </PaginationItem>
              {getPageRange(page, totalPages).map((item, idx) =>
                item === "ellipsis" ? (
                  <PaginationItem key={`ellipsis-${idx}`} className="hidden sm:inline-flex">
                    <PaginationEllipsis className="size-8" />
                  </PaginationItem>
                ) : (
                  <PaginationItem key={item} className="hidden sm:inline-flex">
                    <PaginationLink
                      isActive={item === page}
                      onClick={() => onPageChange(item)}
                      className="h-8 w-8 text-xs"
                    >
                      {item}
                    </PaginationLink>
                  </PaginationItem>
                ),
              )}
              <PaginationItem>
                <PaginationNext
                  onClick={() => onPageChange(Math.min(totalPages, page + 1))}
                  aria-disabled={page === totalPages}
                  className={cn(
                    "h-8 w-8 p-0 [&>svg]:size-4 [&>span]:hidden",
                    page === totalPages && "pointer-events-none opacity-50",
                  )}
                />
              </PaginationItem>
            </PaginationContent>
          </Pagination>
        )}
      </div>
    </div>
  );
}
