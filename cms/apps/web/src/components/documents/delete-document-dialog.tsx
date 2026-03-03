"use client";

import { AlertTriangle } from "lucide-react";
import { useTranslations } from "next-intl";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import type { DocumentItem } from "@/types/document";

interface DeleteDocumentDialogProps {
  document: DocumentItem | null;
  isOpen: boolean;
  onClose: () => void;
  onConfirm: (documentId: number) => void;
}

export function DeleteDocumentDialog({
  document: doc,
  isOpen,
  onClose,
  onConfirm,
}: DeleteDocumentDialogProps) {
  const t = useTranslations("documents.delete");

  if (!doc) return null;

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent>
        <DialogHeader>
          <div className="flex items-center gap-(--spacing-inline)">
            <div className="flex size-10 items-center justify-center rounded-none bg-status-critical/10">
              <AlertTriangle
                className="size-5 text-status-critical"
                aria-hidden="true"
              />
            </div>
            <DialogTitle>{t("title")}</DialogTitle>
          </div>
          <DialogDescription className="pt-(--spacing-inline)">
            {t("confirmation", { name: doc.title ?? doc.filename })}
          </DialogDescription>
        </DialogHeader>
        <p className="text-sm text-foreground-muted">{t("warning")}</p>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            {t("cancel")}
          </Button>
          <Button
            variant="destructive"
            onClick={() => {
              onConfirm(doc.id);
              onClose();
            }}
          >
            {t("confirm")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
