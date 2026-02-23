import { AppSidebar } from "@/components/app-sidebar";

export default async function DashboardLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;

  return (
    <div className="flex min-h-screen flex-col md:flex-row">
      <AppSidebar locale={locale} />
      <main id="main-content" className="flex-1 overflow-auto p-(--spacing-page)">
        {children}
      </main>
    </div>
  );
}
