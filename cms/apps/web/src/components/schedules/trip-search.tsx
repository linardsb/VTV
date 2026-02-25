"use client";

import { useTranslations } from "next-intl";
import { Search } from "lucide-react";
import { Input } from "@/components/ui/input";

interface TripSearchProps {
  value: string;
  onChange: (value: string) => void;
}

export function TripSearch({ value, onChange }: TripSearchProps) {
  const t = useTranslations("schedules.trips");

  return (
    <div className="relative w-56">
      <Search className="absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-foreground-muted" aria-hidden="true" />
      <Input
        placeholder={t("searchPlaceholder")}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="pl-9 h-9"
      />
    </div>
  );
}
