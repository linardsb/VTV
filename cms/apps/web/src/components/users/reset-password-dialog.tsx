"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import type { User } from "@/types/user";

interface ResetPasswordDialogProps {
  user: User | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onConfirm: (newPassword: string) => void;
}

export function ResetPasswordDialog({
  user,
  open,
  onOpenChange,
  onConfirm,
}: ResetPasswordDialogProps) {
  const t = useTranslations("users.resetPassword");
  const [password, setPassword] = useState("");

  if (!user) return null;

  const isValid =
    password.length >= 10 &&
    /[A-Z]/.test(password) &&
    /[a-z]/.test(password) &&
    /\d/.test(password);

  const handleConfirm = () => {
    if (!isValid) return;
    onConfirm(password);
    setPassword("");
    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t("title")}</DialogTitle>
          <DialogDescription>
            {t("description", { name: user.name })}
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-2">
          <Label htmlFor="newPassword">{t("newPassword")}</Label>
          <Input
            id="newPassword"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder={t("placeholder")}
          />
          <p className="text-xs text-foreground-muted">{t("help")}</p>
          {password.length > 0 && !isValid && (
            <p className="text-xs text-status-critical">{t("help")}</p>
          )}
        </div>
        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => {
              setPassword("");
              onOpenChange(false);
            }}
          >
            {t("cancel")}
          </Button>
          <Button onClick={handleConfirm} disabled={!isValid}>
            {t("confirm")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
