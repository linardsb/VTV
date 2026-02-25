"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { Switch } from "@/components/ui/switch";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import type { User, UserCreate, UserUpdate } from "@/types/user";

interface UserFormProps {
  mode: "create" | "edit";
  user?: User | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (data: UserCreate | UserUpdate) => void;
}

export function UserForm({
  mode,
  user,
  open,
  onOpenChange,
  onSubmit,
}: UserFormProps) {
  const t = useTranslations("users");
  const isEdit = mode === "edit";

  const [name, setName] = useState(user?.name ?? "");
  const [email, setEmail] = useState(user?.email ?? "");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState(user?.role ?? "viewer");
  const [isActive, setIsActive] = useState(user?.is_active ?? true);

  const isPasswordValid =
    isEdit ||
    (password.length >= 10 &&
      /[A-Z]/.test(password) &&
      /[a-z]/.test(password) &&
      /\d/.test(password));

  const isFormValid =
    name.trim() !== "" &&
    email.trim() !== "" &&
    role !== "" &&
    isPasswordValid;

  const handleSubmit = () => {
    if (!isFormValid) return;

    if (isEdit) {
      const data: UserUpdate = {};
      if (name !== user?.name) data.name = name;
      if (email !== user?.email) data.email = email;
      if (role !== user?.role) data.role = role;
      if (isActive !== user?.is_active) data.is_active = isActive;
      onSubmit(data);
    } else {
      const data: UserCreate = {
        name,
        email,
        password,
        role,
      };
      onSubmit(data);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="max-h-[90vh] overflow-y-auto"
        showCloseButton
      >
        <DialogHeader>
          <DialogTitle className="font-heading text-heading font-semibold">
            {isEdit ? t("form.editTitle") : t("form.createTitle")}
          </DialogTitle>
          <DialogDescription className="sr-only">
            {isEdit ? t("form.editTitle") : t("form.createTitle")}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-(--spacing-card)">
          <div className="space-y-3">
            <div>
              <Label htmlFor="userName">
                {t("form.name")} *
              </Label>
              <Input
                id="userName"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder={t("form.namePlaceholder")}
              />
            </div>
            <div>
              <Label htmlFor="userEmail">
                {t("form.email")} *
              </Label>
              <Input
                id="userEmail"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder={t("form.emailPlaceholder")}
              />
            </div>

            {/* Password — create mode only */}
            {!isEdit && (
              <div>
                <Label htmlFor="userPassword">
                  {t("form.password")} *
                </Label>
                <Input
                  id="userPassword"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder={t("form.passwordPlaceholder")}
                />
                <p className="mt-1 text-xs text-foreground-muted">
                  {t("form.passwordHelp")}
                </p>
              </div>
            )}

            <div>
              <Label htmlFor="userRole">
                {t("form.role")} *
              </Label>
              <Select value={role} onValueChange={setRole}>
                <SelectTrigger id="userRole">
                  <SelectValue placeholder={t("form.selectRole")} />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="admin">
                    {t("roles.admin")}
                  </SelectItem>
                  <SelectItem value="dispatcher">
                    {t("roles.dispatcher")}
                  </SelectItem>
                  <SelectItem value="editor">
                    {t("roles.editor")}
                  </SelectItem>
                  <SelectItem value="viewer">
                    {t("roles.viewer")}
                  </SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          {/* Active toggle — edit mode only */}
          {isEdit && (
            <>
              <Separator />
              <div className="flex items-center justify-between">
                <Label htmlFor="userIsActive">{t("form.isActive")}</Label>
                <Switch
                  id="userIsActive"
                  checked={isActive}
                  onCheckedChange={setIsActive}
                />
              </div>
            </>
          )}

          {/* Actions */}
          <Separator />
          <div className="flex gap-2">
            <Button
              variant="outline"
              className="flex-1"
              onClick={() => onOpenChange(false)}
            >
              {t("actions.cancel")}
            </Button>
            <Button
              className="flex-1"
              onClick={handleSubmit}
              disabled={!isFormValid}
            >
              {t("actions.save")}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
