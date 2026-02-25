"use client";

import { useTranslations } from "next-intl";
import { Badge } from "@/components/ui/badge";

interface CalendarStatusBadgeProps {
  startDate: string;
  endDate: string;
}

export function CalendarStatusBadge({ startDate, endDate }: CalendarStatusBadgeProps) {
  const t = useTranslations("schedules.calendars");
  const today = new Date().toISOString().split("T")[0];

  // Compare as ISO strings (YYYY-MM-DD) — lexicographic comparison works
  const isActive = startDate <= today && today <= endDate;
  const isExpired = endDate < today;

  if (isActive) {
    return (
      <Badge variant="outline" className="border-status-ontime/30 bg-status-ontime/10 text-status-ontime text-xs">
        {t("statusActive")}
      </Badge>
    );
  }

  if (isExpired) {
    return (
      <Badge variant="outline" className="border-border text-foreground-subtle text-xs">
        {t("statusExpired")}
      </Badge>
    );
  }

  return (
    <Badge variant="outline" className="border-status-delayed/30 bg-status-delayed/10 text-status-delayed text-xs">
      {t("statusUpcoming")}
    </Badge>
  );
}
