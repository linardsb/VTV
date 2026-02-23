import NextAuth from "next-auth";
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

const AGENT_URL = process.env.NEXT_PUBLIC_AGENT_URL ?? "http://localhost:8123";

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
    jwt({ token, user }) {
      if (user) {
        token.role = user.role;
        token.accessToken = user.accessToken;
        token.refreshToken = user.refreshToken;
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
