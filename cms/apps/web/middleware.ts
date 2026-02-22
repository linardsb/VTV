import { auth } from "./auth";
import { NextResponse } from "next/server";

// VTV RBAC — maps roles to allowed path prefixes (PRD Section 7.5)
const ROLE_PERMISSIONS: Record<string, string[]> = {
  admin: ["/routes", "/stops", "/schedules", "/drivers", "/gtfs", "/users", "/chat", "/documents"],
  dispatcher: ["/routes", "/stops", "/schedules", "/drivers", "/chat", "/documents"],
  editor: ["/routes", "/stops", "/schedules", "/drivers", "/gtfs", "/documents"],
  viewer: ["/routes", "/stops", "/schedules", "/drivers", "/documents"],
};

export default auth((req) => {
  const { pathname } = req.nextUrl;
  const role = req.auth?.user?.role;

  // Not authenticated — redirect to login
  if (!role) {
    return NextResponse.redirect(new URL("/lv/login", req.url));
  }

  // Extract path without locale prefix (e.g., /lv/routes → /routes)
  const segments = pathname.split("/");
  const pathWithoutLocale = "/" + segments.slice(2).join("/");

  const allowed = ROLE_PERMISSIONS[role] ?? [];
  if (!allowed.some((p) => pathWithoutLocale.startsWith(p))) {
    return NextResponse.redirect(new URL("/unauthorized", req.url));
  }
});

export const config = {
  matcher: ["/(lv|en)/(routes|stops|schedules|drivers|gtfs|users|chat|documents)/:path*"],
};
