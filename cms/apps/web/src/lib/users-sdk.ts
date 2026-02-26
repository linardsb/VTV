/**
 * Users API client powered by @vtv/sdk.
 *
 * Drop-in replacement for users-client.ts — same function signatures,
 * backed by the generated SDK instead of hand-written fetch calls.
 */

import "@/lib/sdk";
import {
  listUsersApiV1AuthUsersGet,
  getUserApiV1AuthUsersUserIdGet,
  createUserApiV1AuthUsersPost,
  updateUserApiV1AuthUsersUserIdPatch,
  deleteUserDataApiV1AuthUsersUserIdDelete,
  resetPasswordApiV1AuthResetPasswordPost,
} from "@vtv/sdk";
import type {
  User,
  UserCreate,
  UserUpdate,
  PaginatedUsers,
} from "@/types/user";

/** Error thrown when the users API returns a non-OK response. */
export class UsersApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "UsersApiError";
    this.status = status;
  }
}

/** Fetch paginated users with optional filters. */
export async function fetchUsers(params: {
  page?: number;
  page_size?: number;
  search?: string;
  role?: string;
  is_active?: boolean;
}): Promise<PaginatedUsers> {
  const { data, error, response } = await listUsersApiV1AuthUsersGet({
    query: {
      page: params.page,
      page_size: params.page_size,
      search: params.search ?? null,
      role: params.role ?? null,
      is_active: params.is_active ?? null,
    },
  });
  if (error || !data) {
    throw new UsersApiError(
      response.status,
      typeof error === "string" ? error : "Failed to fetch users",
    );
  }
  return data as unknown as PaginatedUsers;
}

/** Fetch a single user by ID. */
export async function fetchUser(id: number): Promise<User> {
  const { data, error, response } = await getUserApiV1AuthUsersUserIdGet({
    path: { user_id: id },
  });
  if (error || !data) {
    throw new UsersApiError(
      response.status,
      typeof error === "string" ? error : "Failed to fetch user",
    );
  }
  return data as unknown as User;
}

/** Create a new user. */
export async function createUser(userData: UserCreate): Promise<User> {
  const { data, error, response } = await createUserApiV1AuthUsersPost({
    body: userData,
  });
  if (error || !data) {
    throw new UsersApiError(
      response.status,
      typeof error === "string" ? error : "Failed to create user",
    );
  }
  return data as unknown as User;
}

/** Update an existing user. */
export async function updateUser(
  id: number,
  userData: UserUpdate,
): Promise<User> {
  const { data, error, response } =
    await updateUserApiV1AuthUsersUserIdPatch({
      path: { user_id: id },
      body: userData,
    });
  if (error || !data) {
    throw new UsersApiError(
      response.status,
      typeof error === "string" ? error : "Failed to update user",
    );
  }
  return data as unknown as User;
}

/** Delete a user. */
export async function deleteUser(id: number): Promise<void> {
  const { error, response } = await deleteUserDataApiV1AuthUsersUserIdDelete({
    path: { user_id: id },
  });
  if (error) {
    throw new UsersApiError(
      response.status,
      typeof error === "string" ? error : "Failed to delete user",
    );
  }
}

/** Reset a user's password. */
export async function resetUserPassword(
  userId: number,
  newPassword: string,
): Promise<void> {
  const { error, response } = await resetPasswordApiV1AuthResetPasswordPost({
    body: { user_id: userId, new_password: newPassword },
  });
  if (error) {
    throw new UsersApiError(
      response.status,
      typeof error === "string" ? error : "Failed to reset password",
    );
  }
}
