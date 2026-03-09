"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Menu, LogOut, ChevronRight } from "lucide-react";
import { useTranslations } from "next-intl";
import { useSession, signOut } from "next-auth/react";
import { cn } from "@/lib/utils";
import { useIsMobile } from "@/hooks/use-mobile";
import { LocaleToggle } from "@/components/locale-toggle";
import { ThemeToggle } from "@/components/theme-toggle";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";

type NavItem = {
  key: string;
  href: string;
  enabled: boolean;
};

type NavGroup = {
  key: string;
  children: NavItem[];
};

type NavEntry = NavItem | NavGroup;

function isGroup(entry: NavEntry): entry is NavGroup {
  return "children" in entry;
}

const navEntries: NavEntry[] = [
  { key: "dashboard", href: "", enabled: true },
  { key: "routes", href: "/routes", enabled: true },
  { key: "stops", href: "/stops", enabled: true },
  { key: "schedules", href: "/schedules", enabled: true },
  { key: "drivers", href: "/drivers", enabled: true },
  {
    key: "fleetGroup",
    children: [
      { key: "vehicles", href: "/vehicles", enabled: true },
      { key: "fleetDevices", href: "/fleet", enabled: true },
      { key: "fleetMap", href: "/fleet/map", enabled: true },
      { key: "telemetry", href: "/fleet/telemetry", enabled: true },
      { key: "geofences", href: "/geofences", enabled: true },
    ],
  },
  { key: "analytics", href: "/analytics", enabled: true },
  { key: "gtfs", href: "/gtfs", enabled: true },
  { key: "users", href: "/users", enabled: true },
  { key: "documents", href: "/documents", enabled: true },
  { key: "chat", href: "/chat", enabled: true },
];

interface AppSidebarProps {
  locale: string;
}

function NavLink({
  item,
  locale,
  pathname,
  t,
  indent,
}: {
  item: NavItem;
  locale: string;
  pathname: string;
  t: (key: string) => string;
  indent?: boolean;
}) {
  const isActive =
    item.href === ""
      ? pathname === `/${locale}` || pathname === `/${locale}/`
      : pathname.startsWith(`/${locale}${item.href}`);

  if (!item.enabled) {
    return (
      <span
        className={cn(
          "block rounded-md px-3 py-2 text-sm text-disabled-text cursor-not-allowed opacity-(--opacity-disabled)",
          indent && "pl-6"
        )}
      >
        {t(item.key)}
      </span>
    );
  }

  return (
    <Link
      href={`/${locale}${item.href}`}
      className={cn(
        "block rounded-md px-3 py-2 text-sm transition-colors",
        indent && "pl-6",
        isActive
          ? "bg-nav-active-bg text-nav-active-text font-semibold"
          : "font-medium text-nav-inactive-text hover:bg-nav-hover-bg hover:text-nav-active-text"
      )}
      aria-current={isActive ? "page" : undefined}
    >
      {t(item.key)}
    </Link>
  );
}

function NavGroupItem({
  group,
  locale,
  pathname,
  t,
}: {
  group: NavGroup;
  locale: string;
  pathname: string;
  t: (key: string) => string;
}) {
  const hasActiveChild = group.children.some((child) =>
    child.href === ""
      ? pathname === `/${locale}` || pathname === `/${locale}/`
      : pathname.startsWith(`/${locale}${child.href}`)
  );
  const [open, setOpen] = useState(hasActiveChild);

  return (
    <li>
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        className={cn(
          "flex w-full items-center justify-between rounded-md px-3 py-2 text-sm font-medium transition-colors cursor-pointer",
          hasActiveChild
            ? "text-nav-active-text"
            : "text-nav-inactive-text hover:bg-nav-hover-bg hover:text-nav-active-text"
        )}
        aria-expanded={open}
      >
        {t(group.key)}
        <ChevronRight
          className={cn(
            "size-4 transition-transform duration-200",
            open && "rotate-90"
          )}
        />
      </button>
      {/* CSS grid trick for smooth height animation */}
      <div
        className={cn(
          "grid transition-[grid-template-rows] duration-200 ease-out",
          open ? "grid-rows-[1fr]" : "grid-rows-[0fr]"
        )}
      >
        <ul className="overflow-hidden space-y-0.5">
          {group.children.map((child) => (
            <li key={child.key}>
              <NavLink
                item={child}
                locale={locale}
                pathname={pathname}
                t={t}
                indent
              />
            </li>
          ))}
        </ul>
      </div>
    </li>
  );
}

function NavContent({ locale }: { locale: string }) {
  const t = useTranslations("nav");
  const tCommon = useTranslations("common");
  const pathname = usePathname();
  const { data: session } = useSession();

  return (
    <>
      <nav aria-label="Main navigation">
        <p className="text-sm font-semibold text-foreground-muted mb-(--spacing-card)">
          VTV
        </p>
        <ul className="space-y-1">
          {navEntries.map((entry) => {
            if (isGroup(entry)) {
              return (
                <NavGroupItem
                  key={entry.key}
                  group={entry}
                  locale={locale}
                  pathname={pathname}
                  t={t}
                />
              );
            }

            return (
              <li key={entry.key}>
                <NavLink
                  item={entry}
                  locale={locale}
                  pathname={pathname}
                  t={t}
                />
              </li>
            );
          })}
        </ul>
      </nav>
      <div className="mt-auto border-t border-border pt-(--spacing-card)">
        {session?.user && (
          <div className="mb-2 px-3">
            <p className="truncate text-sm font-medium text-foreground">
              {session.user.name}
            </p>
            <p className="truncate text-xs text-foreground-muted">
              {session.user.email}
            </p>
          </div>
        )}
        <Button
          variant="ghost"
          size="sm"
          className="w-full justify-start gap-2 px-3 text-foreground-muted hover:text-foreground cursor-pointer"
          onClick={() => signOut({ callbackUrl: `/${locale}/login` })}
        >
          <LogOut className="size-4" />
          {tCommon("logout")}
        </Button>
        <div className="mt-2 flex items-center justify-between px-3">
          <ThemeToggle />
          <LocaleToggle />
        </div>
      </div>
    </>
  );
}

export function AppSidebar({ locale }: AppSidebarProps) {
  const isMobile = useIsMobile();
  const t = useTranslations("nav");
  const [open, setOpen] = useState(false);

  if (isMobile) {
    return (
      <>
        <header className="flex items-center justify-between border-b border-border bg-surface px-(--spacing-page) py-(--spacing-card)">
          <p className="text-sm font-semibold text-foreground">VTV</p>
          <Button
            variant="ghost"
            size="sm"
            className="size-10 p-0 cursor-pointer"
            onClick={() => setOpen(true)}
            aria-label={t("menu")}
          >
            <Menu className="size-5" />
          </Button>
        </header>
        <Sheet open={open} onOpenChange={setOpen}>
          <SheetContent side="left" className="w-[280px] flex flex-col p-4">
            <SheetHeader>
              <SheetTitle className="sr-only">{t("menu")}</SheetTitle>
            </SheetHeader>
            <NavContent locale={locale} />
          </SheetContent>
        </Sheet>
      </>
    );
  }

  return (
    <aside className="flex w-48 flex-col border-r border-border bg-surface p-3">
      <NavContent locale={locale} />
    </aside>
  );
}
