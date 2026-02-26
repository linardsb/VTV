"use client";

import { useState, useCallback } from "react";
import { useDropzone } from "react-dropzone";
import { useTranslations } from "next-intl";
import { Upload, FileIcon, X } from "lucide-react";
import { toast } from "sonner";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";
import { uploadDocument } from "@/lib/documents-sdk";
import type { DocumentItem } from "@/types/document";

const DEFAULT_DOMAINS = ["general", "operations", "safety", "training"];

const ACCEPTED_TYPES: Record<string, string[]> = {
  "application/pdf": [".pdf"],
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [".docx"],
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [".xlsx"],
  "text/csv": [".csv"],
  "text/plain": [".txt", ".md"],
  "image/png": [".png"],
  "image/jpeg": [".jpg", ".jpeg"],
  "message/rfc822": [".eml"],
};

const MAX_FILE_SIZE = 50 * 1024 * 1024; // 50MB

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

interface DocumentUploadFormProps {
  isOpen: boolean;
  onClose: () => void;
  onUploadComplete: (doc: DocumentItem) => void;
  domains: string[];
}

export function DocumentUploadForm({
  isOpen,
  onClose,
  onUploadComplete,
  domains,
}: DocumentUploadFormProps) {
  const t = useTranslations("documents");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [domain, setDomain] = useState("");
  const [language, setLanguage] = useState("lv");
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);

  const onDrop = useCallback((acceptedFiles: File[]) => {
    if (acceptedFiles.length > 0) {
      setSelectedFile(acceptedFiles[0]);
    }
  }, []);

  const { getRootProps, getInputProps, isDragActive, isDragReject } = useDropzone({
    onDrop,
    accept: ACCEPTED_TYPES,
    maxSize: MAX_FILE_SIZE,
    multiple: false,
  });

  const handleSubmit = useCallback(async () => {
    if (!selectedFile || !domain) return;

    setIsUploading(true);
    setUploadProgress(20);

    try {
      setUploadProgress(50);
      const doc = await uploadDocument({
        file: selectedFile,
        domain,
        language,
        title: title || undefined,
        description: description || undefined,
      });
      setUploadProgress(100);
      toast.success(t("toast.uploaded"));
      onUploadComplete(doc);
      // Reset form
      setSelectedFile(null);
      setTitle("");
      setDescription("");
      setDomain("");
      setLanguage("lv");
      setUploadProgress(0);
    } catch {
      toast.error(t("toast.uploadError"));
    } finally {
      setIsUploading(false);
    }
  }, [selectedFile, domain, language, title, description, t, onUploadComplete]);

  const handleRemoveFile = useCallback(() => {
    setSelectedFile(null);
  }, []);

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-h-[90vh] overflow-y-auto" showCloseButton>
        <DialogHeader>
          <DialogTitle className="font-heading text-heading font-semibold">
            {t("upload.title")}
          </DialogTitle>
          <DialogDescription className="sr-only">
            {t("upload.title")}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-(--spacing-grid)">
          {/* Dropzone */}
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
                {isDragActive
                  ? isDragReject
                    ? t("upload.dropzoneReject")
                    : t("upload.dropzoneActive")
                  : t("upload.dropzone")}
              </p>
              <p className="mt-1 text-xs text-foreground-muted">
                {t("upload.dropzoneHint")}
              </p>
            </div>
          ) : (
            <div className="flex items-center gap-(--spacing-inline) rounded-lg border border-border p-(--spacing-card)">
              <FileIcon className="size-8 shrink-0 text-foreground-muted" aria-hidden="true" />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium truncate">{selectedFile.name}</p>
                <p className="text-xs text-foreground-muted">{formatFileSize(selectedFile.size)}</p>
              </div>
              <Button
                variant="ghost"
                size="sm"
                className="size-8 p-0 shrink-0 cursor-pointer"
                onClick={handleRemoveFile}
                aria-label={t("actions.close")}
              >
                <X className="size-4" />
              </Button>
            </div>
          )}

          {/* Title */}
          <div className="space-y-(--spacing-tight)">
            <Label htmlFor="doc-title">{t("upload.titleLabel")}</Label>
            <Input
              id="doc-title"
              placeholder={t("upload.titlePlaceholder")}
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              disabled={isUploading}
            />
          </div>

          {/* Description */}
          <div className="space-y-(--spacing-tight)">
            <Label htmlFor="doc-description">{t("upload.descriptionLabel")}</Label>
            <Textarea
              id="doc-description"
              placeholder={t("upload.descriptionPlaceholder")}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              disabled={isUploading}
              rows={3}
            />
          </div>

          {/* Domain */}
          <div className="space-y-(--spacing-tight)">
            <Label htmlFor="doc-domain">{t("upload.domainLabel")}</Label>
            <Select value={domain} onValueChange={setDomain} disabled={isUploading}>
              <SelectTrigger id="doc-domain" aria-label={t("upload.domainLabel")}>
                <SelectValue placeholder={t("upload.domainPlaceholder")} />
              </SelectTrigger>
              <SelectContent>
                {[...new Set([...DEFAULT_DOMAINS, ...domains])].map((d) => (
                  <SelectItem key={d} value={d}>{t(`domains.${d}` as Parameters<typeof t>[0])}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Language */}
          <div className="space-y-(--spacing-tight)">
            <Label htmlFor="doc-language">{t("upload.languageLabel")}</Label>
            <Select value={language} onValueChange={setLanguage} disabled={isUploading}>
              <SelectTrigger id="doc-language" aria-label={t("upload.languageLabel")}>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="lv">{t("filters.lv")}</SelectItem>
                <SelectItem value="en">{t("filters.en")}</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* Upload progress */}
          {isUploading && (
            <div className="space-y-(--spacing-tight)">
              <Progress value={uploadProgress} className="w-full" />
              <p className="text-xs text-foreground-muted text-center">
                {uploadProgress < 100 ? t("upload.uploading") : t("upload.processing")}
              </p>
            </div>
          )}

          {/* Submit button */}
          <Button
            className="w-full cursor-pointer"
            disabled={!selectedFile || !domain || isUploading}
            onClick={handleSubmit}
          >
            {isUploading ? t("upload.uploading") : t("upload.submit")}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
