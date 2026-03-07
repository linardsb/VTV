"use client";

import useSWR from "swr";
import { useSession } from "next-auth/react";
import type { AnalyticsOverviewResponse } from "@/types/analytics";

const API_BASE = process.env.NEXT_PUBLIC_AGENT_URL ?? "http://localhost:8123";

export function useAnalyticsOverview() {
  const { status } = useSession();

  const swrKey =
    status === "authenticated"
      ? `${API_BASE}/api/v1/analytics/overview`
      : null;

  const { data, error, isLoading, mutate } =
    useSWR<AnalyticsOverviewResponse>(swrKey, { refreshInterval: 60_000 });

  return {
    data,
    isLoading,
    error: error instanceof Error ? error.message : null,
    refresh: mutate,
  };
}
