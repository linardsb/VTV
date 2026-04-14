"use client";

import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";
import { Download } from "lucide-react";

interface QrCodeDisplayProps {
  base64: string;
  alt: string;
  size?: number;
}

export function QrCodeDisplay({ base64, alt, size = 200 }: QrCodeDisplayProps) {
  const t = useTranslations("shareLinks");
  const dataUri = `data:image/png;base64,${base64}`;

  return (
    <div className="flex flex-col items-center gap-(--spacing-grid)">
      {/* eslint-disable-next-line @next/next/no-img-element -- base64 data URI, next/image requires a URL */}
      <img
        src={dataUri}
        alt={alt}
        width={size}
        height={size}
        className="border border-border"
      />
      <Button variant="outline" size="sm" className="cursor-pointer" asChild>
        <a href={dataUri} download="vtv-share-qr.png">
          <Download className="mr-2 size-4" />
          {t("qrCode")}
        </a>
      </Button>
    </div>
  );
}
