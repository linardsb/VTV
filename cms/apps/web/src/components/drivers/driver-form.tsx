"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import type { Driver, DriverCreate, DriverUpdate } from "@/types/driver";

interface DriverFormProps {
  mode: "create" | "edit";
  driver?: Driver | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (data: DriverCreate | DriverUpdate) => void;
}

export function DriverForm({
  mode,
  driver,
  open,
  onOpenChange,
  onSubmit,
}: DriverFormProps) {
  const t = useTranslations("drivers");
  const isEdit = mode === "edit";

  const [firstName, setFirstName] = useState(driver?.first_name ?? "");
  const [lastName, setLastName] = useState(driver?.last_name ?? "");
  const [employeeNumber, setEmployeeNumber] = useState(driver?.employee_number ?? "");
  const [dateOfBirth, setDateOfBirth] = useState(driver?.date_of_birth ?? "");
  const [phone, setPhone] = useState(driver?.phone ?? "");
  const [email, setEmail] = useState(driver?.email ?? "");
  const [address, setAddress] = useState(driver?.address ?? "");
  const [emergencyName, setEmergencyName] = useState(driver?.emergency_contact_name ?? "");
  const [emergencyPhone, setEmergencyPhone] = useState(driver?.emergency_contact_phone ?? "");
  const [hireDate, setHireDate] = useState(driver?.hire_date ?? "");
  const [defaultShift, setDefaultShift] = useState(driver?.default_shift ?? "morning");
  const [status, setStatus] = useState(driver?.status ?? "available");
  const [licenseCategories, setLicenseCategories] = useState(driver?.license_categories ?? "");
  const [licenseExpiry, setLicenseExpiry] = useState(driver?.license_expiry_date ?? "");
  const [medicalExpiry, setMedicalExpiry] = useState(driver?.medical_cert_expiry ?? "");
  const [qualifiedRoutes, setQualifiedRoutes] = useState(driver?.qualified_route_ids ?? "");
  const [notes, setNotes] = useState(driver?.notes ?? "");
  const [trainingRecords, setTrainingRecords] = useState(driver?.training_records ?? "");
  const [isActive, setIsActive] = useState(driver?.is_active ?? true);

  const handleSubmit = () => {
    if (!firstName.trim() || !lastName.trim() || !employeeNumber.trim()) return;

    if (isEdit) {
      const data: DriverUpdate = {};
      if (firstName !== driver?.first_name) data.first_name = firstName;
      if (lastName !== driver?.last_name) data.last_name = lastName;
      if (employeeNumber !== driver?.employee_number) data.employee_number = employeeNumber;
      if (dateOfBirth !== (driver?.date_of_birth ?? ""))
        data.date_of_birth = dateOfBirth || null;
      if (phone !== (driver?.phone ?? "")) data.phone = phone || null;
      if (email !== (driver?.email ?? "")) data.email = email || null;
      if (address !== (driver?.address ?? "")) data.address = address || null;
      if (emergencyName !== (driver?.emergency_contact_name ?? ""))
        data.emergency_contact_name = emergencyName || null;
      if (emergencyPhone !== (driver?.emergency_contact_phone ?? ""))
        data.emergency_contact_phone = emergencyPhone || null;
      if (hireDate !== (driver?.hire_date ?? "")) data.hire_date = hireDate || null;
      if (defaultShift !== driver?.default_shift) data.default_shift = defaultShift;
      if (status !== driver?.status) data.status = status;
      if (licenseCategories !== (driver?.license_categories ?? ""))
        data.license_categories = licenseCategories || null;
      if (licenseExpiry !== (driver?.license_expiry_date ?? ""))
        data.license_expiry_date = licenseExpiry || null;
      if (medicalExpiry !== (driver?.medical_cert_expiry ?? ""))
        data.medical_cert_expiry = medicalExpiry || null;
      if (qualifiedRoutes !== (driver?.qualified_route_ids ?? ""))
        data.qualified_route_ids = qualifiedRoutes || null;
      if (notes !== (driver?.notes ?? "")) data.notes = notes || null;
      if (trainingRecords !== (driver?.training_records ?? ""))
        data.training_records = trainingRecords || null;
      if (isActive !== driver?.is_active) data.is_active = isActive;
      onSubmit(data);
    } else {
      const data: DriverCreate = {
        first_name: firstName,
        last_name: lastName,
        employee_number: employeeNumber,
        date_of_birth: dateOfBirth || null,
        phone: phone || null,
        email: email || null,
        address: address || null,
        emergency_contact_name: emergencyName || null,
        emergency_contact_phone: emergencyPhone || null,
        hire_date: hireDate || null,
        default_shift: defaultShift,
        status,
        license_categories: licenseCategories || null,
        license_expiry_date: licenseExpiry || null,
        medical_cert_expiry: medicalExpiry || null,
        qualified_route_ids: qualifiedRoutes || null,
        notes: notes || null,
        training_records: trainingRecords || null,
      };
      onSubmit(data);
    }
  };

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-full overflow-y-auto sm:w-[420px]">
        <SheetHeader>
          <SheetTitle className="font-heading text-heading font-semibold">
            {isEdit ? t("form.editTitle") : t("form.createTitle")}
          </SheetTitle>
        </SheetHeader>

        <div className="px-4 pb-4 space-y-(--spacing-card)">
          {/* Personal Info */}
          <p className="text-xs font-medium text-label-text uppercase tracking-wide">
            {t("form.personalInfo")}
          </p>
          <div className="space-y-3">
            <div>
              <Label htmlFor="firstName">{t("form.firstName")} *</Label>
              <Input id="firstName" value={firstName} onChange={(e) => setFirstName(e.target.value)} />
            </div>
            <div>
              <Label htmlFor="lastName">{t("form.lastName")} *</Label>
              <Input id="lastName" value={lastName} onChange={(e) => setLastName(e.target.value)} />
            </div>
            <div>
              <Label htmlFor="employeeNumber">{t("form.employeeNumber")} *</Label>
              <Input
                id="employeeNumber"
                value={employeeNumber}
                onChange={(e) => setEmployeeNumber(e.target.value)}
                readOnly={isEdit}
                className={isEdit ? "bg-muted" : ""}
              />
            </div>
            <div>
              <Label htmlFor="dateOfBirth">{t("form.dateOfBirth")}</Label>
              <Input id="dateOfBirth" type="date" value={dateOfBirth} onChange={(e) => setDateOfBirth(e.target.value)} />
            </div>
            <div>
              <Label htmlFor="phone">{t("form.phone")}</Label>
              <Input id="phone" value={phone} onChange={(e) => setPhone(e.target.value)} />
            </div>
            <div>
              <Label htmlFor="email">{t("form.email")}</Label>
              <Input id="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
            </div>
          </div>

          <Separator />

          {/* Address & Emergency */}
          <p className="text-xs font-medium text-label-text uppercase tracking-wide">
            {t("form.emergencySection")}
          </p>
          <div className="space-y-3">
            <div>
              <Label htmlFor="address">{t("form.address")}</Label>
              <Textarea id="address" value={address} onChange={(e) => setAddress(e.target.value)} rows={2} />
            </div>
            <div>
              <Label htmlFor="emergencyName">{t("form.emergencyName")}</Label>
              <Input id="emergencyName" value={emergencyName} onChange={(e) => setEmergencyName(e.target.value)} />
            </div>
            <div>
              <Label htmlFor="emergencyPhone">{t("form.emergencyPhone")}</Label>
              <Input id="emergencyPhone" value={emergencyPhone} onChange={(e) => setEmergencyPhone(e.target.value)} />
            </div>
          </div>

          <Separator />

          {/* Employment */}
          <p className="text-xs font-medium text-label-text uppercase tracking-wide">
            {t("form.employmentSection")}
          </p>
          <div className="space-y-3">
            <div>
              <Label htmlFor="hireDate">{t("form.hireDate")}</Label>
              <Input id="hireDate" type="date" value={hireDate} onChange={(e) => setHireDate(e.target.value)} />
            </div>
            <div>
              <Label htmlFor="defaultShift">{t("form.defaultShift")}</Label>
              <Select value={defaultShift} onValueChange={setDefaultShift}>
                <SelectTrigger id="defaultShift">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="morning">{t("shifts.morning")}</SelectItem>
                  <SelectItem value="afternoon">{t("shifts.afternoon")}</SelectItem>
                  <SelectItem value="evening">{t("shifts.evening")}</SelectItem>
                  <SelectItem value="night">{t("shifts.night")}</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label htmlFor="status">{t("form.status")}</Label>
              <Select value={status} onValueChange={setStatus}>
                <SelectTrigger id="status">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="available">{t("statuses.available")}</SelectItem>
                  <SelectItem value="on_duty">{t("statuses.on_duty")}</SelectItem>
                  <SelectItem value="on_leave">{t("statuses.on_leave")}</SelectItem>
                  <SelectItem value="sick">{t("statuses.sick")}</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          <Separator />

          {/* License & Medical */}
          <p className="text-xs font-medium text-label-text uppercase tracking-wide">
            {t("form.licenseSection")}
          </p>
          <div className="space-y-3">
            <div>
              <Label htmlFor="licenseCategories">{t("form.licenseCategories")}</Label>
              <Input
                id="licenseCategories"
                value={licenseCategories}
                onChange={(e) => setLicenseCategories(e.target.value)}
                placeholder="D,D1,DE"
              />
            </div>
            <div>
              <Label htmlFor="licenseExpiry">{t("form.licenseExpiry")}</Label>
              <Input id="licenseExpiry" type="date" value={licenseExpiry} onChange={(e) => setLicenseExpiry(e.target.value)} />
            </div>
            <div>
              <Label htmlFor="medicalExpiry">{t("form.medicalExpiry")}</Label>
              <Input id="medicalExpiry" type="date" value={medicalExpiry} onChange={(e) => setMedicalExpiry(e.target.value)} />
            </div>
            <div>
              <Label htmlFor="qualifiedRoutes">{t("form.qualifiedRoutes")}</Label>
              <Input
                id="qualifiedRoutes"
                value={qualifiedRoutes}
                onChange={(e) => setQualifiedRoutes(e.target.value)}
                placeholder="bus_1,bus_3,bus_7"
              />
            </div>
          </div>

          <Separator />

          {/* Notes */}
          <p className="text-xs font-medium text-label-text uppercase tracking-wide">
            {t("form.notesSection")}
          </p>
          <div className="space-y-3">
            <div>
              <Label htmlFor="notes">{t("form.notes")}</Label>
              <Textarea id="notes" value={notes} onChange={(e) => setNotes(e.target.value)} rows={3} />
            </div>
            <div>
              <Label htmlFor="trainingRecords">{t("form.trainingRecords")}</Label>
              <Textarea id="trainingRecords" value={trainingRecords} onChange={(e) => setTrainingRecords(e.target.value)} rows={3} />
            </div>
          </div>

          {/* Active toggle (edit mode only) */}
          {isEdit && (
            <>
              <Separator />
              <div className="flex items-center justify-between">
                <Label htmlFor="isActive">{t("form.isActive")}</Label>
                <Switch id="isActive" checked={isActive} onCheckedChange={setIsActive} />
              </div>
            </>
          )}

          {/* Actions */}
          <Separator />
          <div className="flex gap-2">
            <Button variant="outline" className="flex-1" onClick={() => onOpenChange(false)}>
              {t("actions.cancel")}
            </Button>
            <Button
              className="flex-1"
              onClick={handleSubmit}
              disabled={!firstName.trim() || !lastName.trim() || !employeeNumber.trim()}
            >
              {t("actions.save")}
            </Button>
          </div>
        </div>
      </SheetContent>
    </Sheet>
  );
}
