import { useTranslations } from "next-intl";

export default function DashboardPage() {
  const t = useTranslations("dashboard");

  return (
    <div>
      <h1 className="font-heading text-2xl font-semibold mb-6">
        {t("title")}
      </h1>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <div className="rounded-lg border border-border bg-surface-raised p-4">
          <p className="text-sm text-foreground-muted">
            {t("activeRoutes", { count: 0 })}
          </p>
        </div>
        <div className="rounded-lg border border-border bg-surface-raised p-4">
          <p className="text-sm text-foreground-muted">
            {t("delayedRoutes", { count: 0 })}
          </p>
        </div>
      </div>
    </div>
  );
}
