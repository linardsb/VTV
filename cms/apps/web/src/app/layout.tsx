import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "VTV — Rigas Satiksme",
  description: "Transit operations management for Riga municipal bus system",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="lv" suppressHydrationWarning>
      <body className="min-h-screen font-body antialiased">
        <a href="#main-content" className="skip-link">
          Pariet uz saturu
        </a>
        {children}
      </body>
    </html>
  );
}
