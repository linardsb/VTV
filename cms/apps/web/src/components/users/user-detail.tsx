"use client";

import { useTranslations } from "next-intl";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import type { User } from "@/types/user";

const ROLE_COLORS: Record<string, string> = {
  admin:
    "bg-status-critical/10 text-status-critical border-status-critical/20",
  dispatcher: "bg-interactive/10 text-interactive border-interactive/20",
  editor:
    "bg-status-delayed/10 text-status-delayed border-status-delayed/20",
  viewer: "bg-surface text-foreground-muted border-border",
};

interface DetailRowProps {
  label: string;
  value: string | null | undefined;
}

function DetailRow({ label, value }: DetailRowProps) {
  return (
    <div className="flex justify-between py-1.5">
      <span className="text-sm text-foreground-muted">{label}</span>
      <span className="text-sm font-medium text-foreground text-right max-w-[60%] break-words">
        {value ?? "-"}
      </span>
    </div>
  );
}

interface UserDetailProps {
  user: User | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onEdit: () => void;
  onDelete: () => void;
  onResetPassword: () => void;
}

export function UserDetail({
  user,
  open,
  onOpenChange,
  onEdit,
  onDelete,
  onResetPassword,
}: UserDetailProps) {
  const t = useTranslations("users");

  if (!user) return null;

  const formatDateTime = (dateStr: string) => {
    try {
      return new Intl.DateTimeFormat("en-CA", {
        dateStyle: "short",
        timeStyle: "short",
      }).format(new Date(dateStr));
    } catch {
      return dateStr;
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="sm:max-w-[28rem] max-h-[90vh] overflow-y-auto"
        showCloseButton
      >
        <DialogHeader>
          <DialogTitle className="font-heading text-heading font-semibold">
            {t("detail.title")}
          </DialogTitle>
          <DialogDescription className="sr-only">
            {t("detail.title")}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-(--spacing-card)">
          {/* Status badges */}
          <div className="flex gap-2">
            <Badge
              variant="outline"
              className={cn("text-xs", ROLE_COLORS[user.role] ?? "")}
            >
              {t(`roles.${user.role}`)}
            </Badge>
            <Badge
              variant="outline"
              className={cn(
                "text-xs",
                user.is_active
                  ? "bg-status-ontime/10 text-status-ontime border-status-ontime/20"
                  : "bg-status-critical/10 text-status-critical border-status-critical/20",
              )}
            >
              {user.is_active ? t("detail.active") : t("detail.inactive")}
            </Badge>
          </div>

          <Separator />

          {/* User Info */}
          <div>
            <DetailRow label={t("detail.name")} value={user.name} />
            <DetailRow label={t("detail.email")} value={user.email} />
          </div>

          <Separator />

          {/* Metadata */}
          <div>
            <DetailRow
              label={t("detail.createdAt")}
              value={formatDateTime(user.created_at)}
            />
            <DetailRow
              label={t("detail.updatedAt")}
              value={formatDateTime(user.updated_at)}
            />
          </div>

          <Separator />

          {/* Actions */}
          <div className="flex gap-2">
            <Button variant="outline" className="flex-1" onClick={onEdit}>
              {t("actions.edit")}
            </Button>
            <Button
              variant="outline"
              className="flex-1"
              onClick={onResetPassword}
            >
              {t("actions.resetPassword")}
            </Button>
            <Button
              variant="destructive"
              className="flex-1"
              onClick={onDelete}
            >
              {t("actions.delete")}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
