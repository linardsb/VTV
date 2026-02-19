"use client";

import { useState, useEffect, useMemo, useCallback } from "react";
import { useTranslations } from "next-intl";
import { Plus, Filter } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { useIsMobile } from "@/hooks/use-mobile";
import { DocumentTable } from "@/components/documents/document-table";
import { DocumentFilters } from "@/components/documents/document-filters";
import { DocumentUploadForm } from "@/components/documents/document-upload-form";
import { DocumentDetail } from "@/components/documents/document-detail";
import { DeleteDocumentDialog } from "@/components/documents/delete-document-dialog";
import {
  fetchDocuments,
  deleteDocument,
  downloadDocument,
  fetchDomains,
} from "@/lib/documents-client";
import type { DocumentItem } from "@/types/document";

// Simulated role — in production, read from session
const USER_ROLE: string = "admin";
const IS_READ_ONLY = USER_ROLE === "viewer" || USER_ROLE === "dispatcher";

const PAGE_SIZE = 10;

export default function DocumentsPage() {
  const t = useTranslations("documents");
  const isMobile = useIsMobile();

  // Data state
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [totalItems, setTotalItems] = useState(0);
  const [page, setPage] = useState(1);
  const [domains, setDomains] = useState<string[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  // Filter state
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [domainFilter, setDomainFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [languageFilter, setLanguageFilter] = useState("");
  const [filterSheetOpen, setFilterSheetOpen] = useState(false);

  // UI state
  const [selectedDocumentId, setSelectedDocumentId] = useState<number | null>(null);
  const [detailOpen, setDetailOpen] = useState(false);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<DocumentItem | null>(null);

  // Derived
  const totalPages = Math.max(1, Math.ceil(totalItems / PAGE_SIZE));

  const selectedDocument = useMemo(
    () => documents.find((d) => d.id === selectedDocumentId) ?? null,
    [documents, selectedDocumentId],
  );

  // Client-side search filter (server handles domain/status/language)
  const filteredDocuments = useMemo(() => {
    if (!search) return documents;
    const q = search.toLowerCase();
    return documents.filter((doc) => {
      const name = doc.title ?? doc.filename;
      return (
        name.toLowerCase().includes(q) ||
        doc.filename.toLowerCase().includes(q)
      );
    });
  }, [documents, search]);

  // Client-side type filter (match source_type)
  const displayDocuments = useMemo(() => {
    if (!typeFilter) return filteredDocuments;
    return filteredDocuments.filter((doc) => doc.source_type === typeFilter);
  }, [filteredDocuments, typeFilter]);

  // Fetch documents
  const loadDocuments = useCallback(async () => {
    setIsLoading(true);
    try {
      const result = await fetchDocuments({
        page,
        page_size: PAGE_SIZE,
        domain: domainFilter || undefined,
        status: statusFilter || undefined,
        language: languageFilter || undefined,
      });
      setDocuments(result.items);
      setTotalItems(result.total);
    } catch {
      // Silently handle — empty state will show
      setDocuments([]);
      setTotalItems(0);
    } finally {
      setIsLoading(false);
    }
  }, [page, domainFilter, statusFilter, languageFilter]);

  // Fetch domains on mount
  const loadDomains = useCallback(async () => {
    try {
      const result = await fetchDomains();
      setDomains(result.domains);
    } catch {
      // Silently handle
    }
  }, []);

  useEffect(() => {
    void loadDocuments();
  }, [loadDocuments]);

  useEffect(() => {
    void loadDomains();
  }, [loadDomains]);

  // Handlers
  const handleSelectDocument = useCallback((id: number) => {
    setSelectedDocumentId(id);
    setDetailOpen(true);
  }, []);

  const handleUploadComplete = useCallback(() => {
    setUploadOpen(false);
    void loadDocuments();
    void loadDomains();
  }, [loadDocuments, loadDomains]);

  const handleDeleteRequest = useCallback((doc: DocumentItem) => {
    setDeleteTarget(doc);
    setDeleteOpen(true);
  }, []);

  const handleDeleteConfirm = useCallback(
    async (documentId: number) => {
      try {
        await deleteDocument(documentId);
        toast.success(t("toast.deleted"));
        if (selectedDocumentId === documentId) {
          setSelectedDocumentId(null);
          setDetailOpen(false);
        }
        void loadDocuments();
      } catch {
        toast.error(t("toast.deleteError"));
      }
    },
    [selectedDocumentId, t, loadDocuments],
  );

  const handleDownload = useCallback(
    async (doc: DocumentItem) => {
      try {
        const blob = await downloadDocument(doc.id);
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = doc.filename;
        a.click();
        URL.revokeObjectURL(url);
      } catch {
        toast.error(t("toast.downloadError"));
      }
    },
    [t],
  );

  const handlePageChange = useCallback((newPage: number) => {
    setPage(newPage);
  }, []);

  return (
    <div className="flex h-[calc(100vh-var(--spacing-page)*2)] flex-col gap-(--spacing-grid)">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-heading text-heading font-semibold text-foreground">
            {t("title")}
          </h1>
          <p className="hidden sm:block text-sm text-foreground-muted">{t("description")}</p>
        </div>
        <div className="flex items-center gap-(--spacing-inline)">
          {isMobile && (
            <Button
              variant="outline"
              size="sm"
              className="cursor-pointer"
              onClick={() => setFilterSheetOpen(true)}
              aria-label={t("mobile.showFilters")}
            >
              <Filter className="mr-1 size-4" aria-hidden="true" />
              {t("mobile.showFilters")}
            </Button>
          )}
          {!IS_READ_ONLY && (
            <Button className="cursor-pointer" onClick={() => setUploadOpen(true)}>
              <Plus className="mr-2 size-4" aria-hidden="true" />
              {t("actions.upload")}
            </Button>
          )}
        </div>
      </div>

      {/* Content */}
      {isMobile ? (
        <>
          <DocumentFilters
            search={search}
            onSearchChange={setSearch}
            typeFilter={typeFilter}
            onTypeFilterChange={setTypeFilter}
            domainFilter={domainFilter}
            onDomainFilterChange={setDomainFilter}
            statusFilter={statusFilter}
            onStatusFilterChange={setStatusFilter}
            languageFilter={languageFilter}
            onLanguageFilterChange={setLanguageFilter}
            domains={domains}
            resultCount={displayDocuments.length}
            asSheet
            sheetOpen={filterSheetOpen}
            onSheetOpenChange={setFilterSheetOpen}
          />
          <div className="flex-1 overflow-hidden rounded-lg border border-border">
            {isLoading ? (
              <div className="flex h-full items-center justify-center">
                <p className="text-sm text-foreground-muted">{t("description")}</p>
              </div>
            ) : (
              <DocumentTable
                documents={displayDocuments}
                selectedDocumentId={selectedDocumentId}
                onSelectDocument={handleSelectDocument}
                onDeleteDocument={handleDeleteRequest}
                onDownloadDocument={handleDownload}
                isReadOnly={IS_READ_ONLY}
                page={page}
                totalPages={totalPages}
                totalItems={totalItems}
                pageSize={PAGE_SIZE}
                onPageChange={handlePageChange}
              />
            )}
          </div>
        </>
      ) : (
        <div className="flex min-h-0 flex-1 overflow-hidden rounded-lg border border-border">
          <DocumentFilters
            search={search}
            onSearchChange={setSearch}
            typeFilter={typeFilter}
            onTypeFilterChange={setTypeFilter}
            domainFilter={domainFilter}
            onDomainFilterChange={setDomainFilter}
            statusFilter={statusFilter}
            onStatusFilterChange={setStatusFilter}
            languageFilter={languageFilter}
            onLanguageFilterChange={setLanguageFilter}
            domains={domains}
            resultCount={displayDocuments.length}
          />
          {isLoading ? (
            <div className="flex flex-1 items-center justify-center">
              <p className="text-sm text-foreground-muted">{t("description")}</p>
            </div>
          ) : (
            <DocumentTable
              documents={displayDocuments}
              selectedDocumentId={selectedDocumentId}
              onSelectDocument={handleSelectDocument}
              onDeleteDocument={handleDeleteRequest}
              onDownloadDocument={handleDownload}
              isReadOnly={IS_READ_ONLY}
              page={page}
              totalPages={totalPages}
              totalItems={totalItems}
              pageSize={PAGE_SIZE}
              onPageChange={handlePageChange}
            />
          )}
        </div>
      )}

      {/* Detail Sheet */}
      <DocumentDetail
        document={selectedDocument}
        isOpen={detailOpen}
        onClose={() => { setDetailOpen(false); setSelectedDocumentId(null); }}
        onDelete={handleDeleteRequest}
        onDownload={handleDownload}
        isReadOnly={IS_READ_ONLY}
      />

      {/* Upload Form */}
      <DocumentUploadForm
        isOpen={uploadOpen}
        onClose={() => setUploadOpen(false)}
        onUploadComplete={handleUploadComplete}
        domains={domains}
      />

      {/* Delete Dialog */}
      <DeleteDocumentDialog
        document={deleteTarget}
        isOpen={deleteOpen}
        onClose={() => setDeleteOpen(false)}
        onConfirm={handleDeleteConfirm}
      />
    </div>
  );
}
