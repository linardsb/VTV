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
import type { Route } from "@/types/route";

interface DeleteRouteDialogProps {
  route: Route | null;
  isOpen: boolean;
  onClose: () => void;
  onConfirm: (routeId: number) => void;
}

export function DeleteRouteDialog({
  route,
  isOpen,
  onClose,
  onConfirm,
}: DeleteRouteDialogProps) {
  const t = useTranslations("routes.delete");

  if (!route) return null;

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
            {t("confirmation", { name: `${route.route_short_name} ${route.route_long_name}` })}
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
              onConfirm(route.id);
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
