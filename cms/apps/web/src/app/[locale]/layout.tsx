import { NextIntlClientProvider } from "next-intl";
import { getMessages } from "next-intl/server";
import { SessionProvider } from "next-auth/react";
import { Toaster } from "@/components/ui/sonner";
import { SWRProvider } from "@/components/swr-provider";

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
      <SessionProvider>
        <SWRProvider>
          {children}
        </SWRProvider>
        <Toaster />
      </SessionProvider>
    </NextIntlClientProvider>
  );
}
