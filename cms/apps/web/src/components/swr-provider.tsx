"use client";

import { SWRConfig } from "swr";
import { swrFetcher } from "@/lib/swr-fetcher";

interface SWRProviderProps {
  children: React.ReactNode;
}

export function SWRProvider({ children }: SWRProviderProps) {
  return (
    <SWRConfig
      value={{
        fetcher: swrFetcher,
        dedupingInterval: 5000,
        revalidateOnFocus: true,
        errorRetryCount: 3,
        errorRetryInterval: 5000,
      }}
    >
      {children}
    </SWRConfig>
  );
}
