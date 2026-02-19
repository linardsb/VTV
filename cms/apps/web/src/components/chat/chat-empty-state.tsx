"use client";

import { Bot } from "lucide-react";
import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";

interface ChatEmptyStateProps {
  onSuggestionClick: (text: string) => void;
}

export function ChatEmptyState({ onSuggestionClick }: ChatEmptyStateProps) {
  const t = useTranslations("chat");

  const suggestions = [
    t("suggestion1"),
    t("suggestion2"),
    t("suggestion3"),
    t("suggestion4"),
  ];

  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-(--spacing-lg) px-(--spacing-page) text-center">
      <div className="flex size-16 items-center justify-center rounded-2xl bg-interactive/10">
        <Bot className="size-8 text-interactive" />
      </div>
      <div className="space-y-(--spacing-tight)">
        <h2 className="font-heading text-lg font-semibold text-foreground">
          {t("emptyTitle")}
        </h2>
        <p className="max-w-md text-sm text-foreground-muted">
          {t("emptyDescription")}
        </p>
      </div>
      <div className="flex flex-wrap justify-center gap-(--spacing-sm)">
        {suggestions.map((suggestion) => (
          <Button
            key={suggestion}
            variant="outline"
            size="sm"
            className="cursor-pointer text-sm"
            onClick={() => onSuggestionClick(suggestion)}
          >
            {suggestion}
          </Button>
        ))}
      </div>
    </div>
  );
}
