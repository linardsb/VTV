/**
 * Configured @vtv/sdk client for the VTV web application.
 *
 * Configures the generated client with:
 * - Base URL from NEXT_PUBLIC_AGENT_URL environment variable
 * - Automatic JWT auth token injection via request interceptor
 *
 * Import this module for side-effects before using any SDK functions:
 *   import "@/lib/sdk";
 *   import { listEventsApiV1EventsGet } from "@vtv/sdk";
 */

import { client } from "@vtv/sdk/client";
import { getToken } from "@/lib/auth-fetch";

client.setConfig({
  baseUrl: process.env.NEXT_PUBLIC_AGENT_URL ?? "http://localhost:8123",
});

// Auth interceptor: injects JWT Bearer token into every request.
// Uses the shared getToken() from auth-fetch which caches client-side tokens
// for 60s, avoiding redundant /api/auth/session round trips.
client.interceptors.request.use(async (request) => {
  const token = await getToken();

  if (token) {
    request.headers.set("Authorization", `Bearer ${token}`);
  }

  return request;
});
