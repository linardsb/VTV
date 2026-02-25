import { DashboardContent } from "@/components/dashboard/dashboard-content";

export default async function DashboardPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  return <DashboardContent locale={locale} />;
}
