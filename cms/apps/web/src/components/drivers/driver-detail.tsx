"use client";

import { useTranslations } from "next-intl";
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
import type { Driver } from "@/types/driver";

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

interface DriverDetailProps {
  driver: Driver | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onEdit: () => void;
  onDelete: () => void;
  isReadOnly: boolean;
}

export function DriverDetail({
  driver,
  open,
  onOpenChange,
  onEdit,
  onDelete,
  isReadOnly,
}: DriverDetailProps) {
  const t = useTranslations("drivers");

  if (!driver) return null;

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return null;
    try {
      return new Intl.DateTimeFormat("en-CA").format(new Date(dateStr));
    } catch {
      return dateStr;
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[28rem] max-h-[90vh] overflow-y-auto" showCloseButton>
        <DialogHeader>
          <DialogTitle className="font-heading text-heading font-semibold">
            {driver.first_name} {driver.last_name}
          </DialogTitle>
          <DialogDescription className="sr-only">
            {driver.first_name} {driver.last_name}
          </DialogDescription>
          <p className="text-xs font-mono text-foreground-muted">
            {driver.employee_number}
          </p>
        </DialogHeader>

        <div className="space-y-(--spacing-card)">
          {/* Status & Shift */}
          <div className="flex gap-2">
            <Badge variant="outline" className="text-xs">
              {t(`statuses.${driver.status}`)}
            </Badge>
            <Badge variant="outline" className="text-xs">
              {t(`shifts.${driver.default_shift}`)}
            </Badge>
            {!driver.is_active && (
              <Badge variant="outline" className="text-xs bg-status-critical/10 text-status-critical">
                {t("detail.inactive")}
              </Badge>
            )}
          </div>

          <Separator />

          {/* Personal Info */}
          <div>
            <p className="text-xs font-medium text-label-text uppercase tracking-wide mb-2">
              {t("detail.personalInfo")}
            </p>
            <DetailRow label={t("detail.phone")} value={driver.phone} />
            <DetailRow label={t("detail.email")} value={driver.email} />
            <DetailRow label={t("detail.dateOfBirth")} value={formatDate(driver.date_of_birth)} />
            <DetailRow label={t("detail.address")} value={driver.address} />
          </div>

          <Separator />

          {/* Emergency Contact */}
          <div>
            <p className="text-xs font-medium text-label-text uppercase tracking-wide mb-2">
              {t("detail.emergencyContact")}
            </p>
            <DetailRow label={t("detail.emergencyName")} value={driver.emergency_contact_name} />
            <DetailRow label={t("detail.emergencyPhone")} value={driver.emergency_contact_phone} />
          </div>

          <Separator />

          {/* Employment */}
          <div>
            <p className="text-xs font-medium text-label-text uppercase tracking-wide mb-2">
              {t("detail.employment")}
            </p>
            <DetailRow label={t("detail.hireDate")} value={formatDate(driver.hire_date)} />
            <DetailRow label={t("detail.shift")} value={t(`shifts.${driver.default_shift}`)} />
            <DetailRow label={t("detail.status")} value={t(`statuses.${driver.status}`)} />
          </div>

          <Separator />

          {/* License & Medical */}
          <div>
            <p className="text-xs font-medium text-label-text uppercase tracking-wide mb-2">
              {t("detail.licensing")}
            </p>
            <DetailRow label={t("detail.licenseCategories")} value={driver.license_categories} />
            <DetailRow label={t("detail.licenseExpiry")} value={formatDate(driver.license_expiry_date)} />
            <DetailRow label={t("detail.medicalCertExpiry")} value={formatDate(driver.medical_cert_expiry)} />
            <DetailRow label={t("detail.qualifiedRoutes")} value={driver.qualified_route_ids} />
          </div>

          {/* Notes */}
          {(driver.notes || driver.training_records) && (
            <>
              <Separator />
              <div>
                <p className="text-xs font-medium text-label-text uppercase tracking-wide mb-2">
                  {t("detail.notesSection")}
                </p>
                {driver.notes && <DetailRow label={t("detail.notes")} value={driver.notes} />}
                {driver.training_records && (
                  <DetailRow label={t("detail.trainingRecords")} value={driver.training_records} />
                )}
              </div>
            </>
          )}

          <Separator />

          {/* Metadata */}
          <div>
            <p className="text-xs font-medium text-label-text uppercase tracking-wide mb-2">
              {t("detail.metadata")}
            </p>
            <DetailRow
              label={t("detail.createdAt")}
              value={new Intl.DateTimeFormat("en-CA", {
                dateStyle: "short",
                timeStyle: "short",
              }).format(new Date(driver.created_at))}
            />
            <DetailRow
              label={t("detail.updatedAt")}
              value={new Intl.DateTimeFormat("en-CA", {
                dateStyle: "short",
                timeStyle: "short",
              }).format(new Date(driver.updated_at))}
            />
          </div>

          {/* Actions */}
          {!isReadOnly && (
            <>
              <Separator />
              <div className="flex gap-2">
                <Button variant="outline" className="flex-1" onClick={onEdit}>
                  {t("actions.edit")}
                </Button>
                <Button variant="destructive" className="flex-1" onClick={onDelete}>
                  {t("actions.delete")}
                </Button>
              </div>
            </>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
