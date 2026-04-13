import { RoutePerformanceDashboard } from "@/components/analytics/route-performance/route-performance-dashboard";

export default async function RoutePerformancePage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  return <RoutePerformanceDashboard locale={locale} />;
}
