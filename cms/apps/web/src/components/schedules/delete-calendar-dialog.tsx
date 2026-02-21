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
import type { Calendar } from "@/types/schedule";

interface DeleteCalendarDialogProps {
  calendar: Calendar | null;
  isOpen: boolean;
  onClose: () => void;
  onConfirm: (calendarId: number) => void;
}

export function DeleteCalendarDialog({
  calendar,
  isOpen,
  onClose,
  onConfirm,
}: DeleteCalendarDialogProps) {
  const t = useTranslations("schedules.calendars");

  if (!calendar) return null;

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent>
        <DialogHeader>
          <div className="flex items-center gap-(--spacing-inline)">
            <div className="flex size-10 items-center justify-center rounded-full bg-status-critical/10">
              <AlertTriangle className="size-5 text-status-critical" aria-hidden="true" />
            </div>
            <DialogTitle>{t("deleteTitle")}</DialogTitle>
          </div>
          <DialogDescription className="pt-(--spacing-inline)">
            {t("deleteConfirmation", { name: calendar.gtfs_service_id })}
          </DialogDescription>
        </DialogHeader>
        <p className="text-sm text-foreground-muted">{t("deleteWarning")}</p>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>{t("cancel")}</Button>
          <Button
            variant="destructive"
            onClick={() => { onConfirm(calendar.id); onClose(); }}
          >
            {t("delete")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
