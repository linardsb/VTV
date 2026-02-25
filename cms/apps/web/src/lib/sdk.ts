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

client.setConfig({
  baseUrl: process.env.NEXT_PUBLIC_AGENT_URL ?? "http://localhost:8123",
});

// Auth interceptor: injects JWT Bearer token into every request.
// Uses the same dual-context pattern as authFetch:
// - Server-side: auth() decodes httpOnly JWT cookie (cheap, no network)
// - Client-side: getSession() fetches from /api/auth/session
client.interceptors.request.use(async (request) => {
  let token: string | undefined;

  if (typeof window === "undefined") {
    const { auth } = await import("../../auth");
    const session = await auth();
    token = session?.accessToken;
  } else {
    const { getSession } = await import("next-auth/react");
    const session = await getSession();
    token = session?.accessToken;
  }

  if (token) {
    request.headers.set("Authorization", `Bearer ${token}`);
  }

  return request;
});
