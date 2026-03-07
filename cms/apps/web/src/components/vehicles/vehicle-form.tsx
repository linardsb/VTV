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
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import type { Vehicle, VehicleCreate, VehicleUpdate } from "@/types/vehicle";

interface VehicleFormProps {
  mode: "create" | "edit";
  vehicle?: Vehicle | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (data: VehicleCreate | VehicleUpdate) => void;
}

export function VehicleForm({
  mode,
  vehicle,
  open,
  onOpenChange,
  onSubmit,
}: VehicleFormProps) {
  const t = useTranslations("vehicles");
  const isEdit = mode === "edit";

  const [fleetNumber, setFleetNumber] = useState(
    vehicle?.fleet_number ?? "",
  );
  const [vehicleType, setVehicleType] = useState<string>(
    vehicle?.vehicle_type ?? "bus",
  );
  const [licensePlate, setLicensePlate] = useState(
    vehicle?.license_plate ?? "",
  );
  const [manufacturer, setManufacturer] = useState(
    vehicle?.manufacturer ?? "",
  );
  const [modelName, setModelName] = useState(vehicle?.model_name ?? "");
  const [modelYear, setModelYear] = useState(
    vehicle?.model_year?.toString() ?? "",
  );
  const [capacity, setCapacity] = useState(
    vehicle?.capacity?.toString() ?? "",
  );
  const [status, setStatus] = useState<string>(vehicle?.status ?? "active");
  const [mileage, setMileage] = useState(
    vehicle?.mileage_km?.toString() ?? "0",
  );
  const [registrationExpiry, setRegistrationExpiry] = useState(
    vehicle?.registration_expiry ?? "",
  );
  const [nextMaintenance, setNextMaintenance] = useState(
    vehicle?.next_maintenance_date ?? "",
  );
  const [qualifiedRoutes, setQualifiedRoutes] = useState(
    vehicle?.qualified_route_ids ?? "",
  );
  const [notes, setNotes] = useState(vehicle?.notes ?? "");
  const [isActive, setIsActive] = useState(vehicle?.is_active ?? true);

  const handleSubmit = () => {
    if (!fleetNumber.trim() || !licensePlate.trim()) return;

    if (isEdit) {
      const data: VehicleUpdate = {};
      if (fleetNumber !== vehicle?.fleet_number)
        data.fleet_number = fleetNumber;
      if (vehicleType !== vehicle?.vehicle_type)
        data.vehicle_type = vehicleType as
          | "bus"
          | "trolleybus"
          | "tram";
      if (licensePlate !== vehicle?.license_plate)
        data.license_plate = licensePlate;
      if (manufacturer !== (vehicle?.manufacturer ?? ""))
        data.manufacturer = manufacturer || null;
      if (modelName !== (vehicle?.model_name ?? ""))
        data.model_name = modelName || null;
      const newYear = modelYear ? Number(modelYear) : null;
      if (newYear !== vehicle?.model_year) data.model_year = newYear;
      const newCapacity = capacity ? Number(capacity) : null;
      if (newCapacity !== vehicle?.capacity) data.capacity = newCapacity;
      if (status !== vehicle?.status)
        data.status = status as "active" | "inactive" | "maintenance";
      const newMileage = mileage ? Number(mileage) : undefined;
      if (newMileage !== undefined && newMileage !== vehicle?.mileage_km)
        data.mileage_km = newMileage;
      if (registrationExpiry !== (vehicle?.registration_expiry ?? ""))
        data.registration_expiry = registrationExpiry || null;
      if (nextMaintenance !== (vehicle?.next_maintenance_date ?? ""))
        data.next_maintenance_date = nextMaintenance || null;
      if (qualifiedRoutes !== (vehicle?.qualified_route_ids ?? ""))
        data.qualified_route_ids = qualifiedRoutes || null;
      if (notes !== (vehicle?.notes ?? "")) data.notes = notes || null;
      onSubmit(data);
    } else {
      const data: VehicleCreate = {
        fleet_number: fleetNumber,
        vehicle_type: vehicleType as "bus" | "trolleybus" | "tram",
        license_plate: licensePlate,
        manufacturer: manufacturer || null,
        model_name: modelName || null,
        model_year: modelYear ? Number(modelYear) : null,
        capacity: capacity ? Number(capacity) : null,
        qualified_route_ids: qualifiedRoutes || null,
        notes: notes || null,
      };
      onSubmit(data);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="sm:max-w-[32rem] max-h-[90vh] overflow-y-auto"
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
          {/* Vehicle Information */}
          <p className="text-xs font-medium text-label-text uppercase tracking-wide">
            {t("form.vehicleInfo")}
          </p>
          <div className="space-y-3">
            <div>
              <Label htmlFor="fleetNumber">
                {t("form.fleetNumber")} *
              </Label>
              <Input
                id="fleetNumber"
                value={fleetNumber}
                onChange={(e) => setFleetNumber(e.target.value)}
                readOnly={isEdit}
                className={isEdit ? "bg-muted" : ""}
              />
            </div>
            <div>
              <Label htmlFor="vehicleType">
                {t("form.vehicleType")} *
              </Label>
              <Select value={vehicleType} onValueChange={setVehicleType}>
                <SelectTrigger id="vehicleType">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="bus">{t("types.bus")}</SelectItem>
                  <SelectItem value="trolleybus">
                    {t("types.trolleybus")}
                  </SelectItem>
                  <SelectItem value="tram">{t("types.tram")}</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label htmlFor="licensePlate">
                {t("form.licensePlate")} *
              </Label>
              <Input
                id="licensePlate"
                value={licensePlate}
                onChange={(e) => setLicensePlate(e.target.value)}
              />
            </div>
          </div>

          <Separator />

          {/* Specifications */}
          <p className="text-xs font-medium text-label-text uppercase tracking-wide">
            {t("form.specifications")}
          </p>
          <div className="space-y-3">
            <div>
              <Label htmlFor="manufacturer">
                {t("form.manufacturer")}
              </Label>
              <Input
                id="manufacturer"
                value={manufacturer}
                onChange={(e) => setManufacturer(e.target.value)}
              />
            </div>
            <div>
              <Label htmlFor="modelName">{t("form.modelName")}</Label>
              <Input
                id="modelName"
                value={modelName}
                onChange={(e) => setModelName(e.target.value)}
              />
            </div>
            <div>
              <Label htmlFor="modelYear">{t("form.modelYear")}</Label>
              <Input
                id="modelYear"
                type="number"
                value={modelYear}
                onChange={(e) => setModelYear(e.target.value)}
              />
            </div>
            <div>
              <Label htmlFor="capacity">{t("form.capacity")}</Label>
              <Input
                id="capacity"
                type="number"
                value={capacity}
                onChange={(e) => setCapacity(e.target.value)}
              />
            </div>
          </div>

          {/* Operations (edit mode only) */}
          {isEdit && (
            <>
              <Separator />
              <p className="text-xs font-medium text-label-text uppercase tracking-wide">
                {t("form.operations")}
              </p>
              <div className="space-y-3">
                <div>
                  <Label htmlFor="status">{t("form.status")}</Label>
                  <Select value={status} onValueChange={setStatus}>
                    <SelectTrigger id="status">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="active">
                        {t("statuses.active")}
                      </SelectItem>
                      <SelectItem value="inactive">
                        {t("statuses.inactive")}
                      </SelectItem>
                      <SelectItem value="maintenance">
                        {t("statuses.maintenance")}
                      </SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <Label htmlFor="mileage">{t("form.mileage")}</Label>
                  <Input
                    id="mileage"
                    type="number"
                    value={mileage}
                    onChange={(e) => setMileage(e.target.value)}
                  />
                </div>
                <div>
                  <Label htmlFor="registrationExpiry">
                    {t("form.registrationExpiry")}
                  </Label>
                  <Input
                    id="registrationExpiry"
                    type="date"
                    value={registrationExpiry}
                    onChange={(e) =>
                      setRegistrationExpiry(e.target.value)
                    }
                  />
                </div>
                <div>
                  <Label htmlFor="nextMaintenance">
                    {t("form.nextMaintenance")}
                  </Label>
                  <Input
                    id="nextMaintenance"
                    type="date"
                    value={nextMaintenance}
                    onChange={(e) => setNextMaintenance(e.target.value)}
                  />
                </div>
                <div>
                  <Label htmlFor="qualifiedRoutes">
                    {t("form.qualifiedRoutes")}
                  </Label>
                  <Input
                    id="qualifiedRoutes"
                    value={qualifiedRoutes}
                    onChange={(e) => setQualifiedRoutes(e.target.value)}
                    placeholder="bus_1,bus_3,bus_7"
                  />
                </div>
              </div>
            </>
          )}

          <Separator />

          {/* Notes */}
          <p className="text-xs font-medium text-label-text uppercase tracking-wide">
            {t("form.notesSection")}
          </p>
          <div className="space-y-3">
            <div>
              <Label htmlFor="notes">{t("form.notes")}</Label>
              <Textarea
                id="notes"
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                rows={3}
              />
            </div>
          </div>

          {/* Active toggle (edit mode only) */}
          {isEdit && (
            <>
              <Separator />
              <div className="flex items-center justify-between">
                <Label htmlFor="isActive">{t("form.isActive")}</Label>
                <Switch
                  id="isActive"
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
              disabled={!fleetNumber.trim() || !licensePlate.trim()}
            >
              {t("actions.save")}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
