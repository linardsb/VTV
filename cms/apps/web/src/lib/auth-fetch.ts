/**
 * Authenticated fetch wrapper for VTV API clients.
 *
 * Extracts the backend JWT access token from the Auth.js session
 * and adds the Authorization: Bearer header to all requests.
 *
 * Works in both server components (uses auth() — cheap, no network call)
 * and client components (uses getSession() — fetches from /api/auth/session).
 *
 * Client-side tokens are cached for 60s to avoid redundant /api/auth/session
 * round trips (both authFetch and SDK client share this cache).
 *
 * Usage:
 *   import { authFetch } from "@/lib/auth-fetch"
 *   const response = await authFetch(`${BASE_URL}/api/v1/stops/`)
 */

// Client-side token cache (60s TTL, never persisted to disk/localStorage).
// These module-level variables exist in SSR scope too, but the `typeof window`
// guard in getToken() skips the cache server-side — auth() is called fresh
// every time. Safe because SSR never reads/writes _cachedToken.
let _cachedToken: string | null = null;
let _cachedAt = 0;
const TOKEN_CACHE_TTL = 60_000;

/**
 * Get the current auth token with client-side caching.
 * Server-side: always fresh (auth() is cheap).
 * Client-side: cached for 60s to avoid redundant session fetches.
 */
export async function getToken(): Promise<string | undefined> {
  if (typeof window === "undefined") {
    // Server-side: auth() decodes the httpOnly JWT cookie — cheap (no DB/network call)
    const { auth } = await import("../../auth");
    const session = await auth();
    return session?.accessToken;
  }

  // Client-side: check cache first
  if (_cachedToken && Date.now() - _cachedAt < TOKEN_CACHE_TTL) {
    return _cachedToken;
  }

  // Cache miss — fetch from session endpoint
  const { getSession } = await import("next-auth/react");
  const session = await getSession();
  const token = session?.accessToken;

  if (token) {
    _cachedToken = token;
    _cachedAt = Date.now();
  }

  return token;
}

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
  const token = await getToken();

  const headers = new Headers(options?.headers);
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  return fetch(url, {
    ...options,
    headers,
  });
}
