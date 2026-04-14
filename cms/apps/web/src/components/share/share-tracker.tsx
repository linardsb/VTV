"use client";

import { useCallback } from "react";
import dynamic from "next/dynamic";
import useSWR from "swr";
import { useTranslations } from "next-intl";
import { Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { resolveShareLink, ShareApiError } from "@/lib/share-sdk";
import type { ShareLinkData, ShareVehiclePosition } from "@/types/share";

const ShareMap = dynamic(
  () => import("./share-map").then((m) => ({ default: m.ShareMap })),
  {
    ssr: false,
    loading: () => (
      <div className="flex h-full items-center justify-center bg-surface">
        <Loader2 className="size-8 animate-spin text-foreground-muted" />
      </div>
    ),
  },
);

interface ShareTrackerProps {
  token: string;
}

function formatDelay(
  delaySeconds: number | null,
  t: ReturnType<typeof useTranslations>,
): { text: string; className: string } {
  if (delaySeconds == null || delaySeconds <= 0) {
    return { text: t("onTime"), className: "text-status-ontime" };
  }
  const minutes = Math.round(delaySeconds / 60);
  return {
    text: `${t("delay")}: ${minutes} min`,
    className: "text-status-delayed",
  };
}

function formatTime(timestamp: string | null): string {
  if (!timestamp) return "—";
  try {
    return new Date(timestamp).toLocaleTimeString();
  } catch {
    return "—";
  }
}

function InfoPanel({
  position,
  t,
}: {
  position: ShareVehiclePosition;
  t: ReturnType<typeof useTranslations>;
}) {
  const delay = formatDelay(position.delay_seconds, t);

  return (
    <div className="absolute bottom-0 left-0 right-0 z-[1000] border-t border-border bg-surface p-(--spacing-card) shadow-md sm:bottom-4 sm:left-4 sm:right-auto sm:w-[320px] sm:border sm:shadow-lg">
      <div className="flex items-center gap-(--spacing-inline)">
        {position.route_short_name && (
          <span className="font-heading text-lg font-bold text-foreground">
            {position.route_short_name}
          </span>
        )}
        <span className="text-sm text-foreground-muted">
          {position.vehicle_id}
        </span>
      </div>

      <div className="mt-2 space-y-1 text-sm">
        <div className="flex justify-between">
          <span className="text-foreground-muted">{t("route")}</span>
          <span className="text-foreground">
            {position.route_id ?? "—"}
          </span>
        </div>
        <div className="flex justify-between">
          <span className="text-foreground-muted">{t("delay")}</span>
          <span className={delay.className}>{delay.text}</span>
        </div>
        {position.speed_kmh != null && (
          <div className="flex justify-between">
            <span className="text-foreground-muted">{t("speed")}</span>
            <span className="text-foreground">
              {Math.round(position.speed_kmh)} km/h
            </span>
          </div>
        )}
        {position.next_stop_name && (
          <div className="flex justify-between">
            <span className="text-foreground-muted">{t("nextStop")}</span>
            <span className="text-foreground">{position.next_stop_name}</span>
          </div>
        )}
        <div className="flex justify-between">
          <span className="text-foreground-muted">{t("lastUpdate")}</span>
          <span className="text-foreground">
            {formatTime(position.timestamp)}
          </span>
        </div>
      </div>
    </div>
  );
}

function BrandingFooter({ t }: { t: ReturnType<typeof useTranslations> }) {
  return (
    <div className="absolute left-0 right-0 top-0 z-[1000] bg-primary px-(--spacing-card) py-2 text-center text-xs font-medium text-primary-foreground">
      {t("poweredBy")}
    </div>
  );
}

function shareFetcher(token: string): Promise<ShareLinkData> {
  return resolveShareLink(token);
}

export function ShareTracker({ token }: ShareTrackerProps) {
  const t = useTranslations("shareView");

  const { data, error, isLoading, mutate } = useSWR<ShareLinkData, ShareApiError>(
    `share:${token}`,
    () => shareFetcher(token),
    { refreshInterval: 10_000, shouldRetryOnError: false },
  );

  const handleRetry = useCallback(() => {
    void mutate();
  }, [mutate]);

  if (isLoading) {
    return (
      <div className="flex h-screen flex-col items-center justify-center bg-surface">
        <Loader2 className="size-8 animate-spin text-foreground-muted" />
        <p className="mt-2 text-sm text-foreground-muted">{t("loading")}</p>
      </div>
    );
  }

  if (error instanceof ShareApiError && error.status === 410) {
    return (
      <div className="flex h-screen flex-col items-center justify-center bg-surface">
        <p className="font-heading text-lg font-semibold text-foreground">
          {t("expired")}
        </p>
        <p className="mt-2 text-sm text-foreground-muted">{t("poweredBy")}</p>
      </div>
    );
  }

  if (error instanceof ShareApiError && error.status === 404) {
    return (
      <div className="flex h-screen flex-col items-center justify-center bg-surface">
        <p className="font-heading text-lg font-semibold text-foreground">
          {t("notFound")}
        </p>
        <p className="mt-2 text-sm text-foreground-muted">{t("poweredBy")}</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex h-screen flex-col items-center justify-center bg-surface">
        <p className="font-heading text-lg font-semibold text-error">
          {t("error")}
        </p>
        <Button
          variant="outline"
          className="mt-4 cursor-pointer"
          onClick={handleRetry}
        >
          {t("loading")}
        </Button>
      </div>
    );
  }

  const position = data?.position ?? null;

  return (
    <div className="relative h-screen w-full">
      <BrandingFooter t={t} />
      <ShareMap position={position} />
      {position && <InfoPanel position={position} t={t} />}
    </div>
  );
}
