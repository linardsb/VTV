"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { Textarea } from "@/components/ui/textarea";
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
import type { MaintenanceRecordCreate } from "@/types/vehicle";

interface MaintenanceFormProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (data: MaintenanceRecordCreate) => void;
}

export function MaintenanceForm({
  open,
  onOpenChange,
  onSubmit,
}: MaintenanceFormProps) {
  const t = useTranslations("vehicles.maintenance");
  const tActions = useTranslations("vehicles.actions");

  const [maintenanceType, setMaintenanceType] = useState("scheduled");
  const [description, setDescription] = useState("");
  const [performedDate, setPerformedDate] = useState("");
  const [mileageAtService, setMileageAtService] = useState("");
  const [costEur, setCostEur] = useState("");
  const [nextScheduledDate, setNextScheduledDate] = useState("");
  const [performedBy, setPerformedBy] = useState("");
  const [notes, setNotes] = useState("");

  const handleSubmit = () => {
    if (!description.trim() || !performedDate) return;

    const data: MaintenanceRecordCreate = {
      maintenance_type: maintenanceType as
        | "scheduled"
        | "unscheduled"
        | "inspection"
        | "repair",
      description,
      performed_date: performedDate,
      mileage_at_service: mileageAtService
        ? Number(mileageAtService)
        : null,
      cost_eur: costEur ? Number(costEur) : null,
      next_scheduled_date: nextScheduledDate || null,
      performed_by: performedBy || null,
      notes: notes || null,
    };
    onSubmit(data);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="sm:max-w-[28rem] max-h-[90vh] overflow-y-auto"
        showCloseButton
      >
        <DialogHeader>
          <DialogTitle className="font-heading text-heading font-semibold">
            {t("formTitle")}
          </DialogTitle>
          <DialogDescription className="sr-only">
            {t("formTitle")}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-(--spacing-card)">
          <div className="space-y-3">
            <div>
              <Label htmlFor="maintenanceType">{t("type")} *</Label>
              <Select
                value={maintenanceType}
                onValueChange={setMaintenanceType}
              >
                <SelectTrigger id="maintenanceType">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="scheduled">
                    {t("types.scheduled")}
                  </SelectItem>
                  <SelectItem value="unscheduled">
                    {t("types.unscheduled")}
                  </SelectItem>
                  <SelectItem value="inspection">
                    {t("types.inspection")}
                  </SelectItem>
                  <SelectItem value="repair">
                    {t("types.repair")}
                  </SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label htmlFor="description">{t("description")} *</Label>
              <Textarea
                id="description"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                rows={3}
              />
            </div>
            <div>
              <Label htmlFor="performedDate">
                {t("performedDate")} *
              </Label>
              <Input
                id="performedDate"
                type="date"
                value={performedDate}
                onChange={(e) => setPerformedDate(e.target.value)}
              />
            </div>
          </div>

          <Separator />

          <div className="space-y-3">
            <div>
              <Label htmlFor="mileageAtService">
                {t("mileageAtService")}
              </Label>
              <Input
                id="mileageAtService"
                type="number"
                value={mileageAtService}
                onChange={(e) => setMileageAtService(e.target.value)}
              />
            </div>
            <div>
              <Label htmlFor="costEur">{t("cost")}</Label>
              <Input
                id="costEur"
                type="number"
                step="0.01"
                value={costEur}
                onChange={(e) => setCostEur(e.target.value)}
              />
            </div>
            <div>
              <Label htmlFor="nextScheduledDate">
                {t("nextScheduledDate")}
              </Label>
              <Input
                id="nextScheduledDate"
                type="date"
                value={nextScheduledDate}
                onChange={(e) => setNextScheduledDate(e.target.value)}
              />
            </div>
            <div>
              <Label htmlFor="performedBy">{t("performedBy")}</Label>
              <Input
                id="performedBy"
                value={performedBy}
                onChange={(e) => setPerformedBy(e.target.value)}
              />
            </div>
            <div>
              <Label htmlFor="maintenanceNotes">{t("notes")}</Label>
              <Textarea
                id="maintenanceNotes"
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                rows={2}
              />
            </div>
          </div>

          {/* Actions */}
          <Separator />
          <div className="flex gap-2">
            <Button
              variant="outline"
              className="flex-1"
              onClick={() => onOpenChange(false)}
            >
              {tActions("cancel")}
            </Button>
            <Button
              className="flex-1"
              onClick={handleSubmit}
              disabled={!description.trim() || !performedDate}
            >
              {t("addRecord")}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
