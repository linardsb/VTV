/**
 * Resolve the backend API base URL for the current execution context.
 *
 * Browser: empty string → requests hit `/api/v1/*` on the current origin
 * and nginx proxies them to the app container. The build-time
 * NEXT_PUBLIC_AGENT_URL (e.g. `http://app:8123` in Docker) is a
 * Docker-network hostname the browser cannot resolve.
 *
 * Server (SSR, Route Handlers, Auth.js authorize): the baked
 * NEXT_PUBLIC_AGENT_URL, which is the Docker-network URL in
 * production and http://localhost:8123 in local dev.
 */
export function apiBase(): string {
  if (typeof window !== "undefined") return "";
  return process.env.NEXT_PUBLIC_AGENT_URL ?? "http://localhost:8123";
}
