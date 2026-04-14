/**
 * Configured @vtv/sdk client for the VTV web application.
 *
 * Configures the generated client with:
 * - Base URL resolved per execution context:
 *   - Browser: same-origin (empty base) so requests hit `/api/v1/*` on
 *     the current host and nginx proxies them to the app container.
 *     The build-time NEXT_PUBLIC_AGENT_URL value (`http://app:8123` in
 *     Docker) is unreachable from the browser — it's a Docker-network
 *     hostname — so using it here broke every client-side CRUD call.
 *   - Server (SSR / Route Handlers / Auth.js): NEXT_PUBLIC_AGENT_URL,
 *     which is the Docker-network URL in production and
 *     http://localhost:8123 in local dev.
 * - Automatic JWT auth token injection via request interceptor.
 *
 * Import this module for side-effects before using any SDK functions:
 *   import "@/lib/sdk";
 *   import { listEventsApiV1EventsGet } from "@vtv/sdk";
 */

import { client } from "@vtv/sdk/client";
import { getToken } from "@/lib/auth-fetch";

client.setConfig({
  baseUrl:
    typeof window !== "undefined"
      ? ""
      : (process.env.NEXT_PUBLIC_AGENT_URL ?? "http://localhost:8123"),
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
