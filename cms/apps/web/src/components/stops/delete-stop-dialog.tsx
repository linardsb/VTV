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
import type { Stop } from "@/types/stop";

interface DeleteStopDialogProps {
  stop: Stop | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onConfirm: () => void;
}

export function DeleteStopDialog({
  stop,
  open,
  onOpenChange,
  onConfirm,
}: DeleteStopDialogProps) {
  const t = useTranslations("stops.delete");

  if (!stop) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <div className="flex items-center gap-(--spacing-inline)">
            <div className="flex size-10 items-center justify-center rounded-full bg-status-critical/10">
              <AlertTriangle
                className="size-5 text-status-critical"
                aria-hidden="true"
              />
            </div>
            <DialogTitle>{t("title")}</DialogTitle>
          </div>
          <DialogDescription className="pt-(--spacing-inline)">
            {t("confirmation", { name: stop.stop_name })}
          </DialogDescription>
        </DialogHeader>
        <p className="text-sm text-foreground-muted">{t("warning")}</p>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            {t("cancel")}
          </Button>
          <Button
            variant="destructive"
            onClick={() => {
              onConfirm();
              onOpenChange(false);
            }}
          >
            {t("confirm")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
