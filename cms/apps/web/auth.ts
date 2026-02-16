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

export const { handlers, auth, signIn, signOut } = NextAuth({
  providers: [
    Credentials({
      credentials: {
        email: { label: "Email", type: "email" },
        password: { label: "Password", type: "password" },
      },
      async authorize(credentials) {
        // TODO: Replace with Drizzle ORM query when database is set up
        // For now, use a hardcoded demo user for development
        if (
          credentials?.email === "admin@vtv.lv" &&
          credentials?.password === "admin"
        ) {
          return {
            id: "1",
            email: "admin@vtv.lv",
            name: "VTV Admin",
            role: "admin" as VTVRole,
          };
        }
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
