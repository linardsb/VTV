import type { Metadata } from "next";
import { cookies } from "next/headers";
import "./globals.css";

export const metadata: Metadata = {
  title: "VTV — Rīgas Satiksme",
  description: "Transit operations management for Riga municipal bus system",
};

const skipLinkText: Record<string, string> = {
  lv: "Pāriet uz saturu",
  en: "Skip to content",
};

export default async function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const store = await cookies();
  const locale = store.get("locale")?.value ?? "lv";

  return (
    <html lang={locale} suppressHydrationWarning>
      <body className="min-h-screen font-body antialiased">
        <a href="#main-content" className="skip-link">
          {skipLinkText[locale] ?? skipLinkText.lv}
        </a>
        {children}
      </body>
    </html>
  );
}
