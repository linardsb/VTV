"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Separator } from "@/components/ui/separator";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type {
  TrackedDevice,
  TrackedDeviceCreate,
  TrackedDeviceUpdate,
  DeviceProtocolType,
} from "@/types/fleet";

interface FleetDeviceFormProps {
  mode: "create" | "edit";
  device: TrackedDevice | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (data: TrackedDeviceCreate | TrackedDeviceUpdate) => void;
}

const PROTOCOLS: DeviceProtocolType[] = [
  "teltonika",
  "queclink",
  "general",
  "osmand",
  "other",
];

export function FleetDeviceForm({
  mode,
  device,
  open,
  onOpenChange,
  onSubmit,
}: FleetDeviceFormProps) {
  const t = useTranslations("fleet");
  const isEdit = mode === "edit";

  const [imei, setImei] = useState(device?.imei ?? "");
  const [deviceName, setDeviceName] = useState(device?.device_name ?? "");
  const [simNumber, setSimNumber] = useState(device?.sim_number ?? "");
  const [protocolType, setProtocolType] = useState<DeviceProtocolType>(
    device?.protocol_type ?? "general",
  );
  const [firmwareVersion, setFirmwareVersion] = useState(
    device?.firmware_version ?? "",
  );
  const [notes, setNotes] = useState(device?.notes ?? "");

  const isValidImei = /^\d{15}$/.test(imei);

  const handleSubmit = () => {
    if (!isValidImei) return;

    if (isEdit) {
      const data: TrackedDeviceUpdate = {};
      if (imei !== device?.imei) data.imei = imei;
      if (deviceName !== (device?.device_name ?? ""))
        data.device_name = deviceName || null;
      if (simNumber !== (device?.sim_number ?? ""))
        data.sim_number = simNumber || null;
      if (protocolType !== device?.protocol_type)
        data.protocol_type = protocolType;
      if (firmwareVersion !== (device?.firmware_version ?? ""))
        data.firmware_version = firmwareVersion || null;
      if (notes !== (device?.notes ?? "")) data.notes = notes || null;
      onSubmit(data);
    } else {
      const data: TrackedDeviceCreate = {
        imei,
        device_name: deviceName || null,
        sim_number: simNumber || null,
        protocol_type: protocolType,
        firmware_version: firmwareVersion || null,
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
          <p className="text-xs font-medium text-label-text uppercase tracking-wide">
            {t("form.imei")}
          </p>
          <div className="space-y-1">
            <Input
              value={imei}
              onChange={(e) => setImei(e.target.value)}
              placeholder="123456789012345"
              maxLength={15}
              aria-label={t("form.imei")}
            />
            <p className="text-xs text-foreground-subtle">
              {t("form.imeiHelp")}
            </p>
          </div>

          <div className="space-y-3">
            <div className="space-y-1">
              <p className="text-xs font-medium text-label-text uppercase tracking-wide">
                {t("form.deviceName")}
              </p>
              <Input
                value={deviceName}
                onChange={(e) => setDeviceName(e.target.value)}
                maxLength={100}
                aria-label={t("form.deviceName")}
              />
            </div>

            <div className="space-y-1">
              <p className="text-xs font-medium text-label-text uppercase tracking-wide">
                {t("form.simNumber")}
              </p>
              <Input
                value={simNumber}
                onChange={(e) => setSimNumber(e.target.value)}
                maxLength={20}
                aria-label={t("form.simNumber")}
              />
            </div>
          </div>

          <Separator />

          <div className="space-y-3">
            <div className="space-y-1">
              <p className="text-xs font-medium text-label-text uppercase tracking-wide">
                {t("form.protocol")}
              </p>
              <Select
                value={protocolType}
                onValueChange={(v) =>
                  setProtocolType(v as DeviceProtocolType)
                }
              >
                <SelectTrigger aria-label={t("form.protocol")}>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {PROTOCOLS.map((p) => (
                    <SelectItem key={p} value={p}>
                      {t(`filters.${p}`)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-1">
              <p className="text-xs font-medium text-label-text uppercase tracking-wide">
                {t("form.firmware")}
              </p>
              <Input
                value={firmwareVersion}
                onChange={(e) => setFirmwareVersion(e.target.value)}
                maxLength={50}
                aria-label={t("form.firmware")}
              />
            </div>
          </div>

          <Separator />

          <div className="space-y-1">
            <p className="text-xs font-medium text-label-text uppercase tracking-wide">
              {t("form.notes")}
            </p>
            <Textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              maxLength={2000}
              rows={3}
              aria-label={t("form.notes")}
            />
          </div>

          <div className="flex gap-2">
            <Button
              variant="outline"
              className="flex-1 cursor-pointer"
              onClick={() => onOpenChange(false)}
            >
              {t("actions.cancel")}
            </Button>
            <Button
              className="flex-1 cursor-pointer"
              onClick={handleSubmit}
              disabled={!isValidImei}
            >
              {t("actions.save")}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
