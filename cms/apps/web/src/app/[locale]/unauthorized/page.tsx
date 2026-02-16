import { useTranslations } from "next-intl";

export default function UnauthorizedPage() {
  const t = useTranslations("common");

  return (
    <div className="flex min-h-screen items-center justify-center">
      <h1 className="text-2xl font-semibold">{t("unauthorized")}</h1>
    </div>
  );
}
