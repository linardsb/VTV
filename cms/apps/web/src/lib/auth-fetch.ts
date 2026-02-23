/**
 * Authenticated fetch wrapper for VTV API clients.
 *
 * Extracts the backend JWT access token from the Auth.js session
 * and adds the Authorization: Bearer header to all requests.
 *
 * Works in both server components (uses auth() — cheap, no network call)
 * and client components (uses getSession() — fetches from /api/auth/session).
 *
 * Usage:
 *   import { authFetch } from "@/lib/auth-fetch"
 *   const response = await authFetch(`${BASE_URL}/api/v1/stops/`)
 */

/**
 * Fetch wrapper that automatically adds Bearer token from Auth.js session.
 *
 * Falls back to unauthenticated request if no session/token is available
 * (the backend will return 401 in that case).
 */
export async function authFetch(
  url: string,
  options?: RequestInit,
): Promise<Response> {
  let token: string | undefined;

  if (typeof window === "undefined") {
    // Server-side: auth() decodes the httpOnly JWT cookie — cheap (no DB/network call)
    const { auth } = await import("../../auth");
    const session = await auth();
    token = session?.accessToken;
  } else {
    // Client-side: getSession() fetches from /api/auth/session endpoint
    const { getSession } = await import("next-auth/react");
    const session = await getSession();
    token = session?.accessToken;
  }

  const headers = new Headers(options?.headers);
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  return fetch(url, {
    ...options,
    headers,
  });
}
