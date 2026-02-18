import type { Metadata } from "next";
import { Lexend, Source_Sans_3 } from "next/font/google";
import { cookies } from "next/headers";
import "./globals.css";

const lexend = Lexend({
  subsets: ["latin", "latin-ext"],
  weight: ["300", "400", "500", "600", "700"],
  display: "swap",
  variable: "--font-lexend",
});

const sourceSans3 = Source_Sans_3({
  subsets: ["latin", "latin-ext"],
  weight: ["300", "400", "500", "600", "700"],
  display: "swap",
  variable: "--font-source-sans-3",
});

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
    <html lang={locale} suppressHydrationWarning className={`${lexend.variable} ${sourceSans3.variable}`}>
      <body className="min-h-screen font-body antialiased">
        <a href="#main-content" className="skip-link">
          {skipLinkText[locale] ?? skipLinkText.lv}
        </a>
        {children}
      </body>
    </html>
  );
}
