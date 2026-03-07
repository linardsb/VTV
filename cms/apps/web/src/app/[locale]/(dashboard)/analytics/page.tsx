import { AnalyticsContent } from "@/components/analytics/analytics-content";

export default async function AnalyticsPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  return <AnalyticsContent locale={locale} />;
}
