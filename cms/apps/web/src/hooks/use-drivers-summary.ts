"use client";

import { useState, useEffect, useCallback } from "react";
import { useSession } from "next-auth/react";
import type { Driver } from "@/types/driver";
import { authFetch } from "@/lib/auth-fetch";

interface UseDriversSummaryResult {
  drivers: Driver[];
  isLoading: boolean;
}

const POLL_INTERVAL = 120_000; // 2 minutes

export function useDriversSummary(): UseDriversSummaryResult {
  const apiBase =
    process.env.NEXT_PUBLIC_AGENT_URL ?? "http://localhost:8123";
  const { status } = useSession();
  const [drivers, setDrivers] = useState<Driver[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      const res = await authFetch(
        `${apiBase}/api/v1/drivers?active_only=true&page_size=100`,
      );
      if (res.ok) {
        const data = (await res.json()) as { items: Driver[] };
        setDrivers(data.items);
      }
    } catch {
      // Silently fall back — roster stays empty
    } finally {
      setIsLoading(false);
    }
  }, [apiBase]);

  useEffect(() => {
    if (status !== "authenticated") return;
    void load();
    const interval = setInterval(() => void load(), POLL_INTERVAL);
    return () => clearInterval(interval);
  }, [load, status]);

  return { drivers, isLoading };
}
