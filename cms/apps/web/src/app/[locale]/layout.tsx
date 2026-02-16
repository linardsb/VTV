import { NextIntlClientProvider } from "next-intl";
import { getMessages } from "next-intl/server";
import { auth } from "../../../auth";

export default async function LocaleLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  const messages = await getMessages();
  const session = await auth();

  return (
    <NextIntlClientProvider locale={locale} messages={messages}>
      <div className="flex min-h-screen">
        {session && (
          <aside className="w-60 border-r border-border bg-surface p-4">
            <nav aria-label="Main navigation">
              <p className="text-sm font-semibold text-foreground-muted mb-4">
                VTV
              </p>
              {/* Sidebar nav items will be added with feature pages */}
            </nav>
          </aside>
        )}
        <main id="main-content" className="flex-1 p-6">
          {children}
        </main>
      </div>
    </NextIntlClientProvider>
  );
}
