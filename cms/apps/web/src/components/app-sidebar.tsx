"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Menu } from "lucide-react";
import { useTranslations } from "next-intl";
import { cn } from "@/lib/utils";
import { useIsMobile } from "@/hooks/use-mobile";
import { LocaleToggle } from "@/components/locale-toggle";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";

const navItems = [
  { key: "dashboard", href: "", enabled: true },
  { key: "routes", href: "/routes", enabled: true },
  { key: "stops", href: "/stops", enabled: false },
  { key: "schedules", href: "/schedules", enabled: false },
  { key: "gtfs", href: "/gtfs", enabled: false },
  { key: "users", href: "/users", enabled: false },
  { key: "chat", href: "/chat", enabled: true },
] as const;

interface AppSidebarProps {
  locale: string;
}

function NavContent({ locale }: { locale: string }) {
  const t = useTranslations("nav");
  const pathname = usePathname();

  return (
    <>
      <nav aria-label="Main navigation">
        <p className="text-sm font-semibold text-foreground-muted mb-(--spacing-card)">
          VTV
        </p>
        <ul className="space-y-1">
          {navItems.map((item) => {
            const isActive = item.href === ""
              ? pathname === `/${locale}` || pathname === `/${locale}/`
              : pathname.startsWith(`/${locale}${item.href}`);

            return (
              <li key={item.key}>
                {item.enabled ? (
                  <Link
                    href={`/${locale}${item.href}`}
                    className={cn(
                      "block rounded-md px-3 py-2 text-sm transition-colors",
                      isActive
                        ? "bg-nav-active-bg text-nav-active-text font-semibold"
                        : "font-medium text-nav-inactive-text hover:bg-nav-hover-bg hover:text-nav-active-text"
                    )}
                    aria-current={isActive ? "page" : undefined}
                  >
                    {t(item.key)}
                  </Link>
                ) : (
                  <span className="block rounded-md px-3 py-2 text-sm text-disabled-text cursor-not-allowed opacity-(--opacity-disabled)">
                    {t(item.key)}
                  </span>
                )}
              </li>
            );
          })}
        </ul>
      </nav>
      <div className="mt-auto pt-(--spacing-card)">
        <LocaleToggle />
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
    <aside className="flex w-60 flex-col border-r border-border bg-surface p-4">
      <NavContent locale={locale} />
    </aside>
  );
}
