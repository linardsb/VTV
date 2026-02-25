/**
 * VTV Users API Client
 *
 * Connects to the FastAPI auth endpoints for user management.
 */

import type {
  User,
  UserCreate,
  UserUpdate,
  PaginatedUsers,
} from "@/types/user";
import { authFetch } from "@/lib/auth-fetch";

const BASE_URL =
  process.env.NEXT_PUBLIC_AGENT_URL ?? "http://localhost:8123";
const API_PREFIX = "/api/v1/auth";

/** Error thrown when the users API returns a non-OK response. */
export class UsersApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "UsersApiError";
    this.status = status;
  }
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const detail = await response.text().catch(() => "Unknown error");
    throw new UsersApiError(response.status, detail);
  }
  return response.json() as Promise<T>;
}

/** Fetch paginated users with optional filters. */
export async function fetchUsers(params: {
  page?: number;
  page_size?: number;
  search?: string;
  role?: string;
  is_active?: boolean;
}): Promise<PaginatedUsers> {
  const searchParams = new URLSearchParams();
  if (params.page !== undefined) searchParams.set("page", String(params.page));
  if (params.page_size !== undefined)
    searchParams.set("page_size", String(params.page_size));
  if (params.search) searchParams.set("search", params.search);
  if (params.role) searchParams.set("role", params.role);
  if (params.is_active !== undefined)
    searchParams.set("is_active", String(params.is_active));

  const response = await authFetch(
    `${BASE_URL}${API_PREFIX}/users?${searchParams.toString()}`,
  );
  return handleResponse<PaginatedUsers>(response);
}

/** Fetch a single user by ID. */
export async function fetchUser(id: number): Promise<User> {
  const response = await authFetch(`${BASE_URL}${API_PREFIX}/users/${id}`);
  return handleResponse<User>(response);
}

/** Create a new user. */
export async function createUser(data: UserCreate): Promise<User> {
  const response = await authFetch(`${BASE_URL}${API_PREFIX}/users`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  return handleResponse<User>(response);
}

/** Update an existing user. */
export async function updateUser(
  id: number,
  data: UserUpdate,
): Promise<User> {
  const response = await authFetch(`${BASE_URL}${API_PREFIX}/users/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  return handleResponse<User>(response);
}

/** Delete a user. */
export async function deleteUser(id: number): Promise<void> {
  const response = await authFetch(`${BASE_URL}${API_PREFIX}/users/${id}`, {
    method: "DELETE",
  });
  if (!response.ok) {
    const detail = await response.text().catch(() => "Unknown error");
    throw new UsersApiError(response.status, detail);
  }
}

/** Reset a user's password. */
export async function resetUserPassword(
  userId: number,
  newPassword: string,
): Promise<void> {
  const response = await authFetch(
    `${BASE_URL}${API_PREFIX}/reset-password`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: userId, new_password: newPassword }),
    },
  );
  if (!response.ok) {
    const detail = await response.text().catch(() => "Unknown error");
    throw new UsersApiError(response.status, detail);
  }
}
