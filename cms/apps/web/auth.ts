import NextAuth from "next-auth";
import type { JWT } from "next-auth/jwt";
import Credentials from "next-auth/providers/credentials";
import type { DefaultSession } from "next-auth";

// VTV role type — matches PRD Section 7.5
export type VTVRole = "admin" | "dispatcher" | "editor" | "viewer";

declare module "next-auth" {
  interface Session {
    user: { role: VTVRole } & DefaultSession["user"];
    accessToken?: string;
  }
  interface User {
    role: VTVRole;
    accessToken?: string;
    refreshToken?: string;
  }
}

declare module "next-auth/jwt" {
  interface JWT {
    role?: string;
    accessToken?: string;
    refreshToken?: string;
    accessTokenExpires?: number;
  }
}

const AGENT_URL = process.env.NEXT_PUBLIC_AGENT_URL ?? "http://localhost:8123";

// Refresh the backend access token 5 minutes before it expires
const REFRESH_BUFFER_MS = 5 * 60 * 1000;

/** Decode JWT payload without verification (expiry check only). */
function decodeJwtExpiry(token: string): number | null {
  try {
    const payload = JSON.parse(
      Buffer.from(token.split(".")[1], "base64").toString(),
    ) as { exp?: number };
    return payload.exp ? payload.exp * 1000 : null;
  } catch {
    return null;
  }
}

/** Use the refresh token to get a new access token from the backend. */
async function refreshAccessToken(token: JWT): Promise<JWT> {
  try {
    const response = await fetch(`${AGENT_URL}/api/v1/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: token.refreshToken }),
    });

    if (!response.ok) {
      // Refresh token expired or revoked — force re-login
      return { ...token, accessToken: undefined, accessTokenExpires: 0 };
    }

    const data = (await response.json()) as { access_token: string };
    const newExpiry = decodeJwtExpiry(data.access_token);

    return {
      ...token,
      accessToken: data.access_token,
      accessTokenExpires: newExpiry ?? Date.now() + 30 * 60 * 1000,
    };
  } catch {
    // Backend unreachable — keep existing token, retry next time
    return token;
  }
}

// SECURITY: Frontend brute-force protection (defense in depth — backend also enforces)
const LOGIN_MAX_ATTEMPTS = 5;
const LOGIN_LOCKOUT_MS = 15 * 60 * 1000; // 15 minutes

interface LoginAttempt {
  count: number;
  lockedUntil: number | null;
}

const loginAttempts = new Map<string, LoginAttempt>();

function checkBruteForce(email: string): boolean {
  const attempt = loginAttempts.get(email);
  if (!attempt) return true;
  if (attempt.lockedUntil && Date.now() < attempt.lockedUntil) return false;
  if (attempt.lockedUntil && Date.now() >= attempt.lockedUntil) {
    loginAttempts.delete(email);
    return true;
  }
  return true;
}

function recordFailedAttempt(email: string): void {
  const attempt = loginAttempts.get(email) ?? { count: 0, lockedUntil: null };
  attempt.count += 1;
  if (attempt.count >= LOGIN_MAX_ATTEMPTS) {
    attempt.lockedUntil = Date.now() + LOGIN_LOCKOUT_MS;
  }
  loginAttempts.set(email, attempt);
}

function clearAttempts(email: string): void {
  loginAttempts.delete(email);
}

export const { handlers, auth, signIn, signOut } = NextAuth({
  providers: [
    Credentials({
      credentials: {
        email: { label: "Email", type: "email" },
        password: { label: "Password", type: "password" },
      },
      async authorize(credentials) {
        const email = credentials?.email as string | undefined;
        const password = credentials?.password as string | undefined;
        if (!email || !password) return null;

        // SECURITY: Frontend brute-force check (defense in depth)
        if (!checkBruteForce(email)) {
          return null;
        }

        try {
          const response = await fetch(`${AGENT_URL}/api/v1/auth/login`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email, password }),
          });

          if (!response.ok) {
            recordFailedAttempt(email);
            return null;
          }

          const user = (await response.json()) as {
            id: number;
            email: string;
            name: string;
            role: VTVRole;
            access_token: string;
            refresh_token: string;
          };

          clearAttempts(email);
          return {
            id: String(user.id),
            email: user.email,
            name: user.name,
            role: user.role,
            accessToken: user.access_token,
            refreshToken: user.refresh_token,
          };
        } catch {
          // Backend unreachable — treat as failed attempt
          recordFailedAttempt(email);
          return null;
        }
      },
    }),
  ],
  callbacks: {
    async jwt({ token, user }) {
      // Initial sign-in: store tokens and expiry from backend response
      if (user) {
        token.role = user.role;
        token.accessToken = user.accessToken;
        token.refreshToken = user.refreshToken;
        token.accessTokenExpires = user.accessToken
          ? (decodeJwtExpiry(user.accessToken) ?? Date.now() + 30 * 60 * 1000)
          : 0;
        return token;
      }

      // Subsequent requests: refresh if access token is expiring soon
      const expiresAt = token.accessTokenExpires ?? 0;
      if (Date.now() < expiresAt - REFRESH_BUFFER_MS) {
        // Token still fresh
        return token;
      }

      // Token expired or expiring soon — refresh it
      if (token.refreshToken) {
        return refreshAccessToken(token);
      }

      return token;
    },
    session({ session, token }) {
      const validRoles: string[] = ["admin", "dispatcher", "editor", "viewer"];
      session.user.role = validRoles.includes(token.role as string)
        ? (token.role as VTVRole)
        : "viewer";
      session.accessToken = typeof token.accessToken === "string" ? token.accessToken : undefined;
      return session;
    },
  },
  pages: {
    signIn: "/lv/login",
  },
});
