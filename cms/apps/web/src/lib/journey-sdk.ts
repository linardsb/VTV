/**
 * Journey planner API client using authFetch.
 *
 * Uses authFetch directly because the @vtv/sdk does not yet include
 * the journey planner endpoint. Can be migrated to SDK wrappers
 * once the SDK is regenerated with the backend running.
 */

import { authFetch } from "@/lib/auth-fetch";
import type { JourneyPlanParams, JourneyPlanResponse } from "@/types/journey";

const BASE = process.env.NEXT_PUBLIC_AGENT_URL ?? "http://localhost:8123";

export class JourneyApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "JourneyApiError";
    this.status = status;
  }
}

/** Fetch a journey plan from the OTP-backed endpoint. */
export async function fetchJourneyPlan(
  params: JourneyPlanParams,
): Promise<JourneyPlanResponse> {
  const query = new URLSearchParams();
  query.set("from_lat", String(params.from_lat));
  query.set("from_lon", String(params.from_lon));
  query.set("to_lat", String(params.to_lat));
  query.set("to_lon", String(params.to_lon));
  if (params.depart_at) query.set("depart_at", params.depart_at);
  if (params.arrive_by) query.set("arrive_by", params.arrive_by);
  if (params.modes) query.set("modes", params.modes);

  const res = await authFetch(
    `${BASE}/api/v1/transit/plan?${query.toString()}`,
  );
  if (!res.ok) {
    throw new JourneyApiError(res.status, "Failed to fetch journey plan");
  }
  return res.json() as Promise<JourneyPlanResponse>;
}
