import NextAuth from "next-auth";
import Credentials from "next-auth/providers/credentials";
import type { DefaultSession } from "next-auth";

// VTV role type — matches PRD Section 7.5
export type VTVRole = "admin" | "dispatcher" | "editor" | "viewer";

declare module "next-auth" {
  interface Session {
    user: { role: VTVRole } & DefaultSession["user"];
  }
  interface User {
    role: VTVRole;
  }
}

// SECURITY: Login brute-force protection
// 5 failed attempts per email = 15-minute lockout
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
        if (!email) return null;

        // SECURITY: Check brute-force lockout
        if (!checkBruteForce(email)) {
          return null;
        }

        // SECURITY: Replace with Drizzle ORM query when database is set up
        // Hardcoded demo user for development only
        if (email === "admin@vtv.lv" && credentials?.password === "admin") {
          clearAttempts(email);
          return {
            id: "1",
            email: "admin@vtv.lv",
            name: "VTV Admin",
            role: "admin" as VTVRole,
          };
        }

        recordFailedAttempt(email);
        return null;
      },
    }),
  ],
  callbacks: {
    jwt({ token, user }) {
      if (user) {
        (token as Record<string, unknown>).role = user.role;
      }
      return token;
    },
    session({ session, token }) {
      session.user.role = (token as Record<string, unknown>).role as VTVRole;
      return session;
    },
  },
  pages: {
    signIn: "/lv/login",
  },
});
