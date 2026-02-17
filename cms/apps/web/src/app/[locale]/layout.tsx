import { NextIntlClientProvider, useTranslations } from "next-intl";
import { getMessages } from "next-intl/server";
import Link from "next/link";
import { LocaleToggle } from "@/components/locale-toggle";

const navItems = [
  { key: "dashboard", href: "", enabled: true },
  { key: "routes", href: "/routes", enabled: false },
  { key: "stops", href: "/stops", enabled: false },
  { key: "schedules", href: "/schedules", enabled: false },
  { key: "gtfs", href: "/gtfs", enabled: false },
  { key: "users", href: "/users", enabled: false },
  { key: "chat", href: "/chat", enabled: false },
] as const;

function Sidebar({ locale }: { locale: string }) {
  const t = useTranslations("nav");

  return (
    <aside className="flex w-60 flex-col border-r border-border bg-surface p-4">
      <nav aria-label="Main navigation">
        <p className="text-sm font-semibold text-foreground-muted mb-(--spacing-card)">
          VTV
        </p>
        <ul className="space-y-1">
          {navItems.map((item) => (
            <li key={item.key}>
              {item.enabled ? (
                <Link
                  href={`/${locale}${item.href}`}
                  className="block rounded-md px-3 py-2 text-sm font-medium text-foreground hover:bg-surface-raised transition-colors"
                >
                  {t(item.key)}
                </Link>
              ) : (
                <span className="block rounded-md px-3 py-2 text-sm text-foreground-muted cursor-not-allowed opacity-50">
                  {t(item.key)}
                </span>
              )}
            </li>
          ))}
        </ul>
      </nav>
      <div className="mt-auto pt-(--spacing-card)">
        <LocaleToggle />
      </div>
    </aside>
  );
}

export default async function LocaleLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  const messages = await getMessages();

  return (
    <NextIntlClientProvider locale={locale} messages={messages}>
      <div className="flex min-h-screen">
        <Sidebar locale={locale} />
        <main id="main-content" className="flex-1 p-(--spacing-page)">
          {children}
        </main>
      </div>
    </NextIntlClientProvider>
  );
}
