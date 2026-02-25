/**
 * SWR fetcher using authFetch for authenticated API requests.
 *
 * Wraps authFetch so all SWR hooks automatically get JWT auth
 * and consistent error handling.
 */

import { authFetch } from "@/lib/auth-fetch";

export async function swrFetcher<T>(url: string): Promise<T> {
  const res = await authFetch(url);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json() as Promise<T>;
}
