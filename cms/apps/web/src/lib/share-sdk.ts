import { authFetch } from "@/lib/auth-fetch";
import type {
  ShareLinkCreateParams,
  ShareLinkResponse,
  ShareLinkData,
} from "@/types/share";

const BASE = process.env.NEXT_PUBLIC_AGENT_URL ?? "http://localhost:8123";

export class ShareApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "ShareApiError";
    this.status = status;
  }
}

/** Create a share link (requires admin/dispatcher auth). */
export async function createShareLink(
  params: ShareLinkCreateParams,
): Promise<ShareLinkResponse> {
  const res = await authFetch(`${BASE}/api/v1/transit/share`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
  if (!res.ok)
    throw new ShareApiError(res.status, "Failed to create share link");
  return res.json() as Promise<ShareLinkResponse>;
}

/** Resolve a share link token (public, no auth). */
export async function resolveShareLink(
  token: string,
): Promise<ShareLinkData> {
  const res = await fetch(
    `${BASE}/api/v1/transit/share/${encodeURIComponent(token)}`,
  );
  if (res.status === 410) throw new ShareApiError(410, "expired");
  if (!res.ok) throw new ShareApiError(res.status, "not_found");
  return res.json() as Promise<ShareLinkData>;
}
