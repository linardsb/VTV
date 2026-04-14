"use client";

import { useState, useCallback } from "react";
import dynamic from "next/dynamic";
import { useTranslations } from "next-intl";
import { Skeleton } from "@/components/ui/skeleton";
import { JourneyForm } from "@/components/journey-planner/journey-form";
import { JourneyResults } from "@/components/journey-planner/journey-results";
import { fetchJourneyPlan, JourneyApiError } from "@/lib/journey-sdk";
import type { JourneyPlanResponse, JourneyPlanParams } from "@/types/journey";

function MapSkeleton() {
  return (
    <div className="flex h-full w-full items-center justify-center bg-surface">
      <Skeleton className="h-8 w-32" />
    </div>
  );
}

const JourneyMap = dynamic(
  () =>
    import("@/components/journey-planner/journey-map").then((m) => ({
      default: m.JourneyMap,
    })),
  { ssr: false, loading: () => <MapSkeleton /> },
);

export function JourneyPlannerPage() {
  const t = useTranslations("journeyPlanner");

  const [plan, setPlan] = useState<JourneyPlanResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedIndex, setSelectedIndex] = useState(0);

  const handleSearch = useCallback(
    async (params: JourneyPlanParams) => {
      setLoading(true);
      setError(null);
      setPlan(null);
      setSelectedIndex(0);
      try {
        const result = await fetchJourneyPlan(params);
        setPlan(result);
      } catch (err) {
        if (err instanceof JourneyApiError) {
          if (err.status === 503) {
            setError(t("serviceUnavailable"));
          } else if (err.status === 422) {
            setError(t("invalidParams"));
          } else {
            setError(t("error"));
          }
        } else {
          setError(t("error"));
        }
      } finally {
        setLoading(false);
      }
    },
    [t],
  );

  const selectedItinerary =
    plan && plan.itineraries.length > selectedIndex
      ? plan.itineraries[selectedIndex]
      : null;

  return (
    <div className="flex h-full flex-col gap-(--spacing-section) lg:flex-row">
      {/* Left panel: form + results */}
      <div className="w-full shrink-0 space-y-(--spacing-section) overflow-y-auto lg:w-80">
        <div>
          <h1 className="font-heading text-lg font-semibold text-foreground">
            {t("title")}
          </h1>
          <p className="text-sm text-foreground-muted">{t("description")}</p>
        </div>

        <JourneyForm onSubmit={handleSearch} loading={loading} />

        {error && (
          <div className="border border-error-border bg-error-bg p-(--spacing-card) text-sm text-error">
            {error}
          </div>
        )}

        {plan && (
          <>
            {plan.otp_enriched && (
              <p className="text-xs text-status-ontime">{t("enriched")}</p>
            )}
            <JourneyResults
              itineraries={plan.itineraries}
              selectedIndex={selectedIndex}
              onSelect={setSelectedIndex}
            />
          </>
        )}
      </div>

      {/* Right panel: map */}
      <div className="min-h-[24rem] flex-1 overflow-hidden lg:min-h-0">
        <JourneyMap itinerary={selectedItinerary} />
      </div>
    </div>
  );
}
