"use client";

import { useState, useCallback } from "react";
import { useTranslations } from "next-intl";
import { useLocale } from "next-intl";
import { Plus, Copy, Check } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import type { ShareLinkResponse } from "@/types/share";
import { CreateShareLinkDialog } from "./create-share-link-dialog";
import { QrCodeDisplay } from "./qr-code-display";

export function ShareLinksPage() {
  const t = useTranslations("shareLinks");
  const locale = useLocale();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [recentLinks, setRecentLinks] = useState<ShareLinkResponse[]>([]);
  const [copiedId, setCopiedId] = useState<number | null>(null);

  const handleCreated = useCallback((link: ShareLinkResponse) => {
    setRecentLinks((prev) => [link, ...prev]);
  }, []);

  const handleCopy = useCallback(
    async (link: ShareLinkResponse) => {
      const fullUrl = `${window.location.origin}/${locale}/share/${link.token}`;
      await navigator.clipboard.writeText(fullUrl);
      setCopiedId(link.id);
      setTimeout(() => setCopiedId(null), 2000);
    },
    [locale],
  );

  const isExpired = (expiresAt: string): boolean => {
    return new Date(expiresAt) < new Date();
  };

  return (
    <div className="space-y-(--spacing-section) p-(--spacing-page)">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-heading text-2xl font-semibold text-foreground">
            {t("title")}
          </h1>
          <p className="mt-1 text-sm text-foreground-muted">
            {t("description")}
          </p>
        </div>
        <Button
          className="cursor-pointer"
          onClick={() => setDialogOpen(true)}
        >
          <Plus className="mr-2 size-4" />
          {t("createLink")}
        </Button>
      </div>

      {recentLinks.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 text-foreground-muted">
          <p className="text-sm">{t("noLinks")}</p>
        </div>
      ) : (
        <div className="space-y-(--spacing-grid)">
          {recentLinks.map((link) => {
            const expired = isExpired(link.expires_at);
            return (
              <div
                key={link.id}
                className="border border-border bg-surface p-(--spacing-card)"
              >
                <div className="flex flex-col gap-(--spacing-grid) sm:flex-row sm:items-start sm:justify-between">
                  <div className="space-y-2">
                    <div className="flex items-center gap-(--spacing-inline)">
                      <span className="font-heading text-sm font-semibold text-foreground">
                        {link.vehicle_id}
                      </span>
                      {link.route_id && (
                        <span className="text-sm text-foreground-muted">
                          {link.route_id}
                        </span>
                      )}
                      <Badge variant={expired ? "destructive" : "default"}>
                        {expired ? t("expired") : t("active")}
                      </Badge>
                    </div>

                    <div className="space-y-1 text-sm text-foreground-muted">
                      <div>
                        {t("feedId")}: {link.feed_id}
                      </div>
                      <div>
                        {t("expiresAt")}:{" "}
                        {new Date(link.expires_at).toLocaleString()}
                      </div>
                      <div>
                        {t("createdAt")}:{" "}
                        {new Date(link.created_at).toLocaleString()}
                      </div>
                    </div>

                    <Button
                      variant="outline"
                      size="sm"
                      className="cursor-pointer"
                      onClick={() => void handleCopy(link)}
                    >
                      {copiedId === link.id ? (
                        <>
                          <Check className="mr-2 size-4" />
                          {t("linkCopied")}
                        </>
                      ) : (
                        <>
                          <Copy className="mr-2 size-4" />
                          {t("copyUrl")}
                        </>
                      )}
                    </Button>
                  </div>

                  <div className="shrink-0">
                    <QrCodeDisplay
                      base64={link.qr_code_base64}
                      alt={`${t("qrCode")} — ${link.vehicle_id}`}
                      size={140}
                    />
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      <CreateShareLinkDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        onCreated={handleCreated}
      />
    </div>
  );
}
