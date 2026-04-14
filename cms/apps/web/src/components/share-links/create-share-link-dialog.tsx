"use client";

import { useState, useCallback } from "react";
import { useTranslations } from "next-intl";
import { useLocale } from "next-intl";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
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
import { createShareLink } from "@/lib/share-sdk";
import type {
  ShareLinkExpiryHours,
  ShareLinkResponse,
} from "@/types/share";
import { QrCodeDisplay } from "./qr-code-display";

const EXPIRY_OPTIONS: ShareLinkExpiryHours[] = [1, 2, 4, 6, 12, 24];

interface CreateShareLinkDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreated: (link: ShareLinkResponse) => void;
}

export function CreateShareLinkDialog({
  open,
  onOpenChange,
  onCreated,
}: CreateShareLinkDialogProps) {
  const t = useTranslations("shareLinks");
  const locale = useLocale();

  const [vehicleId, setVehicleId] = useState("");
  const [routeId, setRouteId] = useState("");
  const [feedId, setFeedId] = useState("riga");
  const [expiryHours, setExpiryHours] = useState<ShareLinkExpiryHours>(1);
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<ShareLinkResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      setSubmitting(true);
      setError(null);
      try {
        const link = await createShareLink({
          vehicle_id: vehicleId,
          route_id: routeId || null,
          feed_id: feedId || "riga",
          expiry_hours: expiryHours,
        });
        setResult(link);
        onCreated(link);
      } catch {
        setError(t("createError"));
      } finally {
        setSubmitting(false);
      }
    },
    [vehicleId, routeId, feedId, expiryHours, onCreated, t],
  );

  const fullShareUrl = result
    ? `${typeof window !== "undefined" ? window.location.origin : ""}/${locale}/share/${result.token}`
    : "";

  const handleCopy = useCallback(async () => {
    await navigator.clipboard.writeText(fullShareUrl);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }, [fullShareUrl]);

  const handleClose = useCallback(
    (isOpen: boolean) => {
      if (!isOpen) {
        setResult(null);
        setVehicleId("");
        setRouteId("");
        setFeedId("riga");
        setExpiryHours(1);
        setError(null);
        setCopied(false);
      }
      onOpenChange(isOpen);
    },
    [onOpenChange],
  );

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-[32rem]">
        <DialogHeader>
          <DialogTitle>{t("createLink")}</DialogTitle>
          <DialogDescription>{t("description")}</DialogDescription>
        </DialogHeader>

        {result ? (
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>{t("copyUrl")}</Label>
              <div className="flex gap-2">
                <Input value={fullShareUrl} readOnly />
                <Button
                  variant="outline"
                  className="shrink-0 cursor-pointer"
                  onClick={() => void handleCopy()}
                >
                  {copied ? t("linkCopied") : t("copyUrl")}
                </Button>
              </div>
            </div>

            <div className="flex justify-center">
              <QrCodeDisplay
                base64={result.qr_code_base64}
                alt={`${t("qrCode")} — ${result.vehicle_id}`}
              />
            </div>

            <div className="text-center text-sm text-foreground-muted">
              {t("expiresAt")}:{" "}
              {new Date(result.expires_at).toLocaleString()}
            </div>
          </div>
        ) : (
          <form onSubmit={(e) => void handleSubmit(e)} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="vehicle-id">{t("vehicleId")}</Label>
              <Input
                id="vehicle-id"
                value={vehicleId}
                onChange={(e) => setVehicleId(e.target.value)}
                required
                pattern="^[\w\-.:]+$"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="route-id">{t("routeId")}</Label>
              <Input
                id="route-id"
                value={routeId}
                onChange={(e) => setRouteId(e.target.value)}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="feed-id">{t("feedId")}</Label>
              <Input
                id="feed-id"
                value={feedId}
                onChange={(e) => setFeedId(e.target.value)}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="expiry-hours">{t("expiryHours")}</Label>
              <Select
                value={String(expiryHours)}
                onValueChange={(v) =>
                  setExpiryHours(Number(v) as ShareLinkExpiryHours)
                }
              >
                <SelectTrigger id="expiry-hours" className="cursor-pointer">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {EXPIRY_OPTIONS.map((h) => (
                    <SelectItem
                      key={h}
                      value={String(h)}
                      className="cursor-pointer"
                    >
                      {t("hours", { count: h })}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {error && (
              <p className="text-sm text-error">{error}</p>
            )}

            <Button
              type="submit"
              className="w-full cursor-pointer"
              disabled={submitting || !vehicleId}
            >
              {submitting ? t("createLink") + "..." : t("createLink")}
            </Button>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
}
